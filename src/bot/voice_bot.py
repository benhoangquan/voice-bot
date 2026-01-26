from ..config import Config
import asyncio
from typing import Dict, Any, List, Optional

# Pipecat Core
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import EndFrame, TextFrame, StartFrame
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.llm_service import FunctionCallParams

# Context & Processors
from pipecat.processors.aggregators.llm_context import LLMContext 
from pipecat.processors.frame_processor import FrameProcessor

# Custom adapters
# We only import the ones we actually use for business logic, not the ones replaced by Pipecat services
from ..adapters.base import CalendarAdapter
from ..rag.menu_rag import MenuRAG
from ..guardrails.safety import Guardrails
from ..transfer.queue import TransferQueue, TransferRequest, TransferPriority

class VoiceBot:
    """
    Modern Pipecat VoiceBot. 
    Manages the PipelineTask and connects business logic (adapters) to LLM Tools.
    """

    def __init__(
        self,
        transport,
        stt_service,
        tts_service,
        llm_service,    
        calendar_adapter: CalendarAdapter,
        menu_rag: MenuRAG,
        guardrails: Guardrails,
        transfer_queue: TransferQueue,
        call_sid: str,
        caller_id: str
    ):
        self.transport = transport
        self.stt = stt_service
        self.tts = tts_service
        self.llm = llm_service
        self.calendar_adapter = calendar_adapter
        self.menu_rag = menu_rag
        self.guardrails = guardrails
        self.transfer_queue = transfer_queue
        self.call_sid = call_sid
        self.caller_id = caller_id
        
        # 1. Initialize Context
        self.context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": self._create_system_prompt()
                }
            ]
        )
        
        # 2. Define Tool Schemas (The "What")
        # We pass these to the LLM so it knows what tools exist.
        self.tool_definitions = [
            {
                "type": "function",
                "function": {
                    "name": "query_menu",
                    "description": "Query the restaurant menu for items and prices",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "The customer's question about the menu"
                            }
                        },
                        "required": ["question"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_reservation",
                    "description": "Create a restaurant reservation",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "YYYY-MM-DD"},
                            "time": {"type": "string", "description": "HH:MM"},
                            "party_size": {"type": "integer"},
                            "customer_name": {"type": "string"},
                            "customer_phone": {"type": "string"}
                        },
                        "required": ["date", "time", "party_size", "customer_name", "customer_phone"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "transfer_to_staff",
                    "description": "Transfer to human staff",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {"type": "string"}
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]
        self.llm.tools = self.tool_definitions

        # 4. Register Callbacks (The "How")
        self._register_tool_handlers()

    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
        Your role is to help customers make reservations, answer menu questions, and transfer to staff.
        Keep responses very concise and conversational."""

    def _register_tool_handlers(self):
        """Bind Python functions to the tool names registered in the LLM Service"""
        
        # Tool: Query Menu
        async def query_menu(params: FunctionCallParams):
            question = params.arguments.get("question")
            results = self.menu_rag.query(question, n_results=3)
            if results:
                formatted = "\n".join([f"- {r['name']}: {r['description']} (${r['price']:.2f})" for r in results])
                await params.result_callback(f"Here are some menu items:\n{formatted}")
            else:
                await params.result_callback("I couldn't find any menu items matching that.")

        # Tool: Create Reservation
        async def create_reservation(params: FunctionCallParams):
            args = params.arguments
            # Validate
            is_valid, error = self.guardrails.validate_reservation_info(args)
            if not is_valid:
                await params.result_callback(f"Issue with details: {error}")
                return

            # Check Availability
            available = await self.calendar_adapter.check_availability(
                args["date"], args["time"], args["party_size"]
            )
            if not available:
                await params.result_callback("That time slot is not available.")
                return

            # Book
            result = await self.calendar_adapter.create_reservation(args)
            if "error" in result:
                await params.result_callback(f"Error creating reservation: {result['error']}")
            else:
                await params.result_callback(f"Reservation confirmed! Confirmation number: {result.get('reservation_id')}")

        # Tool: Transfer
        async def transfer_to_staff(params: FunctionCallParams):
            reason = params.arguments.get("reason")
            request = TransferRequest(
                call_sid=self.call_sid,
                caller_id=self.caller_id,
                reason=reason,
                priority=TransferPriority.NORMAL
            )
            position = await self.transfer_queue.enqueue_transfer(request)
            await params.result_callback(f"Transferring you now. Your position is {position}.")

        # Register the handlers using the new method
        self.llm.register_function("query_menu", query_menu)
        self.llm.register_function("create_reservation", create_reservation)
        self.llm.register_function("transfer_to_staff", transfer_to_staff)

    async def run(self):
        context_aggregator = LLMContextAggregatorPair(self.context)
        user_context = context_aggregator.user()
        assistant_context = context_aggregator.assistant()

        # 1. FIXED PIPELINE ORDER
        pipeline = Pipeline([
            self.transport.input(),
            self.stt,
            user_context,
            self.llm,
            assistant_context, # Must be BEFORE TTS so it sees the text
            self.tts,
            self.transport.output(),
        ])

        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        # 2. FIXED GREETING LOGIC
        async def send_greeting():
            await asyncio.sleep(2.0) # Wait for media connection
            greeting_text = "Hello! I am ready to take your order."
            print(f"[VOICE] 🔊 Sending greeting: {greeting_text}")
            
            # A. Add to memory manually (since we bypass LLM)
            self.context.add_message({"role": "assistant", "content": greeting_text})
            
            # B. Inject directly into the pipeline (Targeting TTS)
            await task.queue_frame(TextFrame(text=greeting_text))

        asyncio.create_task(send_greeting())
        
        # 3. REGISTER EXIT HANDLER (For Part 2)
        @self.transport.event_handler("on_participant_left")
        async def on_participant_left(transport, participant, reason):
            # Check how many people are left. If only 1 (the bot), we exit.
            params = transport.participant_counts()
            print(f"[VOICE] Participant left. Remaining: {params['present']}")
            if params['present'] <= 1:
                print("[VOICE] Last user left. Shutting down...")
                await task.cancel()

        print("[VOICE] Starting pipeline runner...")
        await runner.run(task)
