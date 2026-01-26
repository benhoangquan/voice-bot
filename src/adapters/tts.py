"""Text-to-Speech adapter implementations"""

from typing import AsyncIterator
import asyncio
from .base import TTSAdapter
from elevenlabs.client import AsyncElevenLabs

class ElevenLabsAdapter(TTSAdapter):
    """ElevenLabs TTS adapter (SDK v1+)"""
    
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        # Initialize the async client with the API key
        self.client = AsyncElevenLabs(api_key=api_key)
        self.voice_id = voice_id
    
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text to audio stream"""
        try:
            # The v1 SDK 'convert' method returns an async generator
            response = await self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128"  # Optional: specific format
            )
            
            # Yield chunks as they arrive
            async for chunk in response:
                if chunk:
                    yield chunk

        except Exception as e:
            print(f"TTS synthesis error: {e}")
            yield b""
    
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio (accumulate stream)"""
        try:
            # Even for non-streaming, the async client returns an iterator.
            # We simply accumulate the chunks.
            response = await self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2_5"
            )
            
            # Gather all chunks into a single bytes object
            audio_data = b""
            async for chunk in response:
                audio_data += chunk
                
            return audio_data

        except Exception as e:
            print(f"TTS synthesis error: {e}")
            return b""

class QwenTTSAdapter(TTSAdapter):
    """Qwen3-TTS adapter (future open-source implementation)"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        # TODO: Initialize Qwen3-TTS model
    
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text to audio stream using Qwen3-TTS"""
        # TODO: Implement Qwen3-TTS streaming
        yield b""
    
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio using Qwen3-TTS"""
        # TODO: Implement Qwen3-TTS synthesis
        return b""
    
    async def cancel(self) -> None:
        """Cancel current synthesis"""
        # TODO: Implement cancellation
        pass
