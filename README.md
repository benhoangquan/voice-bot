# Voice Restaurant Bot

A real-time voice telephone chatbot system for restaurant reservations with menu queries, calendar booking, staff transfers, guardrails, and barge-in handling.

## Features

- **Voice Telephone Interface**: Handle incoming calls via Twilio
- **Real-time STT/TTS**: Streaming speech recognition and synthesis
- **LLM with Tool Calling**: Intelligent conversation with function calling
- **Menu RAG System**: Query menu items using vector search
- **Reservation Booking**: Create reservations via Yelp API
- **Queue-based Staff Transfer**: Transfer customers to human staff
- **Guardrails**: Rate limiting, validation, and abuse detection
- **Barge-in Support**: Handle interruptions gracefully
- **Adapter Pattern**: Easy migration from APIs to open-source models

## Architecture

The system uses an adapter pattern architecture, allowing easy switching between:
- **Telephony**: Twilio (current) → Asterisk (future)
- **STT**: Deepgram (current) → Whisper (future)
- **TTS**: ElevenLabs (current) → Qwen3-TTS (future)
- **LLM**: Anthropic Claude (current) → Ollama (future)
- **Calendar**: Yelp API (current) → Google Calendar (future)

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required API keys:
- Twilio (Account SID, Auth Token, Phone Number)
- Deepgram (for STT)
- ElevenLabs (for TTS)
- Anthropic (for LLM)
- Google Calendar (Service Account credentials or OAuth token)

### 3. Initialize Menu Data

```bash
python scripts/init_menu_data.py
```

This creates sample menu data and loads it into the RAG database.

### 4. Run the Server

**Production Server (with Twilio):**
```bash
python main.py
```
The server will start on `http://0.0.0.0:8000`

**Test Server (without Twilio):**
```bash
python test_main.py
```
The test server will start on `http://0.0.0.0:8001` with a web interface for testing.

### 5. Configure Twilio Webhook (Production Only)

In your Twilio console, set the webhook URL for incoming calls to:
```
https://your-domain.com/voice/incoming
```

## Project Structure

```
voice_bot/
├── src/
│   ├── adapters/          # Adapter interfaces and implementations
│   │   ├── base.py        # Base adapter interfaces
│   │   ├── telephony.py   # Twilio/Asterisk adapters
│   │   ├── stt.py         # Deepgram/Whisper adapters
│   │   ├── tts.py         # ElevenLabs/Qwen3-TTS adapters
│   │   ├── llm.py         # Anthropic/Ollama adapters
│   │   └── calendar.py    # Google Calendar adapter
│   ├── bot/               # Main bot application
│   │   ├── voice_bot.py   # Core bot logic
│   │   └── pipeline_setup.py  # Pipecat pipeline configuration
│   ├── rag/               # RAG system for menu queries
│   │   └── menu_rag.py    # Menu vector database
│   ├── guardrails/        # Safety and abuse prevention
│   │   └── safety.py      # Rate limiting, validation
│   ├── transfer/          # Staff transfer system
│   │   └── queue.py       # Queue-based transfer
│   ├── config.py          # Configuration management
│   └── server.py          # FastAPI web server
├── data/
│   └── sample_menu.json   # Sample menu data
├── scripts/
│   └── init_menu_data.py  # Initialize menu RAG
├── main.py                # Entry point
└── pyproject.toml         # Dependencies
```

## Usage

### Making a Call

When a customer calls your Twilio number:
1. The bot greets them
2. They can ask about the menu
3. They can make a reservation
4. They can request to speak with staff

### Menu Queries

Customers can ask questions like:
- "What vegetarian options do you have?"
- "What's the price of the salmon?"
- "Do you have gluten-free dishes?"

### Reservations

The bot collects:
- Date and time
- Party size
- Customer name and phone
- Special requests

### Staff Transfer

If a customer requests help or the bot can't assist:
- Request is added to queue
- Available staff member is assigned
- Call is transferred with context

## Development

### Adding New Adapters

1. Create a new class inheriting from the base adapter interface
2. Implement all abstract methods
3. Update configuration to select the adapter

### Testing

```bash
# Test menu RAG
python scripts/init_menu_data.py

# Run server in development
python main.py
```

## License

MIT
