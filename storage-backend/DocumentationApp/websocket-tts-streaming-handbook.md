# WebSocket TTS Streaming Handbook

**Last Updated:** 2026-01-12
**Scope:** Real-time TTS streaming architecture with parallel text/audio processing

## Overview

This document describes the real-time Text-to-Speech (TTS) streaming architecture that enables audio generation to begin **before text generation completes**. This is achieved through WebSocket-based communication with ElevenLabs.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Flow](#data-flow)
4. [Key Components](#key-components)
5. [ElevenLabs WebSocket Protocol](#elevenlabs-websocket-protocol)
6. [Queue-Based Text Duplication](#queue-based-text-duplication)
7. [Configuration](#configuration)
8. [WebSocket Events](#websocket-events)
9. [OpenAI TTS Provider (Non-WebSocket)](#openai-tts-provider-non-websocket)
10. [File Reference](#file-reference)

---

## Overview

### The Problem

Traditional TTS workflows follow a sequential pattern:
1. Generate complete text response
2. Send complete text to TTS provider
3. Wait for audio generation
4. Stream audio to client

This creates **significant latency** - users must wait for both text generation AND audio synthesis to complete.

### The Solution

Our WebSocket TTS streaming architecture enables **parallel processing**:
1. Text generation begins streaming to the client
2. **Simultaneously**, text chunks are duplicated to a TTS queue
3. TTS provider (ElevenLabs) receives text chunks via WebSocket in real-time
4. Audio chunks are generated and streamed back **before text generation completes**

This dramatically reduces perceived latency and creates a more responsive user experience.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (WebSocket)                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FastAPI WebSocket Route                             │
│                      (features/chat/websocket_routes.py)                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Workflow Dispatcher                               │
│                    (dispatch_workflow, stream_response)                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        StreamingManager                              │   │
│  │  - Token-based completion ownership                                  │   │
│  │  - Queue fan-out (WebSocket, TTS)                                    │   │
│  │  - Text chunk duplication to TTS queue                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         TTSOrchestrator                              │   │
│  │  - Lifecycle management for parallel TTS                             │   │
│  │  - Background task creation and monitoring                           │   │
│  │  - TTS queue registration with StreamingManager                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                          │                         │
                          ▼                         ▼
            ┌──────────────────────┐   ┌──────────────────────────────────┐
            │   Text Provider      │   │        TTS Service               │
            │  (OpenAI, Claude,    │   │  (features/tts/service.py)       │
            │   Gemini, etc.)      │   │                                  │
            │                      │   │  stream_from_text_queue()        │
            └──────────────────────┘   └──────────────────────────────────┘
                          │                         │
                          │                         ▼
                          │            ┌──────────────────────────────────┐
                          │            │   ElevenLabsTTSProvider          │
                          │            │  (core/providers/tts/elevenlabs) │
                          │            │                                  │
                          │            │  supports_input_stream = True    │
                          │            └──────────────────────────────────┘
                          │                         │
                          │                         ▼
                          │            ┌──────────────────────────────────┐
                          │            │   ElevenLabs WebSocket API       │
                          │            │  wss://api.elevenlabs.io/v1/     │
                          │            │  text-to-speech/{voice}/         │
                          │            │  stream-input                    │
                          │            │                                  │
                          │            │  - Receives text chunks          │
                          │            │  - Returns audio chunks          │
                          │            └──────────────────────────────────┘
                          │                         │
                          ▼                         ▼
            ┌──────────────────────────────────────────────────────────────┐
            │                     CLIENT (WebSocket)                        │
            │                                                               │
            │  Receives interleaved:                                        │
            │  - {"type": "text_chunk", "content": "chunk..."}              │
            │  - {"type": "audio_chunk", "content": "base64_audio_data"}    │
            └──────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Phase 1: Initialization

1. **Client connects** via WebSocket with TTS settings:
   ```json
   {
     "settings": {
       "tts": {
         "tts_auto_execute": true,
         "provider": "elevenlabs",
         "voice": "21m00Tcm4TlvDq8ikWAM",
         "model": "eleven_turbo_v2_5",
         "format": "pcm_24000"
       }
     }
   }
   ```

2. **StreamingManager** creates a completion token (ensures single completion authority)

3. **TTSOrchestrator** evaluates settings:
   - Checks `tts_auto_execute == true`
   - Checks `streaming != false`
   - If enabled: creates TTS queue and registers with StreamingManager

4. **Background TTS task** starts, waiting for text chunks

### Phase 2: Parallel Streaming

```
Text Provider                  StreamingManager                 TTS Background Task
     │                               │                                   │
     │ emit("chunk1")                │                                   │
     │──────────────────────────────>│                                   │
     │                               │ send_to_queues(text)              │
     │                               │─────────────────────>│ WebSocket  │
     │                               │                      │ Queue      │
     │                               │ _maybe_send_to_tts_queue()        │
     │                               │──────────────────────────────────>│
     │                               │                                   │
     │ emit("chunk2")                │                      await queue.get()
     │──────────────────────────────>│                                   │
     │                               │ (repeat for each chunk)           │
     │                               │                                   │
     │                               │                 ElevenLabs WebSocket
     │                               │                        │
     │                               │                        │ send text
     │                               │                        │────────>
     │                               │                        │
     │                               │                        │ receive audio
     │                               │                        │<────────
     │                               │                        │
     │                               │          audio_queue.put(bytes)   │
     │                               │                                   │
     │                               │<────────── yield audio_chunk ─────│
     │                               │                                   │
     │                               │ send_to_queues(audio)             │
     │                               │─────────────────────> WebSocket   │
```

### Phase 3: Completion

1. **Text generation completes** → `text_completed` event sent
2. **StreamingManager deregisters TTS queue** → sends `None` sentinel
3. **TTS task receives sentinel** → sends EOS to ElevenLabs WebSocket
4. **ElevenLabs closes connection** after final audio chunk
5. **Audio persisted to S3** (if configured)
6. **TTS completion events sent**: `tts_generation_completed`, `tts_completed`
7. **Client completion**: both `text_completed` and `tts_completed` received → streaming complete

---

## Key Components

### StreamingManager

**Location**: `core/streaming/manager.py`

Manages multiple output queues with token-based completion ownership.

**Key responsibilities**:
- Queue fan-out (WebSocket clients, TTS)
- Text chunk duplication to TTS queue
- Completion signal coordination

```python
class StreamingManager:
    def register_tts_queue(self, queue: asyncio.Queue) -> None:
        """Register queue for TTS text chunk duplication."""
        self._tts_text_queue = queue
        self._tts_enabled = True

    async def _maybe_send_to_tts_queue(self, data: Any) -> None:
        """Duplicate text payloads to TTS queue when active."""
        if data.get("type") != "text_chunk":
            return
        content = data.get("content")
        if content and content.strip():
            await self._tts_text_queue.put(content)
```

### TTSOrchestrator

**Location**: `features/chat/services/streaming/tts_orchestrator.py`

Manages the lifecycle of parallel TTS streaming during chat flows.

**Key responsibilities**:
- Evaluate whether TTS should be enabled based on settings
- Create and register TTS queue with StreamingManager
- Start background TTS streaming task
- Wait for completion and collect metadata

```python
class TTSOrchestrator:
    def should_enable_tts(self) -> bool:
        """Return True when settings indicate auto-executed streaming TTS."""
        tts_settings = self.settings.get("tts", {})
        auto_execute = bool(tts_settings.get("tts_auto_execute"))
        streaming_enabled = tts_settings.get("streaming")
        return auto_execute and streaming_enabled is not False

    async def start_tts_streaming(self) -> bool:
        """Initialize queue duplication and background TTS streaming."""
        self._tts_queue = asyncio.Queue()
        self.manager.register_tts_queue(self._tts_queue)
        self._tts_task = asyncio.create_task(self._run_tts_streaming(user_settings))
        return True
```

### ElevenLabsTTSProvider

**Location**: `core/providers/tts/elevenlabs.py`

Provider implementation with WebSocket streaming support.

**Key attribute**:
```python
class ElevenLabsTTSProvider(BaseTTSProvider):
    supports_input_stream = True  # Enables queue-based streaming
```

**Key method**:
```python
async def stream_from_text_queue(
    self,
    *,
    text_queue: asyncio.Queue[str | None],
    voice: str,
    model: Optional[str] = None,
    audio_format: str = "pcm_24000",
    ...
) -> AsyncIterator[str]:
    """Stream audio while consuming text chunks from a queue."""
```

---

## ElevenLabs WebSocket Protocol

### Connection URI

```
wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input
    ?model_id={model}
    &inactivity_timeout=180
    &output_format={format}
```

### Initial Configuration Message

Sent once upon connection:

```json
{
  "text": " ",
  "voice_settings": {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": true
  },
  "generation_config": {
    "chunk_length_schedule": [120, 160, 250, 290]
  },
  "xi_api_key": "your_api_key"
}
```

### Text Chunk Messages

Each text chunk is sent as:

```json
{"text": "chunk content here"}
```

### End-of-Stream Signal

When text generation completes:

```json
{"text": ""}
```

### Audio Response Messages

ElevenLabs responds with:

```json
{
  "audio": "base64_encoded_audio_bytes",
  "status": "ongoing"
}
```

Final message:

```json
{
  "audio": "final_base64_audio",
  "status": "finished"
}
```

### Implementation

**Location**: `core/providers/tts/utils/queue_websocket_streaming.py`

```python
async def stream_websocket_audio_from_queue(
    *,
    uri: str,
    text_queue: asyncio.Queue[str | None],
    api_key: str,
    voice_settings: Mapping[str, Any],
    chunk_length_schedule: list[int],
    provider_name: str,
) -> AsyncIterator[bytes]:
    """
    Duplex WebSocket streaming:
    - Send task: reads text from queue, forwards to ElevenLabs
    - Receive task: listens for audio chunks from ElevenLabs
    Both run concurrently - no waiting for text completion!
    """
```

Key implementation details:

1. **Separate async tasks** for sending and receiving
2. **Audio queue** bridges receive task to main iterator
3. **Sentinel value** (`None`) signals end of text stream
4. **Error propagation** via tuple in audio queue

---

## Queue-Based Text Duplication

The key innovation enabling parallel TTS is the text queue duplication mechanism.

### How It Works

1. **StreamingManager** maintains a reference to the TTS text queue
2. **Every text chunk** sent via `send_to_queues()` is also duplicated to TTS queue
3. **TTS background task** consumes from this queue independently
4. **When text completes**, sentinel (`None`) is placed in queue

### Code Flow

```python
# In StreamingManager.send_to_queues()
async def send_to_queues(self, data: Any, queue_type: str = "all") -> None:
    # Send to WebSocket queues
    for queue in self.queues:
        await queue.put(data)

    # Duplicate text to TTS queue
    await self._maybe_send_to_tts_queue(data)

async def _maybe_send_to_tts_queue(self, data: Any) -> None:
    if not self._tts_enabled:
        return
    if data.get("type") != "text_chunk":
        return
    content = data.get("content")
    if content and content.strip():
        await self._tts_text_queue.put(content)
```

---

## Configuration

### TTS Settings Schema

**Location**: `features/tts/schemas/requests.py`

```python
class TTSProviderSettings(BaseModel):
    provider: str              # "elevenlabs" or "openai"
    model: str                 # e.g., "eleven_turbo_v2_5"
    voice: str                 # Voice ID or name
    format: str                # "pcm", "pcm_24000", "mp3", etc.
    streaming: bool            # Reserved for future use
    speed: float               # Playback speed multiplier
    instructions: str          # Additional instructions
    tts_auto_execute: bool     # KEY: Enable parallel TTS during chat
    chunk_schedule: list[int]  # ElevenLabs chunk boundaries

    # ElevenLabs-specific:
    stability: float           # Voice stability (0-1)
    similarity_boost: float    # Similarity boost (0-1)
    style: float               # Style exaggeration (0-1)
    use_speaker_boost: bool    # Apply speaker boost
```

### Enabling WebSocket TTS Streaming

Client must send:

```json
{
  "settings": {
    "tts": {
      "tts_auto_execute": true,
      "provider": "elevenlabs",
      "voice": "rachel",
      "model": "eleven_turbo_v2_5",
      "format": "pcm_24000"
    }
  }
}
```

### Voice Resolution

ElevenLabs supports friendly voice names that are resolved to IDs:

```python
VOICE_NAME_TO_ID = {
    "sherlock": "ywZw8GayBRRkuqUnUGhk",
    "naval": "30zc5PfKKHzfXQfjXbLU",
    "rachel": "21m00Tcm4TlvDq8ikWAM",
    # ... more voices
}
```

### Audio Format Mapping

```python
FORMAT_TO_WEBSOCKET_FORMAT = {
    "pcm": "pcm_24000",
    "pcm_24000": "pcm_24000",
    "mp3": "mp3_44100_128",
    "mp3_44100": "mp3_44100_128",
}
```

### Chunk Length Schedule

Controls when ElevenLabs produces audio chunks:

```python
chunk_length_schedule = [120, 160, 250, 290]  # Default
# Tells ElevenLabs to produce audio at approximately these character boundaries
```

---

## WebSocket Events

### Events Sent to Client

| Event Type | Description |
|------------|-------------|
| `text_chunk` | Text chunk from AI response |
| `audio_chunk` | Base64-encoded audio chunk |
| `tts_started` | TTS streaming has begun |
| `tts_generation_completed` | TTS streaming finished with metadata |
| `tts_completed` | TTS processing complete |
| `text_completed` | Text generation finished |
| `tts_file_uploaded` | Audio file uploaded to S3 |

**Completion model**: Clients track two flags (`text_completed` + `tts_completed`) and finalize when both are true. See `websocket-events-handbook.md` for details.

### Event Sequence

```
1. Connection established
2. Text generation starts
3. tts_started
4. text_chunk (interleaved)
5. audio_chunk (interleaved, starts before text completes)
6. text_completed
7. (remaining audio chunks)
8. tts_generation_completed
9. tts_completed
10. tts_file_uploaded (if S3 enabled)
```

---

## OpenAI TTS Provider (Non-WebSocket)

OpenAI's TTS API does not support WebSocket streaming, so it cannot achieve the same parallel processing.

**Location**: `core/providers/tts/openai.py`

### Key Difference

```python
class OpenAITTSProvider(BaseTTSProvider):
    supports_input_stream = False  # Cannot stream text input
```

### Fallback Behavior

When TTS is requested with OpenAI provider:

1. **All text must be collected first** (waits for completion)
2. **Full text sent** to OpenAI TTS API
3. **Audio streamed back** via REST (not WebSocket)
4. Results in: `text_generation_time + audio_generation_time`

### Implementation

Uses threading to bridge blocking OpenAI client:

```python
async def stream(self, request: TTSRequest) -> AsyncIterator[bytes]:
    queue: asyncio.Queue = asyncio.Queue()

    def _produce() -> None:
        with self._client.audio.speech.with_streaming_response.create(**payload) as response:
            for chunk in response.iter_bytes(1024):
                loop.call_soon_threadsafe(queue.put_nowait, bytes(chunk))

    thread = threading.Thread(target=_produce, daemon=True)
    thread.start()

    while True:
        item = await queue.get()
        if item is sentinel:
            break
        yield item
```

### When OpenAI TTS is Used

The system automatically falls back to buffered mode:

```python
# In service_stream_queue_helpers.py
if not provider.supports_input_stream:
    # Fallback: buffer all text, then stream audio
    return await perform_fallback_buffered_stream(...)
```

---

## File Reference

### Core Provider Implementation

| File | Description |
|------|-------------|
| `core/providers/tts/elevenlabs.py` | Main ElevenLabs provider class |
| `core/providers/tts/elevenlabs_websocket.py` | WebSocket streaming helpers |
| `core/providers/tts/openai.py` | OpenAI TTS provider (non-WebSocket) |
| `core/providers/base.py` | Base TTS provider interface |

### WebSocket Streaming Utilities

| File | Description |
|------|-------------|
| `core/providers/tts/utils/queue_websocket_streaming.py` | Queue-based duplex streaming |
| `core/providers/tts/utils/websocket_streaming.py` | Full-text WebSocket streaming |
| `core/providers/tts/utils/_elevenlabs_helpers.py` | Voice resolution, format mapping |

### Service Layer

| File | Description |
|------|-------------|
| `features/tts/service.py` | High-level TTS service orchestration |
| `features/tts/service_stream_queue.py` | Queue-based streaming implementation |
| `features/tts/service_stream_queue_helpers.py` | Streaming helpers with fallback |

### Streaming Infrastructure

| File | Description |
|------|-------------|
| `core/streaming/manager.py` | StreamingManager with TTS queue support |
| `features/chat/services/streaming/tts_orchestrator.py` | Parallel TTS lifecycle management |
| `features/chat/services/streaming/core.py` | Main streaming orchestration |

### Tests

| File | Description |
|------|-------------|
| `tests/unit/core/providers/test_elevenlabs_websocket.py` | WebSocket unit tests |
| `tests/integration/tts/test_websocket.py` | WebSocket integration tests |
| `tests/integration/tts/test_elevenlabs_websocket_integration.py` | Full integration tests |

---

## Summary

The WebSocket TTS streaming architecture achieves low-latency audio by:

1. **Parallel processing**: Text generation and TTS run concurrently
2. **Queue-based decoupling**: StreamingManager duplicates text chunks to TTS queue
3. **WebSocket streaming**: ElevenLabs accepts text chunks in real-time
4. **Duplex communication**: Audio chunks return while text is still being sent
5. **Token-based completion**: Ensures orderly shutdown of all streams

This design reduces perceived latency from `text_time + audio_time` to approximately `max(text_time, audio_time)`, creating a significantly more responsive user experience.
