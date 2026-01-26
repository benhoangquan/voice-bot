import time
import asyncio
import aiohttp
import os

# Pipecat Imports
from pipecat.transports.daily.transport import DailyTransport, DailyParams
from pipecat.transports.daily.utils import (
    DailyRESTHelper, 
    DailyMeetingTokenParams, 
    DailyMeetingTokenProperties
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

# Your Custom Imports
from .config import Config
from .bot.voice_bot import VoiceBot
# Adapters (Custom adapters removed as they are replaced by Pipecat services in VoiceBot)
from .adapters.calendar import GoogleCalendarAdapter
from .rag.menu_rag import MenuRAG
from .guardrails.safety import Guardrails
from .transfer.queue import TransferQueue, StaffMember, StaffStatus

async def wait_for_user(session, room_url, api_key):
    """Polls the Daily API until a user joins the room."""
    print(f"⏳ Waiting for users to join {room_url}...")
    
    # Extract room name from URL (e.g., https://domain.daily.co/room-name -> room-name)
    room_name = room_url.split("/")[-1]
    url = f"https://api.daily.co/v1/rooms/{room_name}/presence"
    headers = {"Authorization": f"Bearer {api_key}"}

    while True:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    # data is a dict of participants e.g. { "session_id": {...}, ... }
                    # If count > 0, someone is in the room
                    if len(data) > 0:
                        print(f"👤 User detected! (Count: {len(data)}) Launching bot...")
                        return
                else:
                    # Ignore errors (room might not be active or other transient issues)
                    pass
        except Exception as e:
            # Ignore network errors
            pass
        
        await asyncio.sleep(2)  # Check every 2 seconds

async def main():
    print("🚀 Initializing Voice Bot (Daily.co Mode)...")

    # Validate Config
    valid, errors = Config.validate()
    if not valid:
        print("❌ Configuration Error:")
        for error in errors:
            print(f"  - {error}")
        # Continue if only Daily is missing (since we might be just testing imports)
        if not Config.DAILY_SAMPLE_ROOM_URL:
             print("❌ Missing DAILY_SAMPLE_ROOM_URL in .env")
             return

    # 1. Initialize RAG
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    try:
        menu_rag.load_from_file(Config.MENU_DATA_PATH)
        print("✅ Menu RAG loaded")
    except Exception:
        print("⚠️ Menu data not found. RAG will be empty.")

    # 2. Initialize Shared Logic
    guardrails = Guardrails()
    transfer_queue = TransferQueue()
    
    # 3. Add Dummy Staff
    transfer_queue.add_staff(StaffMember("staff_1", "Sarah", "+1234567890", StaffStatus.AVAILABLE))
    
    # 4. Configure Transport (Daily.co)
    print(f"Connecting to Daily room: {Config.DAILY_SAMPLE_ROOM_URL}")
    
    # Token handlin
    
    async with aiohttp.ClientSession() as session:
        helper = DailyRESTHelper(
            daily_api_key=Config.DAILY_API_KEY,
            daily_api_url="https://api.daily.co/v1",
            aiohttp_session=session
        )

        # Wait for user to join the room
        await wait_for_user(session, Config.DAILY_SAMPLE_ROOM_URL, Config.DAILY_API_KEY)

        # Calculate expiration (e.g., 1 hour from now)
        # The guide recommends "exp" to secure the token
        expiration = int(time.time() + 3600)

        # Create params matching the guide's "properties" object
        # https://docs.daily.co/reference/rest-api/meeting-tokens/create-meeting-token
        params = DailyMeetingTokenParams(
            properties=DailyMeetingTokenProperties(
                room_name="voice-bot-test", # Optional: limits token to specific room
                is_owner=True,            # Grants admin privileges (broadcasting, etc.)
                exp=expiration,           # Token expiry timestamp
                user_name="Restaurant Bot",
            )
        )

        try:
            # We pass the full params object instead of just the URL
            token = await helper.get_token(
                room_url=Config.DAILY_SAMPLE_ROOM_URL, 
                params=params
            )
            print(f"✅ Generated Token: {token}")
        except Exception as e:
            print(f"⚠️ Failed to generate token: {e}")
    
        transport = DailyTransport(
            room_url=Config.DAILY_SAMPLE_ROOM_URL,
            token=token,
            bot_name="Restaurant Bot",
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                camera_out_enabled=False,
                transcription_enabled=False,
            )
        )
        
        calendar_adapter = GoogleCalendarAdapter(
            credentials_path=Config.GOOGLE_CALENDAR_CREDENTIALS_PATH,
            calendar_id=Config.GOOGLE_CALENDAR_ID
        )
        stt_service = DeepgramSTTService(api_key=Config.DEEPGRAM_API_KEY, audio_passthrough=True)
        tts_service = ElevenLabsTTSService(api_key=Config.ELEVENLABS_API_KEY, voice_id=Config.ELEVENLABS_VOICE_ID)
        llm_service = AnthropicLLMService(
            api_key=Config.ANTHROPIC_API_KEY, 
            model=Config.ANTHROPIC_MODEL,
        )

        # 6. Instantiate Bot
        bot = VoiceBot(
            transport=transport,
            stt_service=stt_service,
            tts_service=tts_service,
            llm_service=llm_service,
            calendar_adapter=calendar_adapter,
            menu_rag=menu_rag,
            guardrails=guardrails,
            transfer_queue=transfer_queue,
            call_sid="daily_session",
            caller_id="daily_user"
        )

        # 7. Run Pipeline
        try:
            await bot.run()
        except KeyboardInterrupt:
            print("Session ended by user")
        except Exception as e:
            print(f"Session ended with error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
