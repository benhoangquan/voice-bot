"""Text-to-Speech adapter implementations"""

from typing import AsyncIterator
import asyncio
from .base import TTSAdapter
from elevenlabs.client import AsyncElevenLabs

class ElevenLabsAdapter(TTSAdapter):
    """ElevenLabs TTS adapter (SDK v1+)"""
    
    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        self.client = AsyncElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.current_stream: Optional[AsyncIterator[bytes]] = None
        self._is_cancelled = False # 1. Add a cancellation flag
    
    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text to audio stream"""
        self._is_cancelled = False # Reset flag at start
        
        try:
            # Get the generator from the SDK
            audio_stream = await self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128"
            )
            
            self.current_stream = audio_stream
            
            # Iterate through chunks
            async for chunk in audio_stream:
                # 2. Check flag before yielding
                if self._is_cancelled:
                    # Optional: Explicitly close generator if supported
                    if hasattr(audio_stream, 'aclose'):
                        await audio_stream.aclose()
                    break
                    
                if chunk:
                    yield chunk
                    
        except Exception as e:
            print(f"TTS synthesis error: {e}")
            yield b""
        finally:
            self.current_stream = None


    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio (accumulate into single bytes object)"""
        self._is_cancelled = False # Reset flag
        audio_data = bytearray()   # Use bytearray for efficient appending
        
        try:
            # We use the same convert method, which returns an async generator
            stream = await self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id="eleven_turbo_v2_5",
                output_format="mp3_44100_128"
            )
            
            # Save reference so cancel() can close it
            self.current_stream = stream
            
            async for chunk in stream:
                # 1. Check cancellation flag
                if self._is_cancelled:
                    if hasattr(stream, 'aclose'):
                        await stream.aclose()
                    return b"" # Return empty bytes on cancel
                
                # 2. Accumulate chunks
                if chunk:
                    audio_data.extend(chunk)
            
            return bytes(audio_data)

        except Exception as e:
            print(f"TTS synthesis error: {e}")
            return b""
        finally:
            self.current_stream = None

    async def cancel(self) -> None:
        """Cancel current synthesis"""
        # 3. Set flag to stop the loop
        self._is_cancelled = True
        
        # 4. Force close the stream if it's currently active
        if self.current_stream and hasattr(self.current_stream, 'aclose'):
            try:
                await self.current_stream.aclose()
            except Exception as e:
                print(f"Error closing stream: {e}")

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
