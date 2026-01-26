"""Speech-to-Text adapter implementations (Deepgram SDK v3)"""

import logging
from typing import AsyncIterator, Optional
import asyncio

# Deepgram SDK v3 imports
from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
    PrerecordedOptions,
)

from .base import STTAdapter

class DeepgramAdapter(STTAdapter):
    """Deepgram Nova 2/3 STT adapter using SDK v3"""
    
    def __init__(self, api_key: str):
        # Initialize with default options
        # For production, consider adding verbose=logging.DEBUG to options for troubleshooting
        self.client = DeepgramClient(api_key)
        self.partial_result: Optional[str] = None
        self.final_result: Optional[str] = None
        
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[str]:
        """Transcribe audio stream in real-time"""
        
        # 1. Create the live connection instance
        dg_connection = self.client.listen.live.v("1")

        # 2. Define event handlers
        def on_message(self, result, **kwargs):
            # Safe access using SDK objects (no manual dict parsing needed)
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return
            
            # Use is_final to distinguish between interim and final results
            if result.is_final:
                # In a real system, you might queue this differently
                self.final_result = sentence
            else:
                self.partial_result = sentence

        def on_error(self, error, **kwargs):
            print(f"Deepgram error: {error}")

        # 3. Register handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        # 4. Configure Options (Typed)
        options = LiveOptions(
            model="nova-2",      # or "nova-3" if available in your tier
            language="en-US",
            smart_format=True,
            interim_results=True,
            endpointing=300,     # milliseconds
            encoding="linear16", # Ensure this matches your audio input!
            sample_rate=16000    # Ensure this matches your audio input!
        )

        # 5. Start Connection
        # Note: start() creates a background thread for the WebSocket
        if dg_connection.start(options) is False:
            print("Failed to start Deepgram connection")
            return

        try:
            # 6. Send Audio Loop
            async for audio_chunk in audio_stream:
                # send() is thread-safe in v3
                dg_connection.send(audio_chunk)
                
                # Yield results if we captured any from the background thread
                if self.final_result:
                    yield self.final_result
                    self.final_result = None
                elif self.partial_result:
                    yield self.partial_result
                    self.partial_result = None
                
                # Yield control to event loop briefly
                await asyncio.sleep(0.01)

        except Exception as e:
            print(f"Stream error: {e}")
        finally:
            # 7. Cleanup
            dg_connection.finish()

    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio chunk (Prerecorded)"""
        try:
            # Wrap raw bytes in payload dict source
            payload = {"buffer": audio}
            
            # Define options
            options = PrerecordedOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
            )

            # v3 sync call (blocks, but usually fast for short buffers).
            # For heavy loads, run this in a thread executor.
            response = self.client.listen.prerecorded.v("1").transcribe_file(payload, options)
            
            # Access typed response
            if response.results.channels:
                return response.results.channels[0].alternatives[0].transcript
            return ""
            
        except Exception as e:
            print(f"Transcription error: {e}")
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
