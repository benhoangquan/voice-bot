# Test Server Guide

The test server allows you to test the voice bot without setting up Twilio or making actual phone calls. It provides a web interface and API endpoints for testing all bot functionality.

## Features

- **Web Interface**: Interactive chat interface in your browser
- **REST API**: Text-based chat endpoint for programmatic testing
- **WebSocket API**: Real-time chat for advanced testing
- **Session Management**: Multiple concurrent test sessions
- **No Twilio Required**: Test all functionality without telephony setup

## Running the Test Server

```bash
python test_main.py
```

The server will start on `http://localhost:8001`

## Usage

### Web Interface

1. Open `http://localhost:8001` in your browser
2. A chat interface will appear
3. Type messages and interact with the bot
4. Click "New Session" to start a fresh conversation

### REST API

**Chat Endpoint:**
```bash
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I want to make a reservation",
    "session_id": "test_123"
  }'
```

**Response:**
```json
{
  "response": "I'd be happy to help you make a reservation...",
  "session_id": "test_123",
  "tool_calls": null
}
```

### WebSocket API

Connect to `ws://localhost:8001/ws/chat` for real-time chat:

```javascript
const ws = new WebSocket('ws://localhost:8001/ws/chat');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'message',
    text: 'Hello!'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Bot response:', data.text);
};
```

## API Endpoints

### GET `/`
Web interface for interactive testing

### POST `/api/chat`
Text-based chat endpoint

**Request:**
```json
{
  "text": "What vegetarian options do you have?",
  "session_id": "optional_session_id"
}
```

**Response:**
```json
{
  "response": "Here are some vegetarian options...",
  "session_id": "session_id",
  "tool_calls": null
}
```

### WebSocket `/ws/chat`
Real-time chat via WebSocket

**Messages:**
- `{"type": "message", "text": "..."}` - Send message
- `{"type": "close"}` - Close connection

**Responses:**
- `{"type": "connected", "session_id": "...", "message": "..."}` - Connection established
- `{"type": "response", "text": "...", "session_id": "..."}` - Bot response

### GET `/api/health`
Health check and service status

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "stt": true,
    "tts": true,
    "llm": true,
    "calendar": true,
    "rag": true
  },
  "active_sessions": 2
}
```

### GET `/api/sessions`
List all active sessions

**Response:**
```json
{
  "sessions": ["test_123", "test_456"],
  "count": 2
}
```

### DELETE `/api/sessions/{session_id}`
Delete a specific session

## Testing Scenarios

### 1. Menu Queries
```
User: "What vegetarian options do you have?"
Bot: [Lists vegetarian menu items from RAG database]
```

### 2. Reservation Creation
```
User: "I want to make a reservation for 4 people on December 25th at 7pm"
Bot: [Collects details and creates Google Calendar event]
```

### 3. Staff Transfer
```
User: "I need to speak with a manager"
Bot: [Adds to transfer queue and initiates transfer]
```

### 4. Guardrails Testing
```
User: [Profanity or spam]
Bot: [Applies guardrails and blocks/redirects]
```

## Configuration

The test server uses the same configuration as the main server but doesn't require:
- Twilio credentials (uses mock telephony adapter)
- Phone number configuration

Still required:
- Anthropic API key (for LLM)
- Deepgram API key (optional, for STT features)
- ElevenLabs API key (optional, for TTS features)
- Google Calendar credentials (optional, for reservation features)

## Differences from Production Server

1. **No Twilio Integration**: Uses a mock telephony adapter
2. **Text Input/Output**: Direct text instead of audio
3. **Web Interface**: Built-in chat UI for easy testing
4. **Different Port**: Runs on port 8001 instead of 8000
5. **Session Management**: Multiple concurrent test sessions

## Troubleshooting

### "Missing required environment variable"
- Set up your `.env` file with at least `ANTHROPIC_API_KEY`
- Other API keys are optional but enable additional features

### "Menu data file not found"
- Run `python scripts/init_menu_data.py` to create sample menu data

### "Failed to initialize Google Calendar"
- Calendar features are optional
- Bot will still work for menu queries and general conversation
- Set up Google Calendar credentials to test reservation features

### Session not persisting
- Sessions are stored in memory
- Restarting the server clears all sessions
- Use the same `session_id` to continue a conversation

## Example Test Script

```python
import requests
import json

BASE_URL = "http://localhost:8001"

# Start a conversation
session_id = "test_session_1"

# Test menu query
response = requests.post(
    f"{BASE_URL}/api/chat",
    json={"text": "What vegetarian options do you have?", "session_id": session_id}
)
print("Menu query:", response.json()["response"])

# Test reservation
response = requests.post(
    f"{BASE_URL}/api/chat",
    json={
        "text": "I want to make a reservation for 4 people on 2024-12-25 at 19:00",
        "session_id": session_id
    }
)
print("Reservation:", response.json()["response"])

# Check health
health = requests.get(f"{BASE_URL}/api/health")
print("Health:", health.json())
```
