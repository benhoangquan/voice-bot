"""Web server for handling Twilio webhooks and call management"""

from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
import asyncio
from typing import Dict

from .config import Config
from .adapters.telephony import TwilioAdapter
from .adapters.stt import DeepgramAdapter
from .adapters.tts import ElevenLabsAdapter
from .adapters.llm import AnthropicAdapter
from .adapters.calendar import GoogleCalendarAdapter
from .rag.menu_rag import MenuRAG
from .guardrails.safety import Guardrails
from .transfer.queue import TransferQueue, StaffMember, StaffStatus
from .bot.voice_bot import VoiceBot

app = FastAPI()

# Global instances
telephony_adapter = None
stt_adapter = None
tts_adapter = None
llm_adapter = None
calendar_adapter = None
menu_rag = None
guardrails = None
transfer_queue = None
active_bots: Dict[str, VoiceBot] = {}


@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    global telephony_adapter, stt_adapter, tts_adapter, llm_adapter
    global calendar_adapter, menu_rag, guardrails, transfer_queue
    
    # Validate config
    is_valid, errors = Config.validate()
    if not is_valid:
        print(f"Configuration errors: {errors}")
        raise Exception("Invalid configuration")
    
    # Initialize adapters
    telephony_adapter = TwilioAdapter(
        Config.TWILIO_ACCOUNT_SID,
        Config.TWILIO_AUTH_TOKEN,
        Config.TWILIO_PHONE_NUMBER
    )
    
    stt_adapter = DeepgramAdapter(Config.DEEPGRAM_API_KEY)
    tts_adapter = ElevenLabsAdapter(Config.ELEVENLABS_API_KEY, Config.ELEVENLABS_VOICE_ID)
    llm_adapter = AnthropicAdapter(Config.ANTHROPIC_API_KEY, Config.ANTHROPIC_MODEL)
    # Initialize Google Calendar adapter
    # Try credentials JSON first, then credentials path, then token path
    if Config.GOOGLE_CALENDAR_CREDENTIALS_JSON:
        calendar_adapter = GoogleCalendarAdapter(
            credentials_json=Config.GOOGLE_CALENDAR_CREDENTIALS_JSON,
            calendar_id=Config.GOOGLE_CALENDAR_ID
        )
    elif Config.GOOGLE_CALENDAR_CREDENTIALS_PATH:
        calendar_adapter = GoogleCalendarAdapter(
            credentials_path=Config.GOOGLE_CALENDAR_CREDENTIALS_PATH,
            calendar_id=Config.GOOGLE_CALENDAR_ID
        )
    elif Config.GOOGLE_CALENDAR_TOKEN_PATH:
        calendar_adapter = GoogleCalendarAdapter(
            token_path=Config.GOOGLE_CALENDAR_TOKEN_PATH,
            calendar_id=Config.GOOGLE_CALENDAR_ID
        )
    else:
        raise Exception(
            "Must provide GOOGLE_CALENDAR_CREDENTIALS_JSON, "
            "GOOGLE_CALENDAR_CREDENTIALS_PATH, or GOOGLE_CALENDAR_TOKEN_PATH"
        )
    
    # Initialize RAG
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    
    # Load menu data if available
    try:
        menu_rag.load_from_file(Config.MENU_DATA_PATH)
    except FileNotFoundError:
        print(f"Menu data file not found: {Config.MENU_DATA_PATH}")
        print("Please create menu data file or run data generation script")
    
    # Initialize guardrails
    guardrails = Guardrails()
    
    # Initialize transfer queue
    transfer_queue = TransferQueue()
    
    # Add sample staff members
    staff1 = StaffMember(
        id="staff_1",
        name="Sarah",
        phone="+1234567890",
        status=StaffStatus.AVAILABLE
    )
    staff2 = StaffMember(
        id="staff_2",
        name="Mike",
        phone="+1234567891",
        status=StaffStatus.AVAILABLE
    )
    transfer_queue.add_staff(staff1)
    transfer_queue.add_staff(staff2)
    
    print("Voice bot server started")


@app.post("/voice/incoming")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio call"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    caller_id = form_data.get("From", "")
    
    # Check guardrails
    if guardrails.check_blocked(caller_id):
        response = VoiceResponse()
        response.say("Your call cannot be completed at this time.")
        response.hangup()
        return PlainTextResponse(str(response), media_type="application/xml")
    
    if not guardrails.check_rate_limit(caller_id):
        response = VoiceResponse()
        response.say("You have exceeded the maximum number of calls. Please try again later.")
        response.hangup()
        return PlainTextResponse(str(response), media_type="application/xml")
    
    # Create voice bot instance for this call
    voice_bot = VoiceBot(
        telephony_adapter=telephony_adapter,
        stt_adapter=stt_adapter,
        tts_adapter=tts_adapter,
        llm_adapter=llm_adapter,
        calendar_adapter=calendar_adapter,
        menu_rag=menu_rag,
        guardrails=guardrails,
        transfer_queue=transfer_queue,
        call_sid=call_sid,
        caller_id=caller_id
    )
    
    active_bots[call_sid] = voice_bot
    
    # Create TwiML response with Media Stream
    response = VoiceResponse()
    response.say("Hello! Welcome to our restaurant. How can I help you today?")
    
    # Start Media Stream for real-time audio
    start = Start()
    stream = Stream(url=f"wss://{request.url.hostname}/media/stream")
    start.stream(stream)
    response.append(start)
    
    return PlainTextResponse(str(response), media_type="application/xml")


@app.post("/media/stream")
async def handle_media_stream(request: Request):
    """Handle WebSocket media stream from Twilio"""
    # This would handle the WebSocket connection for real-time audio
    # Implementation would integrate with Pipecat pipeline
    pass


@app.post("/voice/status")
async def handle_call_status(request: Request):
    """Handle call status updates"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    
    if call_status == "completed" and call_sid in active_bots:
        # Clean up bot instance
        del active_bots[call_sid]
    
    return PlainTextResponse("OK")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.SERVER_HOST, port=Config.SERVER_PORT)
