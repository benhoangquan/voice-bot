"""Main entry point for voice bot application"""

import asyncio
from src.server import app
from src.config import Config
import uvicorn


def main():
    """Run the voice bot server"""
    print("Starting Voice Bot Server...")
    print(f"Server will run on {Config.SERVER_HOST}:{Config.SERVER_PORT}")
    print("\nMake sure to:")
    print("1. Set up your .env file with API keys")
    print("2. Configure Twilio webhook URL to point to /voice/incoming")
    print("3. Ensure menu data is loaded in RAG database")
    
    uvicorn.run(
        app,
        host=Config.SERVER_HOST,
        port=Config.SERVER_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()
