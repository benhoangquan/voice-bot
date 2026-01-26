"""Test server for voice bot without Twilio transport layer"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import json

from .config import Config
from .adapters.stt import DeepgramAdapter
from .adapters.tts import ElevenLabsAdapter
from .adapters.llm import AnthropicAdapter
from .adapters.calendar import GoogleCalendarAdapter
from .rag.menu_rag import MenuRAG
from .guardrails.safety import Guardrails
from .transfer.queue import TransferQueue, StaffMember, StaffStatus
from .bot.voice_bot import VoiceBot

app = FastAPI(title="Voice Bot Test Server")

# Enable CORS for web testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
stt_adapter = None
tts_adapter = None
llm_adapter = None
calendar_adapter = None
menu_rag = None
guardrails = None
transfer_queue = None
active_sessions: Dict[str, VoiceBot] = {}


class TextInput(BaseModel):
    """Text input model for testing"""
    text: str
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response model"""
    response: str
    session_id: str
    tool_calls: Optional[list] = None


@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    global stt_adapter, tts_adapter, llm_adapter, calendar_adapter
    global menu_rag, guardrails, transfer_queue
    
    print("Initializing test server...")
    
    # Validate config (skip telephony requirements)
    required_vars = [
        ("DEEPGRAM_API_KEY", Config.DEEPGRAM_API_KEY),
        ("ELEVENLABS_API_KEY", Config.ELEVENLABS_API_KEY),
        ("ANTHROPIC_API_KEY", Config.ANTHROPIC_API_KEY),
    ]
    
    errors = []
    for var_name, var_value in required_vars:
        if not var_value:
            errors.append(f"Missing required environment variable: {var_name}")
    
    if errors:
        print(f"Configuration errors: {errors}")
        print("Note: Some features may not work without proper configuration")
    
    # Initialize adapters (STT and TTS are optional for text-only testing)
    if Config.DEEPGRAM_API_KEY:
        stt_adapter = DeepgramAdapter(Config.DEEPGRAM_API_KEY)
    else:
        print("Warning: DEEPGRAM_API_KEY not set, STT features disabled")
    
    if Config.ELEVENLABS_API_KEY:
        tts_adapter = ElevenLabsAdapter(Config.ELEVENLABS_API_KEY, Config.ELEVENLABS_VOICE_ID)
    else:
        print("Warning: ELEVENLABS_API_KEY not set, TTS features disabled")
    
    if Config.ANTHROPIC_API_KEY:
        llm_adapter = AnthropicAdapter(Config.ANTHROPIC_API_KEY, Config.ANTHROPIC_MODEL)
    else:
        raise Exception("ANTHROPIC_API_KEY is required")
    
    # Initialize Google Calendar adapter
    try:
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
            print("Warning: Google Calendar credentials not set, calendar features disabled")
            calendar_adapter = None
    except Exception as e:
        print(f"Warning: Failed to initialize Google Calendar: {e}")
        calendar_adapter = None
    
    # Initialize RAG
    menu_rag = MenuRAG(Config.CHROMA_DB_PATH)
    try:
        menu_rag.load_from_file(Config.MENU_DATA_PATH)
        print("Menu RAG database loaded")
    except FileNotFoundError:
        print(f"Warning: Menu data file not found: {Config.MENU_DATA_PATH}")
        print("Run 'python scripts/init_menu_data.py' to initialize menu data")
    
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
    
    print("Test server initialized successfully")


class MockTelephonyAdapter:
    """Mock telephony adapter for testing"""
    
    async def connect(self, call_sid: str):
        pass
    
    async def transfer(self, call_sid: str, target: str, context: Dict[str, Any]) -> bool:
        print(f"[MOCK] Transferring call {call_sid} to {target}")
        print(f"[MOCK] Context: {json.dumps(context, indent=2)}")
        return True
    
    async def hangup(self, call_sid: str) -> None:
        pass
    
    async def get_audio_stream(self, call_sid: str):
        async def empty_stream():
            while True:
                await asyncio.sleep(0.1)
                yield b""
        return empty_stream()


def get_or_create_bot(session_id: str) -> VoiceBot:
    """Get or create a voice bot instance for a session"""
    if session_id not in active_sessions:
        # Create mock telephony adapter
        mock_telephony = MockTelephonyAdapter()
        
        # Create voice bot instance
        bot = VoiceBot(
            transport=mock_telephony,
            stt_adapter=stt_adapter,
            tts_adapter=tts_adapter,
            llm_adapter=llm_adapter,
            calendar_adapter=calendar_adapter,
            menu_rag=menu_rag,
            guardrails=guardrails,
            transfer_queue=transfer_queue,
            call_sid=session_id,
            caller_id=f"test_user_{session_id}"
        )
        active_sessions[session_id] = bot
    
    return active_sessions[session_id]


@app.get("/")
async def root():
    """Root endpoint with test interface"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voice Bot Test Server</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 50px auto;
                padding: 20px;
            }
            .chat-container {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 20px;
                margin: 20px 0;
                min-height: 400px;
                background: #f9f9f9;
            }
            .message {
                margin: 10px 0;
                padding: 10px;
                border-radius: 5px;
            }
            .user-message {
                background: #007bff;
                color: white;
                text-align: right;
            }
            .bot-message {
                background: #e9ecef;
                color: #333;
            }
            input[type="text"] {
                width: 70%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                padding: 10px 20px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background: #0056b3;
            }
            .session-info {
                background: #e7f3ff;
                padding: 10px;
                border-radius: 4px;
                margin-bottom: 20px;
            }
        </style>
    </head>
    <body>
        <h1>Voice Bot Test Server</h1>
        <div class="session-info">
            <strong>Session ID:</strong> <span id="sessionId"></span>
            <button onclick="newSession()" style="margin-left: 20px;">New Session</button>
        </div>
        <div class="chat-container" id="chatContainer"></div>
        <div>
            <input type="text" id="userInput" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()">Send</button>
        </div>
        
        <script>
            let sessionId = 'test_' + Math.random().toString(36).substr(2, 9);
            document.getElementById('sessionId').textContent = sessionId;
            
            function newSession() {
                sessionId = 'test_' + Math.random().toString(36).substr(2, 9);
                document.getElementById('sessionId').textContent = sessionId;
                document.getElementById('chatContainer').innerHTML = '';
            }
            
            function handleKeyPress(event) {
                if (event.key === 'Enter') {
                    sendMessage();
                }
            }
            
            async function sendMessage() {
                const input = document.getElementById('userInput');
                const text = input.value.trim();
                if (!text) return;
                
                // Add user message to chat
                addMessage(text, 'user');
                input.value = '';
                
                try {
                    const response = await fetch('/api/chat', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            text: text,
                            session_id: sessionId
                        })
                    });
                    
                    const data = await response.json();
                    addMessage(data.response, 'bot');
                    
                    if (data.tool_calls) {
                        console.log('Tool calls:', data.tool_calls);
                    }
                } catch (error) {
                    addMessage('Error: ' + error.message, 'bot');
                }
            }
            
            function addMessage(text, type) {
                const container = document.getElementById('chatContainer');
                const message = document.createElement('div');
                message.className = 'message ' + (type === 'user' ? 'user-message' : 'bot-message');
                message.textContent = text;
                container.appendChild(message);
                container.scrollTop = container.scrollHeight;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/api/chat", response_model=SessionResponse)
async def chat_endpoint(input_data: TextInput):
    """Chat endpoint for text-based testing"""
    try:
        # Get or create bot for this session
        session_id = input_data.session_id or f"test_{asyncio.get_event_loop().time()}"
        bot = get_or_create_bot(session_id)
        
        # Process user input
        response_text = await bot.process_user_input(input_data.text)
        
        return SessionResponse(
            response=response_text,
            session_id=session_id,
            tool_calls=None  # Could extract from bot if needed
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    session_id = f"ws_{asyncio.get_event_loop().time()}"
    bot = get_or_create_bot(session_id)
    
    try:
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "message": "Connected to voice bot test server"
        })
        
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            if data.get("type") == "message":
                text = data.get("text", "")
                if text:
                    # Process message
                    response = await bot.process_user_input(text)
                    
                    # Send response
                    await websocket.send_json({
                        "type": "response",
                        "text": response,
                        "session_id": session_id
                    })
            
            elif data.get("type") == "close":
                break
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected: {session_id}")
        if session_id in active_sessions:
            del active_sessions[session_id]
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "stt": stt_adapter is not None,
            "tts": tts_adapter is not None,
            "llm": llm_adapter is not None,
            "calendar": calendar_adapter is not None,
            "rag": menu_rag is not None,
        },
        "active_sessions": len(active_sessions)
    }


@app.get("/api/sessions")
async def list_sessions():
    """List active sessions"""
    return {
        "sessions": list(active_sessions.keys()),
        "count": len(active_sessions)
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"status": "deleted", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn
    print("Starting Voice Bot Test Server...")
    print("Open http://localhost:8001 in your browser to test")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
