"""Speech-to-Text adapter implementations"""

from typing import AsyncIterator, Optional
import asyncio
from deepgram import DeepgramClient
from deepgram.core.events import EventType

from .base import STTAdapter


class DeepgramAdapter(STTAdapter):
    """Deepgram Nova 3 STT adapter"""
    
    def __init__(self, api_key: str):
        self.client = DeepgramClient(api_key)
        self.partial_result: Optional[str] = None
        self.live_connection = None
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe audio stream in real-time"""
        # Create live transcription connection using v1 API
        # connect() returns an Iterator (context manager), so we need to enter it
        connection_iter = self.client.listen.v1.connect(
            model="nova-2",
            language="en-US",
            smart_format="true",
            interim_results="true",
            endpointing="300",
        )
        
        # Get the connection from the iterator
        connection = next(connection_iter)
        
        connection.on(EventType.OPEN, self._on_open)
        connection.on(EventType.MESSAGE, self._on_message)
        connection.on(EventType.ERROR, self._on_error)
        connection.on(EventType.CLOSE, self._on_close)
        
        connection.start_listening()
        self.live_connection = connection
        
        try:
            # Send audio chunks and yield transcriptions
            async for audio_chunk in audio_stream:
                connection.send(audio_chunk)
                if self.partial_result:
                    yield self.partial_result
                    self.partial_result = None
                await asyncio.sleep(0.01)  # Small delay for processing
        finally:
            # Clean up connection
            if self.live_connection:
                try:
                    connection.finish()
                except:
                    pass
                self.live_connection = None
    
    def _on_open(self, *args, **kwargs):
        """Handle connection open"""
        pass
    
    def _on_message(self, message, **kwargs):
        """Handle transcription message"""
        # In v5, the message structure may be different
        # Check if message has results/channel structure
        if hasattr(message, 'results') and message.results:
            if hasattr(message.results, 'channels') and message.results.channels:
                channel = message.results.channels[0]
                if hasattr(channel, 'alternatives') and channel.alternatives:
                    sentence = channel.alternatives[0].transcript
                    if sentence:
                        self.partial_result = sentence
        elif hasattr(message, 'channel'):
            # Alternative structure
            if hasattr(message.channel, 'alternatives') and message.channel.alternatives:
                sentence = message.channel.alternatives[0].transcript
                if sentence:
                    self.partial_result = sentence
    
    def _on_error(self, *args, **kwargs):
        """Handle error"""
        error = kwargs.get("error")
        print(f"Deepgram error: {error}")
    
    def _on_close(self, *args, **kwargs):
        """Handle connection close"""
        pass
    
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio chunk"""
        # Use v5 API: transcribe_file takes request as first arg, then keyword options
        # Note: This is a synchronous call, but we're in an async function
        # In a real async context, you might want to use AsyncDeepgramClient
        response = self.client.listen.v1.media.transcribe_file(
            request=audio,
            model="nova-2",
            language="en-US",
            smart_format="true",
        )
        
        if response.results and response.results.channels:
            return response.results.channels[0].alternatives[0].transcript
        return ""
    
    async def get_partial_results(self) -> Optional[str]:
        """Get partial transcription results"""
        result = self.partial_result
        self.partial_result = None
        return result


class WhisperAdapter(STTAdapter):
    """Whisper.cpp adapter (future open-source implementation)"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        # TODO: Initialize Whisper model
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe audio stream using Whisper"""
        # TODO: Implement Whisper streaming transcription
        async for chunk in audio_stream:
            # Process chunk with Whisper
            yield ""
    
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio chunk using Whisper"""
        # TODO: Implement Whisper transcription
        return ""
    
    async def get_partial_results(self) -> Optional[str]:
        """Get partial transcription results"""
        # TODO: Implement partial results
        return None
