"""Test server for voice bot with local microphone and speaker"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import json
import signal
import sys

from .config import Config
from .adapters.stt import DeepgramAdapter
from .adapters.tts import ElevenLabsAdapter
from .adapters.llm import AnthropicAdapter
from .adapters.calendar import GoogleCalendarAdapter
from .adapters.local_audio import LocalAudioTransport
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
voice_bot_task: Optional[asyncio.Task] = None
voice_bot: Optional[VoiceBot] = None


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


def create_voice_bot() -> VoiceBot:
    """Create a voice bot instance with local audio transport"""
    # Create local audio transport
    local_audio = LocalAudioTransport()
    
    # Create voice bot instance
    bot = VoiceBot(
        transport=local_audio,
        stt_adapter=stt_adapter,
        tts_adapter=tts_adapter,
        llm_adapter=llm_adapter,
        calendar_adapter=calendar_adapter,
        menu_rag=menu_rag,
        guardrails=guardrails,
        transfer_queue=transfer_queue,
        call_sid="local_audio_session",
        caller_id="local_user"
    )
    
    return bot


@app.get("/")
async def root():
    """Root endpoint with voice conversation UI"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Voice Bot Test Server</title>
        <style>
            * {
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 {
                margin: 0 0 10px 0;
                color: #333;
                font-size: 28px;
            }
            .subtitle {
                color: #666;
                margin-bottom: 30px;
                font-size: 14px;
            }
            .status-card {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                text-align: center;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
                background: #dc3545;
                animation: pulse 2s infinite;
            }
            .status-indicator.active {
                background: #28a745;
            }
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            .status-text {
                font-weight: 600;
                color: #333;
                font-size: 16px;
            }
            .status-message {
                color: #666;
                font-size: 14px;
                margin-top: 5px;
            }
            .button-container {
                text-align: center;
                margin-bottom: 20px;
            }
            button {
                padding: 14px 40px;
                font-size: 16px;
                font-weight: 600;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s;
                min-width: 150px;
            }
            .btn-start {
                background: #007bff;
                color: white;
            }
            .btn-start:hover:not(:disabled) {
                background: #0056b3;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(0,123,255,0.3);
            }
            .btn-stop {
                background: #dc3545;
                color: white;
            }
            .btn-stop:hover:not(:disabled) {
                background: #c82333;
                transform: translateY(-1px);
                box-shadow: 0 4px 12px rgba(220,53,69,0.3);
            }
            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .info-box {
                background: #e7f3ff;
                border-left: 4px solid #007bff;
                padding: 15px;
                border-radius: 4px;
                margin-top: 20px;
                font-size: 14px;
                color: #004085;
            }
            .info-box ul {
                margin: 10px 0 0 0;
                padding-left: 20px;
            }
            .info-box li {
                margin: 5px 0;
            }
            .log-container {
                margin-top: 20px;
                max-height: 200px;
                overflow-y: auto;
                background: #f8f9fa;
                border-radius: 6px;
                padding: 15px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                color: #333;
            }
            .log-entry {
                margin: 5px 0;
                padding: 5px;
            }
            .log-entry.success {
                color: #28a745;
            }
            .log-entry.error {
                color: #dc3545;
            }
            .log-entry.info {
                color: #007bff;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎤 Voice Bot</h1>
            <div class="subtitle">Start a conversation using your microphone and speaker</div>
            
            <div class="status-card">
                <div>
                    <span class="status-indicator" id="statusIndicator"></span>
                    <span class="status-text" id="statusText">Stopped</span>
                </div>
                <div class="status-message" id="statusMessage">Ready to start conversation</div>
            </div>
            
            <div class="button-container">
                <button id="startBtn" class="btn-start" onclick="startConversation()">Start Conversation</button>
                <button id="stopBtn" class="btn-stop" onclick="stopConversation()" style="display: none;">Stop Conversation</button>
            </div>
            
            <div class="info-box">
                <strong>How to use:</strong>
                <ul>
                    <li>Click "Start Conversation" to begin</li>
                    <li>Speak into your microphone - the bot will listen</li>
                    <li>The bot will respond through your speakers</li>
                    <li>Click "Stop Conversation" when done</li>
                </ul>
            </div>
            
            <div class="log-container" id="logContainer"></div>
        </div>
        
        <script>
            let statusCheckInterval = null;
            
            // Check status on page load
            window.addEventListener('load', () => {
                checkStatus();
                // Poll status every 2 seconds
                statusCheckInterval = setInterval(checkStatus, 2000);
            });
            
            window.addEventListener('beforeunload', () => {
                if (statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                }
            });
            
            async function checkStatus() {
                try {
                    const response = await fetch('/api/voice/status');
                    const data = await response.json();
                    updateUI(data.status === 'running', data.message);
                } catch (error) {
                    console.error('Error checking status:', error);
                }
            }
            
            function updateUI(isRunning, message) {
                const indicator = document.getElementById('statusIndicator');
                const statusText = document.getElementById('statusText');
                const statusMessage = document.getElementById('statusMessage');
                const startBtn = document.getElementById('startBtn');
                const stopBtn = document.getElementById('stopBtn');
                
                if (isRunning) {
                    indicator.classList.add('active');
                    statusText.textContent = 'Active';
                    statusMessage.textContent = message || 'Conversation is running';
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'inline-block';
                } else {
                    indicator.classList.remove('active');
                    statusText.textContent = 'Stopped';
                    statusMessage.textContent = message || 'Ready to start conversation';
                    startBtn.style.display = 'inline-block';
                    stopBtn.style.display = 'none';
                }
            }
            
            function addLog(message, type = 'info') {
                const logContainer = document.getElementById('logContainer');
                const entry = document.createElement('div');
                entry.className = `log-entry ${type}`;
                const timestamp = new Date().toLocaleTimeString();
                entry.textContent = `[${timestamp}] ${message}`;
                logContainer.appendChild(entry);
                logContainer.scrollTop = logContainer.scrollHeight;
            }
            
            async function startConversation() {
                const startBtn = document.getElementById('startBtn');
                startBtn.disabled = true;
                addLog('Starting voice conversation...', 'info');
                
                try {
                    const response = await fetch('/api/voice/start', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        addLog(data.message, 'success');
                        updateUI(true, data.message);
                    } else {
                        addLog(`Error: ${data.detail || data.message}`, 'error');
                    }
                } catch (error) {
                    addLog(`Error: ${error.message}`, 'error');
                } finally {
                    startBtn.disabled = false;
                }
            }
            
            async function stopConversation() {
                const stopBtn = document.getElementById('stopBtn');
                stopBtn.disabled = true;
                addLog('Stopping voice conversation...', 'info');
                
                try {
                    const response = await fetch('/api/voice/stop', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        addLog(data.message, 'success');
                        updateUI(false, data.message);
                    } else {
                        addLog(`Error: ${data.detail || data.message}`, 'error');
                    }
                } catch (error) {
                    addLog(`Error: ${error.message}`, 'error');
                } finally {
                    stopBtn.disabled = false;
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/api/chat", response_model=SessionResponse)
async def chat_endpoint(input_data: TextInput):
    """Chat endpoint for text-based testing (Note: VoiceBot doesn't support text input directly)"""
    try:
        # Note: VoiceBot is designed for audio input/output via Pipecat pipeline
        # This endpoint is kept for compatibility but doesn't work with the current VoiceBot implementation
        # Use /api/voice/start to start a voice conversation instead
        
        return SessionResponse(
            response="Text-based chat is not supported. Please use /api/voice/start to start a voice conversation.",
            session_id=input_data.session_id or "text_session",
            tool_calls=None
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint (Note: VoiceBot doesn't support text input directly)"""
    await websocket.accept()
    
    try:
        await websocket.send_json({
            "type": "error",
            "message": "Text-based WebSocket chat is not supported. Use /api/voice/start to start a voice conversation."
        })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
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


@app.post("/api/voice/start")
async def start_voice_conversation():
    """Start a voice conversation using microphone and speaker"""
    global voice_bot_task, voice_bot
    
    if voice_bot_task and not voice_bot_task.done():
        return {"status": "already_running", "message": "Voice conversation is already running"}
    
    try:
        print("[VOICE] Creating voice bot with local audio transport...")
        # Create voice bot with local audio transport
        voice_bot = create_voice_bot()
        print("[VOICE] Voice bot created successfully")
        
        # Start the bot in a background task with error handling
        async def run_bot_with_error_handling():
            try:
                print("[VOICE] Starting pipeline...")
                await voice_bot.run()
                print("[VOICE] Pipeline completed")
            except asyncio.CancelledError:
                print("[VOICE] Pipeline cancelled")
                raise
            except Exception as e:
                print(f"[VOICE] ERROR in pipeline: {e}")
                import traceback
                traceback.print_exc()
                # Cleanup on error
                if voice_bot and hasattr(voice_bot, 'transport'):
                    try:
                        if asyncio.iscoroutinefunction(voice_bot.transport.cleanup):
                            await voice_bot.transport.cleanup()
                        else:
                            voice_bot.transport.cleanup()
                    except Exception as cleanup_error:
                        print(f"[VOICE] Cleanup error: {cleanup_error}")
        
        voice_bot_task = asyncio.create_task(run_bot_with_error_handling())
        print("[VOICE] Background task created")
        
        # Give it a moment to start, then check if it errored immediately
        await asyncio.sleep(0.5)
        if voice_bot_task.done():
            try:
                await voice_bot_task
            except Exception as e:
                print(f"[VOICE] Task failed immediately: {e}")
                raise HTTPException(status_code=500, detail=f"Pipeline failed to start: {str(e)}")
        
        return {
            "status": "started",
            "message": "Voice conversation started. Speak into your microphone!"
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[VOICE] Failed to start voice conversation: {error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to start voice conversation: {str(e)}")


@app.post("/api/voice/stop")
async def stop_voice_conversation():
    """Stop the voice conversation"""
    global voice_bot_task, voice_bot
    
    if not voice_bot_task or voice_bot_task.done():
        return {"status": "not_running", "message": "No voice conversation is running"}
    
    try:
        # Cancel the bot task
        voice_bot_task.cancel()
        
        # Cleanup audio resources
        if voice_bot and hasattr(voice_bot, 'transport'):
            try:
                if asyncio.iscoroutinefunction(voice_bot.transport.cleanup):
                    await voice_bot.transport.cleanup()
                else:
                    voice_bot.transport.cleanup()
            except Exception as cleanup_error:
                print(f"[VOICE] Cleanup error: {cleanup_error}")
        
        voice_bot_task = None
        voice_bot = None
        
        return {
            "status": "stopped",
            "message": "Voice conversation stopped"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop voice conversation: {str(e)}")


@app.get("/api/voice/status")
async def voice_status():
    """Get the status of the voice conversation"""
    global voice_bot_task
    
    if voice_bot_task:
        if voice_bot_task.done():
            # Check if it completed with an error
            try:
                await voice_bot_task
                return {"status": "stopped", "message": "Voice conversation completed"}
            except Exception as e:
                return {"status": "error", "message": f"Voice conversation error: {str(e)}"}
        else:
            return {"status": "running", "message": "Voice conversation is active"}
    else:
        return {"status": "stopped", "message": "No voice conversation is running"}


@app.get("/api/audio/devices")
async def list_audio_devices():
    """List available audio input and output devices"""
    try:
        devices = LocalAudioTransport.list_audio_devices()
        return {"devices": devices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list audio devices: {str(e)}")


@app.get("/api/voice/debug")
async def voice_debug():
    """Debug information about the voice conversation"""
    global voice_bot_task, voice_bot
    
    debug_info = {
        "task_running": voice_bot_task is not None and not voice_bot_task.done(),
        "task_done": voice_bot_task is not None and voice_bot_task.done(),
        "bot_exists": voice_bot is not None,
    }
    
    if voice_bot_task and voice_bot_task.done():
        try:
            await voice_bot_task
            debug_info["task_result"] = "completed"
        except Exception as e:
            debug_info["task_error"] = str(e)
            debug_info["task_result"] = "error"
    
    if voice_bot:
        debug_info["transport_exists"] = hasattr(voice_bot, 'transport')
        if hasattr(voice_bot, 'transport'):
            debug_info["transport_type"] = type(voice_bot.transport).__name__
    
    return debug_info


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id in active_sessions:
        del active_sessions[session_id]
        return {"status": "deleted", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    global voice_bot_task, voice_bot
    
    if voice_bot_task and not voice_bot_task.done():
        voice_bot_task.cancel()
        try:
            await voice_bot_task
        except asyncio.CancelledError:
            pass
    
    if voice_bot and hasattr(voice_bot, 'transport'):
        voice_bot.transport.cleanup()


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("\nShutting down...")
    sys.exit(0)


if __name__ == "__main__":
    import uvicorn
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting Voice Bot Test Server...")
    print("=" * 60)
    print("Voice Conversation Endpoints:")
    print("  POST /api/voice/start  - Start voice conversation")
    print("  POST /api/voice/stop   - Stop voice conversation")
    print("  GET  /api/voice/status - Check conversation status")
    print("  GET  /api/audio/devices - List audio devices")
    print("=" * 60)
    print("\nOpen http://localhost:8001 in your browser for API documentation")
    print("Use POST /api/voice/start to begin a voice conversation\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
