"""Telephony adapter implementations"""

import asyncio
from typing import AsyncIterator, Dict, Any
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse
import websockets
import json

from .base import TelephonyAdapter, AudioStream


class TwilioAdapter(TelephonyAdapter):
    """Twilio Voice API adapter"""
    
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.client = TwilioClient(account_sid, auth_token)
        self.phone_number = phone_number
        self.active_calls: Dict[str, Any] = {}
    
    async def connect(self, call_sid: str) -> AudioStream:
        """Connect to Twilio call via WebSocket"""
        # Twilio Media Streams uses WebSocket
        # This is a simplified version - actual implementation would connect to Twilio's media streams
        stream = AudioStream()
        self.active_calls[call_sid] = {"stream": stream, "status": "connected"}
        return stream
    
    async def transfer(self, call_sid: str, target: str, context: Dict[str, Any]) -> bool:
        """Transfer call using Twilio"""
        try:
            call = self.client.calls(call_sid)
            
            # Create TwiML for transfer with context
            response = VoiceResponse()
            response.say(f"Transferring you to {target}. Please hold.")
            
            # Transfer with context passed via headers or status callback
            call.update(
                twiml=str(response),
                status_callback=f"/transfer_callback?context={json.dumps(context)}"
            )
            
            return True
        except Exception as e:
            print(f"Transfer failed: {e}")
            return False
    
    async def hangup(self, call_sid: str) -> None:
        """Hang up the call"""
        try:
            call = self.client.calls(call_sid)
            call.update(status="completed")
            if call_sid in self.active_calls:
                del self.active_calls[call_sid]
        except Exception as e:
            print(f"Hangup failed: {e}")
    
    async def get_audio_stream(self, call_sid: str) -> AsyncIterator[bytes]:
        """Get audio stream from Twilio Media Streams"""
        # This would connect to Twilio's Media Streams WebSocket
        # For now, return empty iterator as placeholder
        # Actual implementation would yield audio chunks from WebSocket
        while True:
            await asyncio.sleep(0.1)
            yield b""


class AsteriskAdapter(TelephonyAdapter):
    """Asterisk ARI adapter (future implementation)"""
    
    def __init__(self, ari_url: str, username: str, password: str):
        self.ari_url = ari_url
        self.username = username
        self.password = password
        self.active_calls: Dict[str, Any] = {}
    
    async def connect(self, call_sid: str) -> AudioStream:
        """Connect to Asterisk call via ARI"""
        # TODO: Implement Asterisk ARI connection
        stream = AudioStream()
        self.active_calls[call_sid] = {"stream": stream, "status": "connected"}
        return stream
    
    async def transfer(self, call_sid: str, target: str, context: Dict[str, Any]) -> bool:
        """Transfer call using Asterisk ARI"""
        # TODO: Implement Asterisk transfer
        return False
    
    async def hangup(self, call_sid: str) -> None:
        """Hang up the call"""
        # TODO: Implement Asterisk hangup
        if call_sid in self.active_calls:
            del self.active_calls[call_sid]
    
    async def get_audio_stream(self, call_sid: str) -> AsyncIterator[bytes]:
        """Get audio stream from Asterisk"""
        # TODO: Implement Asterisk audio stream
        while True:
            await asyncio.sleep(0.1)
            yield b""
