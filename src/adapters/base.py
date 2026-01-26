"""Base adapter interfaces using ABC pattern"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Dict, Any, Optional
from pydantic import BaseModel


class AudioStream:
    """Represents an audio stream"""
    pass


class TelephonyAdapter(ABC):
    """Base interface for telephony providers"""
    
    @abstractmethod
    async def connect(self, call_sid: str) -> AudioStream:
        """Connect to a call and return audio stream"""
        pass
    
    @abstractmethod
    async def transfer(self, call_sid: str, target: str, context: Dict[str, Any]) -> bool:
        """Transfer call to target with context"""
        pass
    
    @abstractmethod
    async def hangup(self, call_sid: str) -> None:
        """Hang up the call"""
        pass
    
    @abstractmethod
    async def get_audio_stream(self, call_sid: str) -> AsyncIterator[bytes]:
        """Get audio stream from call"""
        pass


class STTAdapter(ABC):
    """Base interface for Speech-to-Text providers"""
    
    @abstractmethod
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe audio stream in real-time"""
        pass
    
    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio chunk"""
        pass
    
    @abstractmethod
    async def get_partial_results(self) -> Optional[str]:
        """Get partial transcription results"""
        pass


class TTSAdapter(ABC):
    """Base interface for Text-to-Speech providers"""
    
    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text to audio stream"""
        pass
    
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio"""
        pass
    
    @abstractmethod
    async def cancel(self) -> None:
        """Cancel current synthesis"""
        pass


class LLMAdapter(ABC):
    """Base interface for LLM providers"""
    
    @abstractmethod
    async def chat(self, messages: list[Dict[str, Any]], tools: Optional[list] = None) -> Dict[str, Any]:
        """Chat with LLM and return response"""
        pass
    
    @abstractmethod
    async def chat_stream(self, messages: list[Dict[str, Any]], tools: Optional[list] = None) -> AsyncIterator[str]:
        """Chat with LLM and stream response"""
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool function"""
        pass


class CalendarAdapter(ABC):
    """Base interface for calendar/reservation providers"""
    
    @abstractmethod
    async def create_reservation(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create a reservation"""
        pass
    
    @abstractmethod
    async def check_availability(self, date: str, time: str, party_size: int) -> bool:
        """Check if time slot is available"""
        pass
    
    @abstractmethod
    async def cancel_reservation(self, reservation_id: str) -> bool:
        """Cancel a reservation"""
        pass
