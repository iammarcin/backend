**Tags:** `#backend` `#audio` `#speech-to-text` `#stt` `#transcription` `#deepgram` `#openai-whisper` `#gemini` `#websocket` `#streaming`

# Audio Feature (Speech-to-Text)

Multi-provider speech-to-text transcription system supporting both static file upload and real-time streaming transcription.

## System Context

Part of the **storage-backend** FastAPI service. Provides audio transcription capabilities used by the chat feature for voice input, standalone transcription endpoints, and audio processing workflows.

## Architecture Overview

**Dual-Mode Design:**
1. **Static Mode** - Upload audio files via REST endpoint for batch transcription
2. **Streaming Mode** - Real-time transcription via WebSocket with live results

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/audio/transcribe` | POST | Static audio file transcription |
| WebSocket endpoint | WS | Real-time streaming transcription |

## Supported Providers

| Provider | Models | Modes | Notes |
|----------|--------|-------|-------|
| **Deepgram** | nova-3, nova-2 | Streaming only | Default streaming provider, real-time WebSocket |
| **OpenAI** | whisper-1, gpt-4o-transcribe | Static & Streaming | Whisper models for transcription |
| **Gemini** | gemini-2.5-flash/pro | Static & Streaming | Multimodal audio understanding |

## Key Workflows

### Static Transcription Flow
```
POST /transcribe → parse form → persist file → STTService.transcribe_file()
    → resolve provider → provider.transcribe_file() → rewrite transcript
    → build response with metadata
```

### Streaming Transcription Flow
```
WebSocket connect → receive settings JSON → send "websocket_ready"
    → create audio source from WS frames → STTService.transcribe_stream()
    → provider streams chunks → forward events to frontend
    → send "transcription_complete" on finish
```

## Audio Actions

- `TRANSCRIBE` - Convert speech to text
- `TRANSLATE` - Transcribe and translate to target language
- `CHAT` - Transcribe for chat input processing

## Provider Selection Logic

1. User specifies model or uses default
2. `infer_provider()` detects provider from model name
3. **Special case**: Deepgram falls back to Gemini for static (Deepgram is streaming-only)
4. Model aliases resolved (e.g., `deepgram-nova-3` → `nova-3`)

## Key Files

| File | Purpose |
|------|---------|
| `routes.py` | HTTP transcription endpoint |
| `websocket.py` | WebSocket streaming endpoint |
| `service.py` | `STTService` orchestration |
| `static_workflow.py` | Static file transcription workflow |
| `streaming_workflow.py` | Streaming transcription workflow |
| `config/audio/` | Centralised provider configuration and model lists |
| `deepgram_helpers.py` | Deepgram WebSocket protocol handling |
| `audio_sources.py` | Async generators for audio ingestion |

## Configuration

**Configuration Modules:**
- `config.audio.DEFAULT_TRANSCRIBE_MODEL` - Default transcription model
- `config.audio.DEFAULT_TRANSCRIBE_PROVIDER` - Default provider

**User Settings (from request):**
```json
{
  "speech": {
    "model": "nova-3",
    "language": "en",
    "temperature": 0.0,
    "optional_prompt": "context hint"
  }
}
```

## Audio Processing

- **Resampling**: Automatic PCM resampling if client rate ≠ provider rate (24kHz → 16kHz)
- **Chunk handling**: Binary frames or base64-encoded JSON chunks
- **Post-processing**: Regex-based transcription rewriting rules

## WebSocket Message Protocol

**Client → Server:**
- Binary frames: Raw PCM audio
- JSON: `{"type": "audio_chunk", "data": "<base64>"}` or control messages

**Server → Client:**
- `{"type": "websocket_ready"}` - Connection ready
- `{"type": "transcription", "content": "..."}` - Transcript segment
- `{"type": "transcription_complete"}` - Transcription finished

## Dependencies

- `core/providers/audio/` - Provider implementations
- `core/streaming/manager.py` - Event distribution
- `config/transcription/replacements.py` - Rewrite rules
