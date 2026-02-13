**Tags:** `#backend` `#realtime` `#voice-chat` `#websocket` `#openai-realtime-api` `#gemini-live` `#duplex-audio` `#turn-management` `#vad`

# Real-Time Voice Chat Feature

Sophisticated WebSocket-based duplex audio conversation platform supporting OpenAI Realtime API and Google Gemini Live with session management, turn tracking, and audio persistence.

## System Context

Part of the **storage-backend** FastAPI service. Provides low-latency voice conversations with AI models, integrated with chat history persistence and S3 audio storage.

## Architecture Overview

**Dual Task Model:**
```
┌──────────────────────────────────────────┐
│       RealtimeSessionController          │
├────────────────┬─────────────────────────┤
│ relay_provider │ forward_client_messages │
│   _events()    │        ()               │
├────────────────┼─────────────────────────┤
│ Receives from  │ Sends to provider,      │
│ AI provider    │ queues audio from client│
└────────────────┴─────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/ws` | WebSocket | Main realtime endpoint (mode detection) |
| `/realtime/health` | GET | Provider health & session count |
| `/realtime/health/ready` | GET | Readiness probe |
| `/realtime/health/live` | GET | Liveness probe |

## Supported Providers

| Provider | Models | Features |
|----------|--------|----------|
| **OpenAI Realtime** | gpt-realtime, gpt-realtime-mini | VAD, 10 voices, bidirectional |
| **Gemini Live** | gemini-2.5-flash/pro | Multimodal, live translation |

## Session Lifecycle

```
1. WebSocket connects → Accept, send websocketReady
2. Client sends init message with settings
3. Backend validates, creates session context
4. Opens provider connection (OpenAI/Gemini)
5. Dual task execution:
   - relay_provider_events() → Forward AI audio to client
   - forward_client_messages() → Send client audio to AI
6. Turn management: detect completion, finalize, persist
7. Cleanup: close provider, upload audio, close WebSocket
```

## Turn State Machine

```
IDLE → USER_SPEAKING → AI_THINKING → AI_RESPONDING → PERSISTING → COMPLETED
                                                  ↓
                                            CANCELLED/ERRORED
```

**Turn Completion Conditions:**
- `response_done` from provider
- `has_user_transcript` (if required)
- `has_ai_text` OR `has_ai_audio` (if required)

## Key Components

### RealtimeSessionController
Main orchestrator:
- Session startup and configuration
- Provider resolution and connection
- Event dispatching and turn detection
- Graceful shutdown coordination

### SessionClosureManager
Coordinates graceful shutdown:
- `request_close()` - Initiate shutdown
- `ensure_closed()` - Complete cleanup
- Handles provider disconnection, S3 upload

### TurnFinaliser
Turn completion workflow:
- Audio processing (validate, upload, translate)
- History persistence
- Event emission (turn.completed, turn.persisted)

### RealtimeTurnContext
Accumulates streaming fragments:
- `user_transcript_parts` - User speech chunks
- `assistant_text_parts` - AI text response
- `audio_chunks` - Raw PCM16 audio bytes

## Audio Processing

**Format:** PCM16, 24kHz, mono

**Pipeline:**
1. Collect audio chunks during turn
2. Validate format and minimum duration
3. Convert PCM → WAV
4. Upload to S3: `assets/realtime/{customer_id}/...`
5. Optional translation (Gemini with live_translation)

## Event Types

**Turn Events:**
- `turn.ai_responding` - AI started output
- `turn.completed` - Turn finished
- `turn.persisted` - Saved to database

**Content Events:**
- `text` - Text chunks (model or transcript)
- `audio` - Audio chunks (base64)
- `transcription` - User speech transcript

**Control Events:**
- `session.closed` - Session ended
- `realtime.error` - Error with recovery info

## Session Settings

```json
{
  "model": "gpt-realtime",
  "voice": "alloy",
  "temperature": 0.7,
  "vad_enabled": true,
  "enable_audio_input": true,
  "enable_audio_output": true,
  "tts_auto_execute": true,
  "live_translation": false,
  "instructions": "System prompt..."
}
```

## VAD (Voice Activity Detection)

**Enabled (default):**
- Server-side silence detection
- Multi-turn conversations
- Triggers `input_audio_buffer` events

**Disabled:**
- Single-turn mode
- Manual turn boundaries

## File Structure

```
features/realtime/
├── routes.py               # WebSocket endpoint
├── service.py              # RealtimeChatService
├── session_controller.py   # Main orchestrator
├── session_startup.py      # Initialization
├── session_closer_*.py     # Shutdown coordination
├── provider.py             # Provider event relay
├── provider_session.py     # Provider resolution
├── event_handler.py        # Event dispatch
├── event_payloads.py       # Event construction
├── turn_*.py               # Turn management
├── audio_finaliser.py      # Audio processing
├── client*.py              # Client message handling
├── context.py              # RealtimeTurnContext
├── state.py                # RealtimeTurnState
├── schemas.py              # Pydantic models
├── metrics.py              # Observability
└── errors.py               # Error classification
```

## Error Classification

**Expected (non-fatal):**
- `empty_input_audio_buffer` - No audio captured
- `voice_not_found` - VAD didn't detect speech

**Fatal:**
- `connection_failed_error` - Provider unreachable
- `persistence_failed_error` - Database write failure
- `audio_upload_failed_error` - S3 failure

## Dependencies

- `core/providers/realtime/` - Provider implementations
- `core/streaming/manager.py` - Event distribution
- `features/chat/services/history/` - Chat persistence
- `infrastructure/aws/storage.py` - S3 uploads
