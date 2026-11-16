# Voice Restaurant Bot

A voice agent that answers restaurant questions, books tables and hands the call to staff. A browser caller speaks to it in real time over a Daily room.

<!-- demo: add docs/demo.gif and an image link here once the recording exists -->

## Architecture

```
caller ─▶ Daily transport ─▶ Silero VAD ─▶ Deepgram STT ─▶ Smart Turn v3 ─▶ Claude (Anthropic) ─▶ ElevenLabs TTS ─▶ caller
                                                                                  │
                                                         tool calls ──────────────┤
                                  query_menu ─▶ MenuRAG (ChromaDB, all-MiniLM-L6-v2 embeddings)
                                  create_reservation ─▶ Guardrails validation ─▶ Google Calendar availability + booking
                                  transfer_to_staff ─▶ TransferQueue (priority queue, staff status)
```

One Pipecat pipeline (`src/bot/voice_bot.py`) runs the audio path. The model sees three tools. While a tool runs, the bot says "Let me check on that for you" to cover the wait. Smart Turn v3 decides when the caller has finished speaking, and Silero VAD handles interruptions.

| Path | Role |
|---|---|
| `src/bot/voice_bot.py` | Pipeline, tool schemas and tool handlers |
| `src/test_server.py` | Entry point: joins a Daily room, runs the bot and restarts after each session |
| `src/rag/menu_rag.py` | Menu embeddings in ChromaDB, top-3 semantic search |
| `src/guardrails/safety.py` | Rate limit (10 calls per hour per caller), profanity filter, failed-attempt blocking and reservation field validation. The bot calls only the reservation validation today |
| `src/transfer/queue.py` | Priority queue and staff availability for handoff |
| `src/adapters/calendar.py` | `GoogleCalendarAdapter` (used) and `YelpAdapter` (not wired in) behind one `CalendarAdapter` interface |
| `scripts/` | Menu data loader and component tests |

## Results

No latency or booking-accuracy benchmarks are recorded yet. What is checked today: `scripts/test_components.py` covers the guardrails (rate limit, profanity, reservation validation), the transfer queue (enqueue, dequeue, staff assignment) and menu search. The guardrail and queue tests pass. The menu-search test needs `chromadb` and `sentence-transformers` installed.

## Quickstart

Requires Python 3.13, [uv](https://docs.astral.sh/uv/), and accounts for Deepgram, ElevenLabs, Anthropic, Daily and Google Calendar.

```bash
uv sync
cp .env.example .env            # add API keys and the Daily room URL
python scripts/init_menu_data.py
uv run python -m src.test_server
```

Then join the Daily room from a browser and start talking. `docs/google_calendar_setup.md` covers the calendar credentials. A `Dockerfile` runs the same entry point.
