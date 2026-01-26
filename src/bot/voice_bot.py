"""Main voice bot application using Pipecat"""

import asyncio
from typing import Dict, Any, Optional, List
from pipecat.frames.frames import (
    AudioRawFrame,
    TextFrame,
    LLMMessagesFrame,
    LLMResponseStartFrame,
    LLMResponseEndFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import LLMResponseAggregator
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.anthropic import AnthropicLLMService
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.vad.silero import SileroVADAnalyzer

from ..adapters.base import STTAdapter, TTSAdapter, LLMAdapter, CalendarAdapter, TelephonyAdapter
from ..adapters.stt import DeepgramAdapter
from ..adapters.tts import ElevenLabsAdapter
from ..adapters.llm import AnthropicAdapter
from ..adapters.calendar import YelpAdapter
from ..rag.menu_rag import MenuRAG
from ..guardrails.safety import Guardrails
from ..transfer.queue import TransferQueue, TransferRequest, TransferPriority, StaffStatus, StaffMember
from ..config import Config


class ToolProcessor(FrameProcessor):
    """Process tool calls from LLM"""
    
    def __init__(
        self,
        menu_rag: MenuRAG,
        calendar_adapter: CalendarAdapter,
        transfer_queue: TransferQueue,
        guardrails: Guardrails,
        telephony_adapter: TelephonyAdapter,
        call_sid: str,
        caller_id: str
    ):
        super().__init__()
        self.menu_rag = menu_rag
        self.calendar_adapter = calendar_adapter
        self.transfer_queue = transfer_queue
        self.guardrails = guardrails
        self.telephony_adapter = telephony_adapter
        self.call_sid = call_sid
        self.caller_id = caller_id
        self.conversation_context: List[Dict[str, str]] = []
    
    async def process_frame(self, frame, direction):
        """Process frames and handle tool calls"""
        await super().process_frame(frame, direction)
        
        # Handle LLM messages
        if isinstance(frame, LLMMessagesFrame):
            self.conversation_context = frame.messages
        
        # Handle tool calls (would be in LLM response)
        # This is simplified - actual implementation would parse tool calls from LLM response
        
        await self.push_frame(frame, direction)


class VoiceBot:
    """Main voice bot application"""
    
    def __init__(
        self,
        telephony_adapter: TelephonyAdapter,
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
        self.telephony_adapter = telephony_adapter
        self.stt_adapter = stt_adapter
        self.tts_adapter = tts_adapter
        self.llm_adapter = llm_adapter
        self.calendar_adapter = calendar_adapter
        self.menu_rag = menu_rag
        self.guardrails = guardrails
        self.transfer_queue = transfer_queue
        self.call_sid = call_sid
        self.caller_id = caller_id
        
        self.conversation_history: List[Dict[str, str]] = []
        self.reservation_context: Dict[str, Any] = {}
        
        # Initialize system prompt
        self.system_prompt = self._create_system_prompt()
        
        # Tool definitions
        self.tools = self._create_tools()
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for the bot"""
        return """You are a friendly and professional voice assistant for a restaurant reservation system. 
Your role is to:
1. Help customers make reservations by collecting: date, time, party size, customer name, phone number, and any special requests
2. Answer questions about the menu using the menu query tool
3. Transfer customers to human staff when they request it or when you cannot help
4. Be concise and natural in conversation
5. Confirm reservation details before booking
6. Handle interruptions gracefully (barge-in)

Always be polite, professional, and helpful. If a customer seems frustrated, offer to transfer them to a human staff member."""
    
    def _create_tools(self) -> List[Dict[str, Any]]:
        """Create tool definitions for LLM"""
        return [
            {
                "name": "query_menu",
                "description": "Query the restaurant menu for items, prices, dietary information, or availability",
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
            },
            {
                "name": "create_reservation",
                "description": "Create a restaurant reservation with all required details",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string", "description": "Reservation date in YYYY-MM-DD format"},
                        "time": {"type": "string", "description": "Reservation time in HH:MM format"},
                        "party_size": {"type": "integer", "description": "Number of people"},
                        "customer_name": {"type": "string", "description": "Customer's name"},
                        "customer_phone": {"type": "string", "description": "Customer's phone number"},
                        "customer_email": {"type": "string", "description": "Customer's email (optional)"},
                        "special_requests": {"type": "string", "description": "Any special requests or dietary restrictions"}
                    },
                    "required": ["date", "time", "party_size", "customer_name", "customer_phone"]
                }
            },
            {
                "name": "transfer_to_staff",
                "description": "Transfer the customer to a human staff member. Use when customer requests it or when you cannot help",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {"type": "string", "description": "Reason for transfer"}
                    },
                    "required": ["reason"]
                }
            },
            {
                "name": "validate_reservation_info",
                "description": "Validate reservation information before creating it",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "info": {
                            "type": "object",
                            "description": "Reservation information to validate"
                        }
                    },
                    "required": ["info"]
                }
            }
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Handle tool calls from LLM"""
        if tool_name == "query_menu":
            question = arguments.get("question", "")
            results = self.menu_rag.query(question, n_results=3)
            
            # Format results for LLM
            if results:
                formatted = "\n".join([
                    f"- {r['name']}: {r['description']} (${r['price']:.2f})"
                    for r in results
                ])
                return f"Here are some menu items that match your query:\n{formatted}"
            else:
                return "I couldn't find any menu items matching your query. Would you like to speak with a staff member?"
        
        elif tool_name == "create_reservation":
            # Validate first
            is_valid, error = self.guardrails.validate_reservation_info(arguments)
            if not is_valid:
                return f"I'm sorry, there's an issue with the reservation details: {error}. Please provide the correct information."
            
            # Check availability
            available = await self.calendar_adapter.check_availability(
                arguments.get("date"),
                arguments.get("time"),
                arguments.get("party_size", 1)
            )
            
            if not available:
                return "I'm sorry, that time slot is not available. Would you like to try a different time?"
            
            # Create reservation
            result = await self.calendar_adapter.create_reservation(arguments)
            
            if "error" in result:
                return f"I'm sorry, I couldn't create the reservation: {result['error']}. Would you like to speak with a staff member?"
            
            reservation_id = result.get("reservation_id", "unknown")
            return f"Great! I've created your reservation. Your confirmation number is {reservation_id}. We look forward to seeing you!"
        
        elif tool_name == "transfer_to_staff":
            reason = arguments.get("reason", "Customer requested")
            
            # Create transfer request
            request = TransferRequest(
                call_sid=self.call_sid,
                caller_id=self.caller_id,
                reason=reason,
                context={
                    "conversation_history": self.conversation_history[-5:],  # Last 5 messages
                    "reservation_context": self.reservation_context,
                },
                priority=TransferPriority.NORMAL
            )
            
            position = await self.transfer_queue.enqueue_transfer(request)
            
            if position == 1:
                # Try to assign immediately
                staff = await self.transfer_queue.assign_transfer(request)
                if staff:
                    # Perform transfer
                    await self.telephony_adapter.transfer(
                        self.call_sid,
                        staff.phone,
                        request.context
                    )
                    return f"Transferring you to {staff.name} now. Please hold."
            
            wait_time = request.estimated_wait or 0
            return f"I'll transfer you to a staff member. Your position in queue is {position}. Estimated wait time is {wait_time // 60} minutes."
        
        elif tool_name == "validate_reservation_info":
            info = arguments.get("info", {})
            is_valid, error = self.guardrails.validate_reservation_info(info)
            if is_valid:
                return "The reservation information looks good!"
            else:
                return f"There are some issues: {error}"
        
        return "I'm not sure how to handle that request."
    
    async def process_user_input(self, text: str) -> str:
        """Process user input and generate response"""
        # Check guardrails
        if self.guardrails.check_profanity(text):
            return "I'm sorry, but I can't help with that. Is there something else I can assist you with?"
        
        # Add user message to history
        self.conversation_history.append({"role": "user", "content": text})
        
        # Prepare messages for LLM
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.conversation_history)
        
        # Get LLM response
        response = await self.llm_adapter.chat(messages, tools=self.tools)
        
        # Check for tool calls
        if response.get("tool_calls"):
            # Process tool calls
            for tool_call in response.get("tool_calls", []):
                tool_name = tool_call.get("name")
                tool_input = tool_call.get("input", {})
                
                if tool_name:
                    tool_result = await self.handle_tool_call(tool_name, tool_input)
                    
                    # Add tool result to conversation in Anthropic format
                    messages.append({
                        "role": "assistant",
                        "content": [{
                            "type": "tool_use",
                            "id": tool_call.get("id", "tool_1"),
                            "name": tool_name,
                            "input": tool_input
                        }]
                    })
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tool_call.get("id", "tool_1"),
                            "content": tool_result
                        }]
                    })
                    
                    # Get final response after tool execution
                    response = await self.llm_adapter.chat(messages, tools=self.tools)
        
        response_text = response.get("content", "I'm sorry, I didn't understand that.")
        
        # Add assistant response to history
        self.conversation_history.append({"role": "assistant", "content": response_text})
        
        return response_text
    
    async def run(self):
        """Run the voice bot"""
        # This is a simplified version - actual implementation would use Pipecat pipeline
        # For now, this provides the core logic that would be integrated with Pipecat
        
        # Check guardrails
        if not self.guardrails.check_rate_limit(self.caller_id):
            return "Rate limit exceeded"
        
        if self.guardrails.check_blocked(self.caller_id):
            return "Call blocked"
        
        # Main conversation loop would be handled by Pipecat pipeline
        # This method provides the core processing logic
