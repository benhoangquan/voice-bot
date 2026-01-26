from ..config import Config
import asyncio
from typing import Dict, Any, List

# Pipecat Core
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.frames.frames import EndFrame
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMAssistantContextAggregator
)

# Services
from pipecat.services.anthropic import AnthropicLLMService
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService

# Context Management
from pipecat.processors.frame_processor import FrameProcessor
# --- FIXED IMPORTS ---
# 1. Aggregators (Logic that adds messages to history)
from pipecat.processors.aggregators.llm_response import (
    LLMUserContextAggregator,
    LLMAssistantContextAggregator
)

# 2. Context (The actual history object)
# Moved from 'pipecat.services.llm' to here:
from pipecat.processors.aggregators.llm_context import LLMContext 

# 3. Processors
from pipecat.processors.frame_processor import FrameProcessor
# ---------------------

# Your custom adapters (assumed to exist)
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
        transport,  # Transport is passed in (e.g., DailyTransport, TwilioTransport)
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
        
        # 1. Initialize Context with System Prompt
        self.context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": self._create_system_prompt()
                }
            ]
        )
        
        # 2. Initialize Services
        # Note: In a real app, pass API keys or clients here
        self.stt = DeepgramSTTService(api_key=Config.DEEPGRAM_API_KEY, audio_passthrough=True)
        self.tts = ElevenLabsTTSService(api_key=Config.ELEVENLABS_API_KEY, voice_id=Config.ELEVENLABS_VOICE_ID)
        self.llm = AnthropicLLMService(api_key=Config.ANTHROPIC_API_KEY, model=Config.ANTHROPIC_MODEL)

        # 3. Register Tools
        self._register_tools()

    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
        Your role is to help customers make reservations, answer menu questions, and transfer to staff.
        Keep responses concise and conversational."""

    def _register_tools(self):
        """Register tools directly with the Pipecat LLM Service"""
        
        # Tool: Query Menu
        async def query_menu(question: str):
            results = self.menu_rag.query(question, n_results=3)
            if results:
                formatted = "\n".join([f"- {r['name']}: {r['description']} (${r['price']:.2f})" for r in results])
                return f"Here are some menu items:\n{formatted}"
            return "I couldn't find any menu items matching that."

        self.llm.register_function(
            "query_menu",
            query_menu,
            description="Query the restaurant menu for items and prices",
            properties={"question": {"type": "string"}}
        )

        # Tool: Create Reservation
        async def create_reservation(date: str, time: str, party_size: int, customer_name: str, customer_phone: str):
            # Guardrails check
            is_valid, error = self.guardrails.validate_reservation_info(locals())
            if not is_valid:
                return f"Issue with details: {error}"
            
            # Availability check
            available = await self.calendar_adapter.check_availability(date, time, party_size)
            if not available:
                return "That time slot is not available."

            # Booking
            result = await self.calendar_adapter.create_reservation(locals())
            if "error" in result:
                return f"Error creating reservation: {result['error']}"
            return f"Reservation confirmed! Confirmation number: {result.get('reservation_id')}"

        self.llm.register_function(
            "create_reservation",
            create_reservation,
            description="Create a restaurant reservation",
            properties={
                "date": {"type": "string"},
                "time": {"type": "string"},
                "party_size": {"type": "integer"},
                "customer_name": {"type": "string"},
                "customer_phone": {"type": "string"}
            }
        )

        # Tool: Transfer
        async def transfer_to_staff(reason: str):
            request = TransferRequest(
                call_sid=self.call_sid,
                caller_id=self.caller_id,
                reason=reason,
                priority=TransferPriority.NORMAL
            )
            position = await self.transfer_queue.enqueue_transfer(request)
            
            # In a real Pipecat app, triggering a transfer usually involves 
            # sending a specific frame or signal to the telephony provider.
            # Here we return a message, but you might also emit a control frame.
            return f"Transferring you now. Your position is {position}."

        self.llm.register_function(
            "transfer_to_staff",
            transfer_to_staff,
            description="Transfer to human staff",
            properties={"reason": {"type": "string"}}
        )

    async def run(self):
        """Build and run the pipeline"""
        
        # 4. Context Aggregators manage the chat history automatically
        # They collect user speech -> add to context -> send to LLM
        user_context = LLMUserContextAggregator(self.context)
        assistant_context = LLMAssistantContextAggregator(self.context)

        # 5. Define Pipeline Flow
        pipeline = Pipeline([
            self.transport.input(),   # Audio from phone/web
            self.stt,                 # Speech to Text
            user_context,             # Add user text to LLM context
            self.llm,                 # Generate response (and handle tools)
            self.tts,                 # Text to Speech
            self.transport.output(),  # Audio back to phone/web
            assistant_context         # Add assistant response to LLM context
        ])

        # 6. Run the Task
        task = PipelineTask(pipeline)
        runner = PipelineRunner()
        
        await runner.run(task)