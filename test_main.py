"""Test server entry point"""

from src.test_server import app
from src.config import Config
import uvicorn


def main():
    """Run the test server"""
    print("=" * 60)
    print("Voice Bot Test Server")
    print("=" * 60)
    print(f"\nServer will run on {Config.SERVER_HOST}:8001")
    print("\nOpen http://localhost:8001 in your browser to test")
    print("\nEndpoints:")
    print("  - GET  /              - Web interface for testing")
    print("  - POST /api/chat      - Text-based chat API")
    print("  - WS   /ws/chat       - WebSocket for real-time chat")
    print("  - GET  /api/health    - Health check")
    print("  - GET  /api/sessions  - List active sessions")
    print("\nMake sure to:")
    print("  1. Set up your .env file with API keys")
    print("  2. Run 'python scripts/init_menu_data.py' to initialize menu data")
    print("  3. Configure Google Calendar credentials (optional)")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host=Config.SERVER_HOST,
        port=8001,  # Different port from main server
        log_level="info"
    )


if __name__ == "__main__":
    main()
