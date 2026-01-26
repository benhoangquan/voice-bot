"""Test server entry point for local microphone/speaker voice conversations"""

from src.test_server import app
from src.config import Config
import uvicorn


def main():
    """Run the test server with local audio support"""
    print("=" * 60)
    print("Voice Bot Test Server (Local Audio)")
    print("=" * 60)
    print(f"\nServer will run on {Config.SERVER_HOST}:8001")
    print("\nOpen http://localhost:8001 in your browser for API documentation")
    print("\nVoice Conversation Endpoints:")
    print("  - POST /api/voice/start   - Start voice conversation (microphone/speaker)")
    print("  - POST /api/voice/stop    - Stop voice conversation")
    print("  - GET  /api/voice/status  - Check conversation status")
    print("  - GET  /api/audio/devices  - List available audio devices")
    print("\nOther Endpoints:")
    print("  - GET  /api/health        - Health check")
    print("  - GET  /api/sessions      - List active sessions")
    print("\nMake sure to:")
    print("  1. Set up your .env file with API keys (DEEPGRAM_API_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY)")
    print("  2. Run 'python scripts/init_menu_data.py' to initialize menu data")
    print("  3. Configure Google Calendar credentials (optional)")
    print("  4. On macOS, install PortAudio: brew install portaudio")
    print("\nTo start a voice conversation:")
    print("  curl -X POST http://localhost:8001/api/voice/start")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=Config.SERVER_HOST,
        port=8001,  # Different port from main server
        log_level="info"
    )


if __name__ == "__main__":
    main()
