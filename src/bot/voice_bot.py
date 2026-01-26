from ..config import Config
import asyncio
from typing import Dict, Any, List

# Pipecat Core
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import EndFrame, TextFrame, StartFrame
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMAssistantContextAggregator
)

# Services
from pipecat.services.anthropic import AnthropicLLMService
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService

# Context & Processors
from pipecat.processors.aggregators.llm_context import LLMContext 
from pipecat.processors.frame_processor import FrameProcessor

# Custom adapters
from ..adapters.base import STTAdapter, TTSAdapter, LLMAdapter, CalendarAdapter, TelephonyAdapter
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
        stt_adapter: STTAdapter,
        tts_adapter: TTSAdapter,
        llm_adapter: LLMAdapter,
        calendar_adapter: CalendarAdapter,
        menu_rag: MenuRAG,
        guardrails: Guardrails,
        transfer_queue: TransferQueue,
        call_sid: str,
        caller_id: str
    ):
        self.transport = transport
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
        
        # 3. Initialize Services with Tools
        self.stt = DeepgramSTTService(api_key=Config.DEEPGRAM_API_KEY, audio_passthrough=True)
        self.tts = ElevenLabsTTSService(api_key=Config.ELEVENLABS_API_KEY, voice_id=Config.ELEVENLABS_VOICE_ID)
        
        # Pass the definitions here
        self.llm = AnthropicLLMService(
            api_key=Config.ANTHROPIC_API_KEY, 
            model=Config.ANTHROPIC_MODEL,
            tools=self.tool_definitions
        )

        # 4. Register Callbacks (The "How")
        self._register_tool_handlers()

    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
        Your role is to help customers make reservations, answer menu questions, and transfer to staff.
        Keep responses concise and conversational."""

    def _register_tool_handlers(self):
        """Bind Python functions to the tool names registered in the LLM Service"""
        
        # Tool: Query Menu
        async def query_menu(function_name, tool_call_id, args, llm, context, result_callback):
            # Note: Pipecat v0.3 callbacks receive specific arguments
            question = args.get("question")
            results = self.menu_rag.query(question, n_results=3)
            if results:
                formatted = "\n".join([f"- {r['name']}: {r['description']} (${r['price']:.2f})" for r in results])
                await result_callback(f"Here are some menu items:\n{formatted}")
            else:
                await result_callback("I couldn't find any menu items matching that.")

        # Tool: Create Reservation
        async def create_reservation(function_name, tool_call_id, args, llm, context, result_callback):
            # Validate
            is_valid, error = self.guardrails.validate_reservation_info(args)
            if not is_valid:
                await result_callback(f"Issue with details: {error}")
                return

            # Check Availability
            available = await self.calendar_adapter.check_availability(
                args["date"], args["time"], args["party_size"]
            )
            if not available:
                await result_callback("That time slot is not available.")
                return

            # Book
            result = await self.calendar_adapter.create_reservation(args)
            if "error" in result:
                await result_callback(f"Error creating reservation: {result['error']}")
            else:
                await result_callback(f"Reservation confirmed! Confirmation number: {result.get('reservation_id')}")

        # Tool: Transfer
        async def transfer_to_staff(function_name, tool_call_id, args, llm, context, result_callback):
            reason = args.get("reason")
            request = TransferRequest(
                call_sid=self.call_sid,
                caller_id=self.caller_id,
                reason=reason,
                priority=TransferPriority.NORMAL
            )
            position = await self.transfer_queue.enqueue_transfer(request)
            await result_callback(f"Transferring you now. Your position is {position}.")

        # Register the handlers using the new method
        self.llm.register_function("query_menu", query_menu)
        self.llm.register_function("create_reservation", create_reservation)
        self.llm.register_function("transfer_to_staff", transfer_to_staff)

    async def run(self):
        """Build and run the pipeline"""
        
        user_context = LLMUserContextAggregator(self.context)
        assistant_context = LLMAssistantContextAggregator(self.context)

        pipeline = Pipeline([
            self.transport.input(),
            self.stt,
            user_context,
            self.llm,
            self.tts,
            self.transport.output(),
            assistant_context
        ])

        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        # Send an initial greeting after pipeline starts
        # This helps trigger the conversation and lets the user know the bot is ready
        async def send_greeting():
            await asyncio.sleep(1.5)  # Give pipeline time to fully initialize and start audio capture
            try:
                # Add a greeting message to the context and trigger LLM response
                greeting_text = "Hello! How can I help you today?"
                # Push text frame into the user context aggregator to trigger LLM
                greeting_frame = TextFrame(text=greeting_text)
                await user_context.process_frame(greeting_frame, "downstream")
                print(f"[VOICE] Sent initial greeting: {greeting_text}")
            except Exception as e:
                print(f"[VOICE] Error sending greeting: {e}")
        
        # Start the greeting in background
        asyncio.create_task(send_greeting())
        
        print("[VOICE] Starting pipeline runner...")
        await runner.run(task)
        print("[VOICE] Pipeline runner finished")