# test_server.py
import asyncio
import aiohttp
import time
from loguru import logger

# Pipecat Transport & VAD
from pipecat.transports.daily.transport import DailyTransport, DailyParams
from pipecat.transports.daily.utils import (
    DailyRESTHelper, 
    DailyMeetingTokenParams, 
    DailyMeetingTokenProperties
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

# Services
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

# Custom Imports
from .config import Config
from .bot.voice_bot import VoiceBot
from .adapters.calendar import GoogleCalendarAdapter
from .rag.menu_rag import MenuRAG
from .guardrails.safety import Guardrails
from .transfer.queue import TransferQueue, StaffMember, StaffStatus

async def main():
    logger.info("🚀 Initializing Voice Bot (Modern Pipecat Stack)...")

    # Validate Config
    valid, errors = Config.validate()
    if not valid:
        logger.error(f"Config Errors: {errors}")
        return

    # 1. Initialize Data Layers
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    try:
        menu_rag.load_from_file(Config.MENU_DATA_PATH)
        logger.info("✅ Menu RAG loaded")
    except Exception:
        logger.warning("⚠️ Menu data not found. RAG will be empty.")

    guardrails = Guardrails()
    transfer_queue = TransferQueue()
    transfer_queue.add_staff(StaffMember("staff_1", "Sarah", "+1234567890", StaffStatus.AVAILABLE))

    # 2. Token Generation (Preserving your custom logic)
    async with aiohttp.ClientSession() as session:
        helper = DailyRESTHelper(
            daily_api_key=Config.DAILY_API_KEY,
            daily_api_url="https://api.daily.co/v1",
            aiohttp_session=session
        )
        
        # Note: We NO LONGER wait_for_user here. The Runner handles waiting.
        
        expiration = int(time.time() + 3600)
        params = DailyMeetingTokenParams(
            properties=DailyMeetingTokenProperties(
                room_name="voice-bot-test", 
                is_owner=True,            
                exp=expiration,          
                user_name="Restaurant Bot",
            )
        )

        try:
            token = await helper.get_token(
                room_url=Config.DAILY_SAMPLE_ROOM_URL, 
                params=params
            )
            logger.info(f"✅ Generated Token: {token}")
        except Exception as e:
            logger.error(f"Failed to generate token: {e}")
            return

        # 3. Configure Transport with Silero VAD (Crucial for good interruption)
        transport = DailyTransport(
            room_url=Config.DAILY_SAMPLE_ROOM_URL,
            token=token,
            bot_name="Restaurant Bot",
            params=DailyParams(
                audio_out_enabled=True,
                audio_in_enabled=True,
                camera_out_enabled=False,
                transcription_enabled=False,
                # Add VAD to filter background noise
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            )
        )

        # 4. Initialize Services
        stt = DeepgramSTTService(api_key=Config.DEEPGRAM_API_KEY)
        tts = ElevenLabsTTSService(api_key=Config.ELEVENLABS_API_KEY, voice_id=Config.ELEVENLABS_VOICE_ID)
        llm = AnthropicLLMService(api_key=Config.ANTHROPIC_API_KEY, model=Config.ANTHROPIC_MODEL)

        # 5. Instantiate Bot
        # We pass dependencies, but we don't pass transport yet
        bot = VoiceBot(
            stt_service=stt,
            tts_service=tts,
            llm_service=llm,
            calendar_adapter=GoogleCalendarAdapter(
                credentials_path=Config.GOOGLE_CALENDAR_CREDENTIALS_PATH,
                calendar_id=Config.GOOGLE_CALENDAR_ID
            ),
            menu_rag=menu_rag,
            guardrails=guardrails,
            transfer_queue=transfer_queue,
            call_sid="daily_session",
            caller_id="daily_user"
        )

        # 6. Run the Bot
        # This will block until the session ends or Ctrl+C
        try:
            await bot.run(transport, handle_sigint=True)
        except Exception as e:
            logger.exception(f"Bot execution failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())