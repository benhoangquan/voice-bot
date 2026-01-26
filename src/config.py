"""Configuration management"""

import os
from dotenv import load_dotenv
from typing import Optional

load_dotenv()


class Config:
    """Application configuration"""
    
    # Telephony
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    
    # STT
    DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")
    
    # TTS
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    
    # LLM
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    # Calendar (Google Calendar)
    GOOGLE_CALENDAR_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_PATH", "")
    GOOGLE_CALENDAR_CREDENTIALS_JSON: str = os.getenv("GOOGLE_CALENDAR_CREDENTIALS_JSON", "")
    GOOGLE_CALENDAR_ID: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    GOOGLE_CALENDAR_TOKEN_PATH: str = os.getenv("GOOGLE_CALENDAR_TOKEN_PATH", "")
    
    # RAG
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    MENU_DATA_PATH: str = os.getenv("MENU_DATA_PATH", "./data/sample_menu.json")
    
    # VAD
    VAD_SENSITIVITY: float = float(os.getenv("VAD_SENSITIVITY", "0.5"))
    
    # Daily
    DAILY_SAMPLE_ROOM_URL: str = os.getenv("DAILY_SAMPLE_ROOM_URL", "")
    DAILY_TOKEN: str = os.getenv("DAILY_TOKEN", "") # Token for joining the room (if private)
    DAILY_API_KEY: str = os.getenv("DAILY_API_KEY", "") # Optional, if you want to generate tokens
    
    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
    
    @classmethod
    def validate(cls) -> tuple[bool, list[str]]:
        """Validate required configuration"""
        errors = []
        
        required_vars = [
            ("TWILIO_ACCOUNT_SID", cls.TWILIO_ACCOUNT_SID),
            ("TWILIO_AUTH_TOKEN", cls.TWILIO_AUTH_TOKEN),
            ("DEEPGRAM_API_KEY", cls.DEEPGRAM_API_KEY),
            ("ELEVENLABS_API_KEY", cls.ELEVENLABS_API_KEY),
            ("ANTHROPIC_API_KEY", cls.ANTHROPIC_API_KEY),
            ("DAILY_SAMPLE_ROOM_URL", cls.DAILY_SAMPLE_ROOM_URL), 
        ]
        
        for var_name, var_value in required_vars:
            if not var_value:
                errors.append(f"Missing required environment variable: {var_name}")
        
        return len(errors) == 0, errors
