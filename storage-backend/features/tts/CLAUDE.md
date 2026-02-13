**Tags:** `#backend` `#tts` `#text-to-speech` `#audio-synthesis` `#openai-tts` `#elevenlabs` `#streaming` `#websocket` `#audio-generation`

# Text-to-Speech Feature

Multi-provider text-to-speech system supporting HTTP streaming, WebSocket streaming, and queue-based real-time delivery for chat integration.

## System Context

Part of the **storage-backend** FastAPI service. Provides TTS capabilities for chat workflows (auto-TTS), standalone generation, and real-time voice synthesis.

## Supported Providers

| Provider | Models | Key Features |
|----------|--------|--------------|
| **OpenAI** | tts-1, tts-1-hd | Standard REST/streaming, multiple voices |
| **ElevenLabs** | eleven-turbo-v2, etc. | WebSocket real-time, voice customization |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/tts/generate` | POST | Synchronous generation |
| `/api/v1/tts/stream` | POST | HTTP streaming response |
| `/api/v1/tts/ws` | WebSocket | Real-time ElevenLabs streaming |

## Streaming Modes

### 1. HTTP Streaming (`/stream`)
- Client receives `StreamingResponse`
- Audio chunks delivered as they generate
- Headers include provider/model metadata

### 2. WebSocket Streaming (`/ws`)
- Bidirectional: text in, audio out
- ElevenLabs real-time API integration
- Supports progressive text delivery

### 3. Queue-Based (Chat Integration)
- Text queue fed by LLM generation
- Audio queue delivers to client
- Used for auto-TTS in chat workflows

## Request Format

```json
{
  "action": "tts_no_stream" | "tts_stream",
  "userInput": {"text": "Hello world"},
  "userSettings": {
    "general": {"saveToS3": true},
    "tts": {
      "provider": "elevenlabs",
      "model": "eleven-turbo-v2",
      "voice": "21m00Tcm4TlvDq8ikWAM",
      "format": "mp3",
      "speed": 1.0,
      "stability": 0.85,
      "similarityBoost": 0.95,
      "chunkSchedule": [120, 160, 250, 290]
    }
  },
  "customerId": 123
}
```

## Architecture

```
features/tts/
├── routes.py                  # HTTP/WebSocket endpoints
├── service.py                 # TTSService orchestration
├── service_generate.py        # Sync generation
├── service_streaming.py       # Audio chunk iteration
├── service_stream_http.py     # HTTP streaming
├── service_stream_queue.py    # Queue-based streaming
├── service_stream_queue_helpers.py
├── service_persistence.py     # S3 upload
├── request_builder.py         # Request construction
├── utils.py                   # Text tuning, format conversion
├── test_mode.py               # Canned test responses
├── schemas/
│   ├── requests.py            # TTSGenerateRequest
│   └── responses.py           # TTSGenerateResponse
└── websocket/
    ├── endpoint.py            # WebSocket handler
    ├── client.py              # ElevenLabs WS client
    ├── config.py              # Realtime settings
    └── events.py              # Event forwarding
```

## Text Processing

**tune_text():**
- Remove action patterns (`*burps loudly*`)
- Remove XML tags (`<response>`)
- Normalize sentence endings
- Strip inner monologue tags

**split_text_for_tts():**
- Max chunk: 4096 characters
- Respects sentence boundaries
- Splits on `. `, `! `, `? `

## Audio Formats

| Format | MIME Type |
|--------|-----------|
| mp3/mpeg | audio/mpeg |
| wav/wave | audio/wav |
| ogg/opus | audio/ogg |
| pcm_24000 | audio/L16;rate=24000;channels=1 |

**PCM Conversion:**
- Raw PCM → WAV for storage
- Uses Python `wave` module

## ElevenLabs WebSocket Flow

```
1. Client connects to /api/v1/tts/ws
2. Server sends: {"type": "ready"}
3. Client sends init: {"type": "init", "payload": {...}}
4. Server validates, sends: {"type": "status", "status": "initialised"}
5. Client sends: {"type": "send_text", "text": "..."}
6. Server streams: {"type": "audio_chunk", "chunk": "base64...", ...}
7. Client sends: {"type": "stop"}
8. Server sends: {"type": "status", "status": "completed", "timings": {...}}
```

## Chunk Schedule

Controls ElevenLabs audio chunk timing:
- Format: List of 4 integers (milliseconds)
- Example: `[120, 160, 250, 290]`
- Pattern repeats for longer text

## Storage Integration

**S3 Upload (saveToS3: true):**
- Path: `customers/{id}/assets/tts/{timestamp}_{uuid}.mp3`
- Returns public S3 URL

**Inline (saveToS3: false):**
- Returns `data:audio/mpeg;base64,{encoded}`

## Test Mode

When `user_settings.general.return_test_data = true`:
- Returns canned audio payload
- No provider API calls
- Useful for testing/development

## Dependencies

- `core/providers/tts/` - Provider implementations
- `core/streaming/manager.py` - Event distribution
- `infrastructure/aws/storage.py` - S3 uploads
- `websockets` - ElevenLabs WebSocket client

## Configuration

**Configuration Modules:**
- `config.tts.providers.elevenlabs.API_KEY` - ElevenLabs API key (via `ELEVEN_API_KEY`)
- `config.tts.providers.elevenlabs.DEFAULT_MODEL` - Default ElevenLabs model
- `config.tts.providers.openai.DEFAULT_MODEL` - Default OpenAI TTS model
- `config.tts.providers.elevenlabs.DEFAULT_VOICE_ID` - Default voice (`"21m00Tcm4TlvDq8ikWAM"`)
- `config.tts.providers.elevenlabs.DEFAULT_CHUNK_SCHEDULE` - `[120, 160, 250, 290]`
