# BetterAI Backend API Documentation
**Complete Integration Guide for External Applications**

Version: 2.6
Last Updated: 2026-01-12

---

## Table of Contents

1. [Overview](#1-overview)
2. [Authentication](#2-authentication)
3. [Text Generation (Chat)](#3-text-generation-chat)
3.5 [Batch API](#35-batch-api)
4. [Audio Transcription (Speech-to-Text)](#4-audio-transcription-speech-to-text)
5. [Text-to-Speech (TTS)](#5-text-to-speech-tts)
6. [Image Generation](#6-image-generation)
7. [Video Generation](#7-video-generation)
8. [Chart Generation](#8-chart-generation)
9. [Realtime Audio Conversations](#9-realtime-audio-conversations)
10. [Browser Automation](#10-browser-automation)
10.5 [Proactive Agent (Sherlock & Bugsy)](#105-proactive-agent-sherlock--bugsy)
11. [Semantic Search (Context Enhancement)](#11-semantic-search-context-enhancement)
12. [Health Data (Garmin)](#12-health-data-garmin)
13. [Blood Test Data](#13-blood-test-data)
14. [UFC Fighter Data](#14-ufc-fighter-data)
15. [File Upload](#15-file-upload)
16. [WebSocket Communication](#16-websocket-communication)
17. [Error Handling](#17-error-handling)
18. [Rate Limits & Best Practices](#18-rate-limits--best-practices)

---

## 1. Overview

The BetterAI backend provides a unified API for multiple AI providers, enabling text generation, audio processing, image/video generation, and specialized data services. All endpoints support synchronous, streaming, and batch modes for large volumes.

**Base URL**: `https://your-backend-domain.com`

**Key Features**:
- 40+ AI models across 8 text providers
- Multi-provider image and video generation
- Interactive chart generation (bar, line, pie, area, scatter, mermaid diagrams)
- Real-time audio transcription and TTS
- Bidirectional realtime audio conversations
- Health and sports data APIs
- WebSocket streaming for low-latency responses
- Agentic workflow orchestration with internal tool execution (image, video, text, charts)
- Batch API for cost-efficient asynchronous processing (50% cost reduction)

### Agentic Workflow Overview

The backend now ships with the **Agentic Workflow Architecture** described in `DocumentationApp/agentic-workflow-handbook.md`. This loop keeps every provider conversation in the OpenAI Chat Completions format, lets the model call internal tools (generate image/video/text) for up to 10 iterations, and streams each event (`custom_event` with `iterationStarted`, `tool_start`, `tool_result`, `text_chunk`, `iterationCompleted`) over WebSocket/SSE. External integrators only provide the conversation payload—the agent decides when to call tools and automatically appends the tool results back into chat history. Use the handbook for deeper architectural diagrams, but at the API surface this simply means:
- `/chat` and `/chat/stream` automatically run the loop when `settings.general.ai_agent_enabled=true` (default for tool-enabled models)
- WebSocket clients receive tool call events without extra wiring
- Conversation history you store should already include assistant `tool_calls` and tool response messages so that resumptions keep full context

---

## 2. Authentication

### HTTP Authentication
All HTTP requests require a JWT token in the Authorization header:

```http
Authorization: Bearer <your_jwt_token>
```

### WebSocket Authentication
WebSocket connections require the token as a query parameter:

```
wss://your-backend-domain.com/chat/ws?token=<your_jwt_token>
```

### JWT Payload
Your JWT token must contain:
```json
{
  "customer_id": 123,
  "exp": 1234567890,
  "iat": 1234567890
}
```

**Obtaining a Token**: Contact your account manager or use the provided authentication endpoint (not documented here as it's account-specific).

---

## 3. Text Generation (Chat)

Generate text responses using various AI models from OpenAI, Anthropic, Google, and others.

### 3.1 Available Providers & Models

#### **OpenAI**
- `gpt-5.2` - Latest reasoning model with image support (replaces deprecated `gpt-5`)
- `gpt-5.2-pro` - Premium reasoning model (high reasoning effort only)
- `gpt-5-mini` - Lightweight reasoning
- `gpt-5-nano` - Ultra-lightweight
- `gpt-4o` - GPT-4 Omni with vision
- `gpt-4o-mini` - Compact GPT-4 Omni
- `gpt-4.1` - GPT-4.1 with vision
- `gpt-4.1-mini` - Lightweight GPT-4.1
- `gpt-4.1-nano` - Ultra-compact GPT-4.1

#### **Anthropic**
- `claude-sonnet` - Claude Sonnet 4.5 (vision enabled)
- `claude-opus` - Claude Opus 4.5 (reasoning model)
- `claude-haiku` - Claude Haiku 4.5 (fast, vision enabled)
- `claude-code` - Claude Code via sidecar (special features)

#### **Google Gemini**
- `gemini-3-pro-preview` - Gemini 3 Pro Preview (reasoning, multimodal, audio input)
- `gemini-pro` - Gemini 2.5 Pro (reasoning, multimodal, audio input)
- `gemini-flash` - Gemini 3 Flash (fast reasoning, audio input)

#### **Groq**
- `gpt-oss-120b` - OpenAI GPT OSS 120B
- `llama-3.3-70b` - Llama 3.3 70B Versatile

#### **DeepSeek**
- `deepseek-chat` - Standard chat with vision
- `deepseek-reason` - DeepSeek Reasoner

#### **xAI (Grok)**
- `grok-4` - Grok 4 Latest
- `grok-4-mini` - Grok 4 Mini Fast (reasoning)

#### **Perplexity**
- `sonar-deep-research` - Deep research with citations
- `sonar-reason-pro` - Reasoning Pro with citations
- `sonar-reason` - Standard reasoning with citations
- `sonar-pro` - Pro model with citations
- `sonar` - Standard Sonar with citations

### 3.2 Endpoints

Text generation is available via HTTP (synchronous and SSE streaming) and WebSocket (bidirectional streaming).

#### **WS** `/chat/ws?token=<jwt>`
WebSocket streaming - bidirectional, supports agentic workflows, cancellation, and realtime mode detection.
See [Section 16: WebSocket Communication](#16-websocket-communication) for detailed event schemas.

#### **POST** `/chat/`
Non-streaming text generation - returns complete response.

**Request**:
```json
{
  "prompt": "What is the capital of France?",
  "customer_id": 123,
  "session_id": "optional-session-id",
  "settings": {
    "text": {
      "model": "gpt-5",
      "temperature": 0.7,
      "max_tokens": 2000,
      "reasoning_effort": "medium"
    }
  }
}
```

**Alternative Prompt Format** (chat history):
```json
{
  "prompt": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is the capital of France?"}
  ],
  ...
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "text": "The capital of France is Paris.",
    "model": "gpt-5",
    "provider": "openai",
    "reasoning": "Optional reasoning content if reasoning model",
    "citations": [],
    "session_id": "abc123",
    "metadata": {
      "finish_reason": "stop",
      "usage": {"prompt_tokens": 15, "completion_tokens": 20}
    },
    "tool_calls": [],
    "requires_tool_action": false
  }
}
```

#### **POST** `/chat/stream`
Server-Sent Events (SSE) streaming - receives chunks as they're generated.

**Request**: Same as `/chat/`

**Response**: SSE stream with JSON-formatted chunks:
```
data: {"type": "text_chunk", "content": "The capital"}
data: {"type": "text_chunk", "content": " of France"}
data: {"type": "text_chunk", "content": " is Paris."}
data: {"type": "tool_start", "content": {"name": "webSearch", "arguments": {"query": "Paris"}}}
# After the client completes the tool action and sends a follow-up request:
data: {"type": "text_completed", "content": ""}
data: {"type": "tts_not_requested", "content": ""}
```

#### **POST** `/chat/session-name`
Generate a descriptive session name from a conversation starter.

**Request**:
```json
{
  "prompt": "Help me plan a trip to Japan",
  "customer_id": 123,
  "settings": {
    "text": {
      "model": "gpt-4o-mini"
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "session_name": "Japan Trip Planning"
  }
}
```

### 3.3 Configuration Options

#### Text Settings
```json
{
  "text": {
    "model": "gpt-5",              // Required: Model identifier
    "temperature": 0.7,            // 0.0-2.0 (not all models support this)
    "max_tokens": 2000,            // Maximum tokens to generate
    "reasoning_effort": "medium",  // For reasoning models: "low", "medium", "high"
    "stream": true                 // Enable streaming (for /chat/stream)
  }
}
```

**Model Capabilities**:
- **Reasoning Models** (o3, o3-pro, claude-opus, gemini-pro, sonar-reason, etc.):
  - Support `reasoning_effort` parameter
  - May not support `temperature` control
  - Provide separate reasoning content in response

- **Vision Models** (gpt-4o, claude-sonnet, gemini-pro, etc.):
  - Accept image URLs or base64 encoded images in prompt
  - Format: `{"type": "image_url", "image_url": {"url": "https://..."}}`

- **Audio Input Models** (gemini models):
  - Can process audio files directly
  - See [Gemini Audio Direct Mode](#37-special-feature-gemini-audio-direct-mode)

### 3.4 Special Features

#### Citations (Perplexity Models)
Perplexity models automatically include web citations:
```json
{
  "text": "According to recent studies...",
  "citations": [
    {
      "url": "https://example.com/study",
      "title": "Recent Study on...",
      "snippet": "..."
    }
  ]
}
```

#### Reasoning Content (Reasoning Models)
Models with reasoning capabilities return separate reasoning:
```json
{
  "text": "The answer is 42.",
  "reasoning": "Let me think through this step by step: ..."
}
```

#### Claude Code Integration
Using `claude-code` model provides special capabilities:
- Tool usage tracking
- Session management
- Development assistance
- See [WebSocket Events](#1334-claude-code-events) for event details

### 3.5 Batch API

The Batch API enables cost-efficient, asynchronous processing of large volumes of text generation requests. Batch mode offers:

- **50% cost reduction** on all usage (input + output tokens)
- **Separate rate limits** from real-time API
- **Support for OpenAI, Anthropic, and Gemini** providers
- **24-hour turnaround** for most batches (often faster)

#### **POST** `/api/v1/batch`
Submit a batch of text generation requests for asynchronous processing.

**Request**:
```json
{
  "requests": [
    {
      "id": "request-1",
      "prompt": "What is the capital of France?",
      "settings": {
        "text": {
          "model": "gpt-4o-mini",
          "temperature": 0.7,
          "max_tokens": 1000
        }
      }
    },
    {
      "id": "request-2",
      "prompt": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing."}
      ],
      "settings": {
        "text": {
          "model": "claude-sonnet",
          "max_tokens": 2000
        }
      }
    }
  ],
  "customer_id": 123,
  "webhook_url": "https://your-app.com/webhook"  // Optional: for completion notifications
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "batch_id": "batch_abc123",
    "status": "processing",
    "estimated_completion": "2025-01-15T10:00:00Z",
    "request_count": 2
  }
}
```

#### **GET** `/api/v1/batch/{job_id}`
Check the status of a batch processing job.

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "batch_id": "batch_abc123",
    "status": "completed",  // "processing", "completed", "failed"
    "progress": 100,
    "completed_at": "2025-01-15T09:30:00Z",
    "request_count": 2,
    "successful_requests": 2,
    "failed_requests": 0
  }
}
```

#### **GET** `/api/v1/batch/{job_id}/results`
Retrieve the results of a completed batch.

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "batch_id": "batch_abc123",
    "status": "completed",
    "results": [
      {
        "id": "request-1",
        "success": true,
        "text": "The capital of France is Paris.",
        "model": "gpt-4o-mini",
        "provider": "openai",
        "usage": {"prompt_tokens": 15, "completion_tokens": 20}
      },
      {
        "id": "request-2",
        "success": true,
        "text": "Quantum computing uses quantum bits...",
        "model": "claude-sonnet",
        "provider": "anthropic",
        "usage": {"prompt_tokens": 25, "completion_tokens": 150}
      }
    ]
  }
}
```

#### **GET** `/api/v1/batch`
List all batch jobs for the authenticated user.

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "jobs": [
      {
        "job_id": "batch_abc123",
        "status": "completed",
        "request_count": 2,
        "created_at": "2025-01-15T08:00:00Z"
      }
    ],
    "total": 1
  }
}
```

#### **POST** `/api/v1/batch/{job_id}/cancel`
Cancel a batch job that is still processing.

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "job_id": "batch_abc123",
    "status": "cancelled",
    "cancelled_at": "2025-01-15T09:00:00Z"
  }
}
```

**Batch Limits**:
- Maximum 10,000 requests per batch
- Maximum 100 MB total request size
- Supported models: OpenAI (gpt-4o, gpt-4o-mini, etc.), Anthropic (claude-sonnet, claude-haiku), Gemini (gemini-pro, gemini-flash)

---

## 4. Audio Transcription (Speech-to-Text)

Convert audio files or audio streams to text.

### 4.1 Available Providers & Models

#### **Deepgram**
- `nova-3` - Latest Nova model (default)
- Real-time streaming, speaker diarization, 50+ languages

#### **OpenAI Whisper (Batch)**
- `whisper-1` - High accuracy, 98 languages, $0.006/min

#### **OpenAI Streaming**
- `gpt-4o-transcribe` - Real-time WebSocket transcription, $0.10/min
- `gpt-4o-mini-transcribe` - Cost-effective streaming, $0.05/min

#### **Google Gemini**
- `gemini-2.5-pro` - Production default for audio
- `gemini-2.5-flash` - Development default for audio
- Multimodal audio understanding, translation support

#### OpenAI Realtime Models (Speech-to-Speech)

| Model | Type | Features | Voices | Cost |
|-------|------|----------|--------|------|
| `gpt-realtime` | Realtime (GA) | Audio I/O, VAD, Function Calling | alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar | $0.10/min input, $0.20/min output |
| `gpt-realtime-mini` | Realtime (GA) | Audio I/O, VAD, Function Calling | alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar | $0.05/min input, $0.10/min output |
| `gpt-realtime-preview` | Deprecated | Use `gpt-realtime` instead | alloy, ash, ballad, coral, echo, sage, shimmer, verse | $0.10/min input, $0.20/min output |
| `gpt-4o-realtime-preview` | Deprecated | Use `gpt-realtime` instead | alloy, ash, ballad, coral, echo, sage, shimmer, verse | $0.10/min input, $0.20/min output |

**Use Cases**:
- Low-latency conversational AI
- Voice assistants and IVR agents
- Real-time translation with speech output

#### OpenAI Streaming Transcription Models

| Model | Type | Features | Cost |
|-------|------|----------|------|
| `gpt-4o-transcribe` | Transcription | Streaming, VAD | $0.10/min |
| `gpt-4o-mini-transcribe` | Transcription | Streaming, VAD | $0.05/min |

**Use Cases**:
- Live captions and meeting notes
- Contact centre analytics
- Voice memo transcription
- Real-time audio analysis

#### OpenAI Speech-to-Text (Batch)

| Model | Type | Features | Cost |
|-------|------|----------|------|
| `whisper-1` | STT | High accuracy, 98 languages | $0.006/min |

**Use Cases**:
- Batch audio file transcription
- Offline voice analytics
- Multi-language processing

### 4.2 Static Audio Transcription

#### **POST** `/api/v1/audio/transcribe`
Transcribe a complete audio file.

**Request**: `multipart/form-data`
```
Content-Type: multipart/form-data

file: <audio_file>           (Required: mp3, wav, m4a, webm, opus, etc.)
action: "transcribe"          (or "translate" to convert to English)
customerId: 123              (Required)
userSettings: {              (JSON string)
  "audio": {
    "provider": "deepgram",
    "language": "en",
    "enable_speaker_diarization": false
  }
}
```

**cURL Example**:
```bash
curl -X POST "https://your-backend.com/api/v1/audio/transcribe" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@recording.mp3" \
  -F "action=transcribe" \
  -F "customerId=123" \
  -F 'userSettings={"audio":{"provider":"deepgram","language":"en"}}'
```

**Response**:
```json
{
  "success": true,
  "message": "Transcription completed",
  "data": {
    "status": "completed",
    "result": "Hello, this is a transcription of the audio file.",
    "action": "transcribe",
    "provider": "deepgram",
    "filename": "recording.mp3",
    "language": "en"
  },
  "meta": {
    "filename": "recording.mp3",
    "provider": "deepgram",
    "language": "en",
    "metadata": {
      "duration_seconds": 15.3,
      "channels": 1
    }
  }
}
```

### 4.3 Streaming Audio Transcription

For real-time transcription, use WebSocket connection. See [WebSocket Audio Workflows](#1322-audio-workflow).

### 4.4 Configuration Options

```json
{
  "audio": {
    "provider": "deepgram",                    // Required
    "action": "transcribe",                    // or "translate"
    "language": "en",                          // Language code
    "model": "nova-2",                         // Provider-specific model
    "enable_speaker_diarization": false        // Identify speakers (Deepgram)
  }
}
```

**Supported Languages** (common codes):
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `pt` - Portuguese
- `ja` - Japanese
- `zh` - Chinese
- And 50+ more languages (provider-dependent)

---

## 5. Text-to-Speech (TTS)

Convert text to natural-sounding speech audio.

### 5.1 Available Providers & Models

#### **OpenAI TTS**
- **Models**: `gpt-4o-tts`, `gpt-4o-mini-tts` (default)
- **Legacy Models**: `tts-1` (fast), `tts-1-hd` (high quality)
- **Voices**: alloy, echo, fable, onyx, nova, shimmer
- **Formats**: mp3, opus, aac, flac, wav, pcm
- **Speed**: 0.25x - 4.0x

#### **ElevenLabs**
- **Models**: `eleven_monolingual_v1` (default), `eleven_turbo_v2`, custom cloned voices
- **Named Voices** (map to voice IDs): sherlock, naval, yuval, elon, hermiona, david, shaan, rick, morty, samantha, allison, amelia, danielle, hope, alice, bill, brian, eric, jessica, sarah, claire, anarita, bianca, will
- **Default Voice**: Rachel
- **Formats**: pcm, pcm_24000, mp3, mp3_44100, mp3_44100_128
- **Features**: Voice cloning, queue-driven WebSocket streaming, configurable chunk schedules, ultra-low latency

### 5.2 HTTP Endpoints

#### **POST** `/api/v1/tts/generate`
Synchronous TTS - returns complete audio file.

**Request**:
```json
{
  "text": "Hello, this is a test of text to speech.",
  "action": "generate",
  "customer_id": 123,
  "user_settings": {
    "tts": {
      "provider": "openai",
      "model": "tts-1-hd",
      "voice": "alloy",
      "format": "mp3",
      "speed": 1.0
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "message": {
    "status": "completed",
    "result": "<base64_encoded_audio_data>"
  },
  "data": {
    "provider": "openai",
    "model": "tts-1-hd",
    "voice": "alloy",
    "format": "mp3",
    "chunk_count": 1,
    "s3_url": "https://s3.../audio.mp3"
  }
}
```

#### **POST** `/api/v1/tts/stream`
HTTP streaming TTS - receive audio as it's generated.

**Request**: Same as `/api/v1/tts/generate`

**Response**: Binary audio stream with headers:
```
Content-Type: audio/mpeg
X-TTS-Provider: openai
X-TTS-Model: tts-1-hd
X-TTS-Voice: alloy

<binary audio data>
```

**Usage Example**:
```javascript
const response = await fetch('/api/v1/tts/stream', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    text: "Hello world",
    action: "generate",
    customer_id: 123,
    user_settings: { tts: { provider: "openai", voice: "alloy" } }
  })
});

const audioBlob = await response.blob();
const audioUrl = URL.createObjectURL(audioBlob);
audio.src = audioUrl;
```

#### **POST** `/api/v1/tts/generate` (Billing Query)
Query TTS usage/billing information (ElevenLabs).

**Request**:
```json
{
  "action": "billing",
  "user_settings": {
    "tts": {
      "provider": "elevenlabs"
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "character_count": 50000,
    "character_limit": 100000,
    "characters_remaining": 50000,
    "reset_date": "2025-11-01"
  }
}
```

### 5.3 Configuration Options

```json
{
  "general": {
    "return_test_data": false,    // Enable canned responses for smoke tests
    "save_to_s3": true            // Persist streamed audio to object storage
  },
  "tts": {
    "provider": "elevenlabs",     // "openai" or "elevenlabs"
    "model": "eleven_multilingual_v2",
    "voice": "alloy",
    "format": "pcm",              // ElevenLabs websocket format auto-selected when omitted
    "speed": 1.0,                  // Playback speed multiplier (OpenAI only)
    "tts_auto_execute": true,      // Start TTS automatically during chat streaming
    "streaming": true,             // Keep queue-based streaming enabled (default)
    "chunk_schedule": [120, 160, 220, 260],
    "instructions": "Conversational and upbeat"
  }
}
```

**Auto-execute streaming flags**:
- `tts_auto_execute`: When `true`, chat workflows duplicate each text chunk to the TTS queue and begin synthesis immediately. Disable to fall back to the post-processing TTS flow.
- `streaming`: Explicit `false` bypasses queue-based streaming even if `tts_auto_execute` is enabled (useful for providers that only support buffered mode).
- `chunk_schedule`: Optional list of four integers (in characters) that controls ElevenLabs WebSocket pacing. Leave unset to accept the provider default.
- `return_test_data`: Surfaces deterministic sample audio without contacting external providers—handy for contract tests.

**OpenAI Voices**:
- `alloy` - Neutral, balanced
- `echo` - Male, clear
- `fable` - British accent, expressive
- `onyx` - Deep male voice
- `nova` - Female, energetic
- `shimmer` - Female, warm

**Audio Formats** (OpenAI):
- `mp3` - Standard compression (default)
- `opus` - Low latency streaming
- `aac` - High quality
- `flac` - Lossless
- `wav` - Uncompressed
- `pcm` - Raw audio

### 5.4 Chat Auto-Execute Streaming TTS

When `settings.tts.tts_auto_execute` is enabled (default for first-party clients) the chat pipeline now synthesises speech in **parallel** with text generation. The flow mirrors the legacy backend latency profile:

1. `StreamingManager` duplicates each `text` chunk into a dedicated TTS queue while continuing to fan out events to the frontend.[F:docker/storage-backend/core/streaming/manager.py L15-L118]
2. `TTSOrchestrator` registers the queue and starts a background task that consumes the chunks as soon as they arrive.[F:docker/storage-backend/features/chat/services/streaming/tts_orchestrator.py L18-L170]
3. `TTSService.stream_from_text_queue` streams audio over the provider WebSocket, emitting metadata and optional S3 uploads without waiting for the full response.[F:docker/storage-backend/features/tts/service_stream_queue.py L1-L107]
4. ElevenLabs' `stream_from_text_queue` API yields base64 audio frames that are forwarded directly to the client while a buffer accumulates the complete waveform for archival storage.[F:docker/storage-backend/core/providers/tts/elevenlabs_websocket.py L56-L117]

**Event timeline (auto-execute enabled)**:
- `tts_started` → Announces provider/model/voice and includes the current duplicated text chunk count for UI progress bars.
- `audio_chunk` → Base64 PCM frames suitable for immediate playback.
- `tts_generation_completed` → Signals the last live chunk, including counts for telemetry.
- `tts_completed` → Final TTS completion signal for client state tracking.
- `custom_event` → `ttsFileUploaded` (optional) when persisted audio is available for later download.

If a provider does not advertise `supports_input_stream`, the service automatically drains the queue and falls back to buffered synthesis, ensuring compatibility with OpenAI's HTTP streaming mode.[F:docker/storage-backend/features/tts/service_stream_queue_helpers.py L58-L137]

**Provider support**:
- **ElevenLabs**: Full WebSocket streaming with configurable `chunk_schedule` and voice tuning parameters (`stability`, `similarity_boost`, `style`, `use_speaker_boost`).
- **OpenAI**: Continues to use HTTP streaming. Auto-execute still functions, but audio will begin once the text pipeline finishes.

**Use cases**: Low-latency conversational assistants, dictation playback, and accessibility scenarios where audio must start within a few hundred milliseconds of the first text chunk.

---

## 6. Image Generation

Generate images from text prompts using various AI models. Supports text-to-image and image-to-image workflows.

### 6.1 Available Providers & Models

#### **OpenAI (GPT-Image)**
- `gpt-image-1.5` - Latest model (default as of December 2025)
- `gpt-image-1` - Previous generation
- `gpt-image-1-mini` - Lightweight variant
- `dall-e-3`, `dall-e-2` - Legacy models (still supported)
- **Aliases**: `openai-1.5` → `gpt-image-1.5`, `openai-1` → `gpt-image-1`

#### **Flux (Black Forest Labs) - FLUX.2**
- `flux-2-pro` - Professional quality (default as of December 2025)
- `flux-2-max` - Highest quality with real-time grounding
- `flux-2-flex` - Flexible generation
- `flux-dev` - Legacy FLUX.1 development model
- `flux-pro-1.1`, `flux-pro-1.1-ultra` - Legacy FLUX.1 production
- `flux-kontext-pro` - Context-aware generation
- **Aliases**: `flux-pro` → `flux-2-pro`, `flux-max` → `flux-2-max`, `flux-flex` → `flux-2-flex`, `flux-1` → `flux-dev`
- **Image-to-image**: Supports transforming existing images via `image_url` parameter

#### **Stability AI**
- `core` - Stable Diffusion core model (default)
- `sd3.5` - Stable Diffusion 3.5
- `sd3` - Stable Diffusion 3
- `sdxl` - Legacy SDXL

#### **Google Gemini (Nano Banana)**
- `gemini-3-pro-image-preview` - Nano Banana Pro (up to 4K resolution)
- `gemini-2.5-flash-image` - Nano Banana (default)
- `gemini-2.0-flash` - Flash variant
- `imagen-4.0-generate-001` - Legacy Imagen API
- **Aliases**: `gemini-pro` → `gemini-3-pro-image-preview`, `nano-banana` → `gemini-2.5-flash-image`, `nano-banana-pro` → `gemini-3-pro-image-preview`

#### **xAI (Grok)**
- `grok-2-image` - Grok image generation

### 6.2 HTTP Endpoint

#### **POST** `/image/generate`
Generate an image from a text prompt, or transform an existing image.

**Request (Text-to-Image)**:
```json
{
  "prompt": "A serene mountain landscape at sunset with a crystal clear lake",
  "customer_id": 123,
  "save_to_db": true,
  "settings": {
    "image": {
      "provider": "flux",
      "model": "flux-2-pro",
      "width": 1024,
      "height": 1024,
      "quality": "medium"
    }
  }
}
```

**Request (Image-to-Image - Flux only)**:
```json
{
  "prompt": "Transform this into a watercolor painting style",
  "customer_id": 123,
  "image_url": "https://example.com/source-image.png",
  "save_to_db": true,
  "settings": {
    "image": {
      "provider": "flux",
      "model": "flux-2-pro",
      "width": 1024,
      "height": 1024
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "image_url": "https://s3.amazonaws.com/.../image.png",
    "provider": "openai",
    "model": "dall-e-3",
    "settings": {
      "size": "1024x1024",
      "quality": "hd",
      "style": "vivid"
    },
    "prompt": "A serene mountain landscape...",
    "revised_prompt": "A photorealistic mountain landscape..."
  }
}
```

**Alternative Response Format** (base64):
```json
{
  "image_url": "data:image/png;base64,iVBORw0KGgoAAAANSUh..."
}
```

### 6.3 Configuration Options

```json
{
  "image": {
    "provider": "flux",            // Provider: openai, flux, stability, gemini, xai
    "model": "flux-2-pro",         // Model identifier (see 6.1 for options)
    "width": 1024,                 // Image width (max 2048 for Flux)
    "height": 1024,                // Image height (max 2048 for Flux)
    "quality": "medium",           // Quality level
    "enabled": true                // Enable in workflows
  }
}
```

**OpenAI Settings**:
- **Sizes**: `256x256`, `512x512`, `1024x1024`, `1792x1024` (landscape), `1024x1792` (portrait)
- **Quality**: `standard`, `hd`, `low`, `medium`, `high`, `auto`
- **Style**: `natural`, `vivid`
- Uses Responses API with polling for new models (`gpt-image-1.5`)

**Flux Settings (FLUX.2)**:
- **Max dimensions**: Up to 2048x2048
- **guidance**: Guidance scale for generation (optional)
- **steps**: Number of generation steps (optional)
- **seed**: Reproducibility seed (optional)
- **prompt_upsampling**: Enhance prompt automatically (optional)
- **safety_tolerance**: Safety filtering level (optional)
- **Image-to-image**: Pass `image_url` in request for style transfer/modification

**Stability AI Settings**:
- **cfg_scale**: 0-35 (how closely to follow prompt, 7-15 recommended)
- **steps**: 10-150 (quality vs speed, 30-50 recommended)
- **negative_prompt**: What NOT to generate (optional)
- **style_preset**: Visual style preset (optional)
- **seed**: Reproducibility seed (optional)

**Gemini Settings (Nano Banana)**:
- **Aspect ratios**: 1:1 (square), 16:9 (landscape), 9:16 (portrait)
- Dual API system: Uses Imagen API for legacy models, Flash API for Nano Banana

**xAI Settings**:
- **background**: Background selection (optional)
- **moderation**: Content moderation toggle (optional)
- **style**: Art style (optional)
- **seed**: Reproducibility seed (optional)
- **Response formats**: `b64_json` (base64) or `url` (direct URL)

### 6.4 WebSocket Image Generation

Images can also be generated as part of chat workflows. See [WebSocket Image Workflow](#1325-image-workflow).

---

## 7. Video Generation

Generate videos from text or image prompts using multiple AI providers.

### 7.1 Available Providers & Models

#### **Google Gemini (Veo)**
- `veo-3.1-fast-generate-preview` - Fast generation (default, alias: `veo-3.1-fast`)
- `veo-3.1-generate-preview` - Quality generation (alias: `veo-3.1`, `veo-3.1-quality`)
- **Resolutions**: 720p, 1080p
- **Aspect Ratios**: 16:9, 9:16
- **Features**: Text-to-video, image-to-video, camera controls, person generation modes

#### **OpenAI (Sora)**
- `sora-2` - Latest Sora model
- **Durations**: 4, 8, 12 seconds
- **Sizes**: 1280x720, 720x1280, 1024x1792, 1792x1024
- **Features**: Text-to-video, image-to-video

#### **KlingAI** (NEW - Most Feature-Rich)
KlingAI offers the most comprehensive video generation capabilities with multiple model families:

**V1 Family** (Baseline):
- `kling-v1` - Base model
- `kling-v1-5` - Improved V1
- `kling-v1-6` - Multi-image support, best quality in V1 family

**V2 Family** (Improved Quality):
- `kling-v2-master` - Flagship V2
- `kling-v2-1` - Enhanced V2
- `kling-v2-1-master` - Enhanced flagship
- `kling-v2-5` - Latest V2
- `kling-v2-5-turbo` - Fast V2

**V2.6 Family** (Audio-Capable):
- `kling-v2-6` - Standard V2.6 with native audio
- `kling-v2-6-pro` - Professional V2.6 with native audio
- **Note**: Pro mode only (std mode not supported)
- **Unique Feature**: Native audio generation (dialogue, SFX, ambient sounds)

**Omni (O1) Family** (Unified Generation & Editing):
- `kling-o1` - Standard Omni
- `kling-o1-pro` - Professional Omni
- **Note**: Pro mode only
- **Unique Feature**: Multi-image references, unified generation + editing

**KlingAI Features**:
- **Durations**: 5 or 10 seconds per segment
- **Aspect Ratios**: 16:9, 9:16, 1:1
- **Modes**: `std` (standard, cost-effective) or `pro` (professional quality)
- **Generation Modes**: Text-to-video, image-to-video, multi-image-to-video (v1-6 only)
- **Video Extension**: Extend existing videos up to 180 seconds total
- **Avatar/Lip-Sync**: Create talking head videos from face images
- **Motion Brush**: Control specific regions with trajectories (up to 77 points)
- **Camera Control**: Predefined movements (simple, down_back, forward_up, etc.)
- **Native Audio**: V2.6/O1 models generate synchronized audio in single pass

### 7.2 HTTP Endpoints

#### **POST** `/video/generate`
Generate a video from a text prompt or image.

**Request** (Text-to-Video):
```json
{
  "prompt": "A serene ocean sunset with gentle waves",
  "customer_id": 123,
  "save_to_db": true,
  "settings": {
    "video": {
      "provider": "gemini",
      "model": "veo-3.1-fast",
      "duration_seconds": 5,
      "aspect_ratio": "16:9"
    }
  }
}
```

**Request** (Image-to-Video):
```json
{
  "prompt": "Gentle camera pan across the landscape",
  "customer_id": 123,
  "input_image_url": "https://s3.../reference.jpg",
  "settings": {
    "video": {
      "provider": "gemini",
      "model": "veo-3.1-quality",
      "duration_seconds": 10,
      "aspect_ratio": "9:16",
      "camera_motion": "pan_left"
    }
  }
}
```

**Request** (KlingAI with Audio):
```json
{
  "prompt": "A futuristic cityscape at night with flying cars",
  "customer_id": 123,
  "save_to_db": true,
  "settings": {
    "video": {
      "model": "kling-v2-6",
      "duration_seconds": 10,
      "aspect_ratio": "16:9",
      "mode": "pro",
      "enable_audio": true,
      "negative_prompt": "blurry, low quality"
    }
  }
}
```

**Request** (KlingAI Image-to-Video with Motion Brush):
```json
{
  "prompt": "A person dancing smoothly",
  "customer_id": 123,
  "input_image_url": "https://s3.../reference.jpg",
  "settings": {
    "video": {
      "model": "kling-v1-6",
      "duration_seconds": 5,
      "aspect_ratio": "9:16",
      "mode": "std",
      "dynamic_masks": [
        {
          "mask": "https://s3.../mask.png",
          "trajectories": [
            {"x": 0, "y": 0},
            {"x": 100, "y": 100},
            {"x": 200, "y": 50}
          ]
        }
      ]
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "video_url": "https://s3.amazonaws.com/.../video.mp4",
    "provider": "gemini",
    "model": "veo-3.1-fast",
    "duration": 5,
    "settings": {
      "aspect_ratio": "16:9",
      "duration_seconds": 5
    },
    "prompt": "A serene ocean sunset..."
  }
}
```

#### **POST** `/video/extend` (KlingAI Only)
Extend an existing video by 4-5 seconds.

**Request**:
```json
{
  "video_id": "task_12345",
  "prompt": "Continue with more action",
  "customer_id": 123,
  "settings": {
    "video": {
      "mode": "pro"
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "video_url": "https://s3.../extended_video.mp4",
    "video_id": "task_67890",
    "duration": 15,
    "provider": "klingai"
  }
}
```

**Notes**:
- Maximum total duration: 180 seconds (3 minutes)
- Extended videos can be extended again (chainable)
- Videos expire after 30 days

### 7.3 Configuration Options

```json
{
  "video": {
    "provider": "gemini",              // "gemini", "openai", or "klingai"
    "model": "veo-3.1-fast",          // Model identifier
    "duration_seconds": 5,             // 5 or 10 seconds (4, 8, 12 for Sora)
    "aspect_ratio": "16:9",            // "16:9", "9:16", "1:1"
    "camera_motion": "static",         // Camera movement (Gemini)
    "enabled": true,

    // KlingAI-specific options:
    "mode": "std",                     // "std" or "pro" (KlingAI)
    "negative_prompt": "...",          // What to avoid (KlingAI)
    "cfg_scale": 0.5,                  // Prompt adherence 0-1 (V1 only)
    "enable_audio": true,              // Generate audio (V2.6/O1 only)
    "camera_control": {                // Camera movement (KlingAI)
      "type": "simple",
      "config": {"horizontal": 5}
    },
    "static_mask": "url_or_base64",    // Single frame mask (KlingAI)
    "dynamic_masks": [...]             // Motion trajectories (KlingAI)
  }
}
```

**Aspect Ratios**:
- `16:9` - Landscape (YouTube, presentations)
- `9:16` - Portrait (TikTok, Instagram Stories)
- `1:1` - Square (Instagram posts)

**Camera Motion** (Gemini):
- `static` - No camera movement
- `pan_left`, `pan_right` - Horizontal panning
- `tilt_up`, `tilt_down` - Vertical tilting
- `zoom_in`, `zoom_out` - Zoom effects
- `dolly_forward`, `dolly_backward` - Depth movement

**Camera Control Types** (KlingAI):
- `simple` - Basic movement with horizontal/vertical/zoom/tilt/pan/roll
- `down_back`, `forward_up`, `left_turn`, `right_turn` - Preset movements

### 7.4 KlingAI Capability Matrix

| Feature | V1 | V2 | V2.6 | O1 |
|---------|----|----|------|----|
| Text-to-video | ✓ | ✓ | ✓ | ✓ |
| Image-to-video | ✓ | ✓ | ✓ | ✓ |
| Multi-image (2-4 images) | ✓ (v1-6) | | | |
| Video extension | ✓ | ✓ | ✓ | ✓ |
| Native audio | | | ✓ | ✓ |
| Avatar/lip-sync | ✓ | ✓ | ✓ | ✓ |
| Motion brush | ✓ | ✓ | ✓ | ✓ |
| Camera control | ✓ | ✓ | ✓ | ✓ |
| cfg_scale support | ✓ | | | |
| Standard mode | ✓ | ✓ | | |
| Pro mode | ✓ | ✓ | ✓ | ✓ |

### 7.5 Agentic Tool Integration

Video generation is available as an internal tool in agentic workflows:

**Tool**: `video_generation`
**Profiles**: `general`, `media`
**Models**: `veo` (default), `veo-quality`, `sora`, `kling`, `kling-v2`, `kling-audio`

Example prompt that triggers video generation:
> "Create a 10-second video of a cat playing with yarn"

The agent will automatically:
1. Select appropriate provider based on requirements
2. Generate the video
3. Upload to S3
4. Return URL in conversation

---

## 8. Chart Generation

Generate interactive data visualizations and diagrams from real data sources or generated content.

### 8.1 Available Chart Types

#### **Data Charts**
- **Bar Charts** - Categorical comparisons, discrete data
- **Line Charts** - Time-series trends, continuous data
- **Pie Charts** - Part-to-whole relationships, proportional data
- **Area Charts** - Cumulative trends, stacked data visualization
- **Scatter Plots** - Correlation analysis, individual data points

#### **Diagrams**
- **Mermaid Diagrams** - Flowcharts, sequence diagrams, ERDs, state diagrams

### 8.2 Data Sources

#### **Real Data**
- **Garmin Health Data** - Heart rate, steps, sleep, stress, calories, floors climbed, distance
- **Blood Test Data** - Glucose, cholesterol, hemoglobin, WBC, RBC, platelets, liver enzymes, vitamins
- **UFC Fighter Data** - Wins, losses, knockouts, takedowns (planned)

#### **Generated Data**
- **LLM-Generated** - Conceptual examples, synthetic data for illustrations

### 8.3 HTTP Endpoint

#### **POST** `/chat/` or `/chat/stream`
Charts are generated via the agentic workflow when the LLM detects visualization-appropriate requests.

**Example Request:**
```json
{
  "prompt": "Show me my heart rate trends over the past week",
  "customer_id": 123,
  "settings": {
    "text": {"model": "gpt-5"}
  }
}
```

**Response:** Chart appears inline in chat via WebSocket events

### 8.4 WebSocket Events

#### **chartGenerationStarted**
```json
{
  "type": "custom_event",
  "eventType": "chartGenerationStarted",
  "content": {
    "chart_type": "line",
    "title": "Heart Rate Trends"
  }
}
```

#### **chartGenerated**
```json
{
  "type": "custom_event",
  "eventType": "chartGenerated",
  "content": {
    "chart_id": "uuid-string",
    "chart_type": "line",
    "title": "Your Heart Rate - Last 7 Days",
    "data": {
      "datasets": [{"label": "Heart Rate", "data": [72, 75, 71, ...]}],
      "labels": ["Dec 3", "Dec 4", "Dec 5", ...]
    },
    "options": {"interactive": true, "show_legend": true},
    "data_source": "garmin_db",
    "generated_at": "2025-12-10T12:45:00Z"
  }
}
```

#### **chartError**
```json
{
  "type": "custom_event",
  "eventType": "chartError",
  "content": {
    "error": "No data available for specified time range",
    "chart_type": "line"
  }
}
```

### 8.5 Chart Data Schemas

Detailed payload structures for each chart type in the `chartGenerated` event.

#### **Bar Charts**
```javascript
{
  "chart_type": "bar",
  "title": "Programming Languages by Popularity",
  "data": {
    "datasets": [{
      "label": "Score",
      "data": [95, 88, 82],
      "color": "#3776AB"  // Single color for series
    }],
    "labels": ["Python", "JavaScript", "Java"]
  },
  "options": {
    "colors": ["#3776AB", "#F7DF1E", "#FB923C"],  // Per-bar colors
    "show_legend": true
  }
}
```

#### **Line Charts**
```javascript
{
  "chart_type": "line",
  "title": "Heart Rate Trends (30 days)",
  "data": {
    "datasets": [
      {
        "label": "Avg Heart Rate",
        "data": [72, 75, 71, 78, 76, ...],  // One per day
        "color": "#EF4444"
      }
    ],
    "labels": ["Dec 1", "Dec 2", "Dec 3", ...]  // Date labels
  },
  "options": {
    "interactive": true,
    "show_grid": true,
    "x_axis_label": "Date",
    "y_axis_label": "BPM"
  }
}
```

#### **Area Charts**
```javascript
{
  "chart_type": "area",
  "title": "Activity Breakdown",
  "data": {
    "datasets": [
      {"label": "Walking", "data": [30, 45, 20], "color": "#10B981"},
      {"label": "Running", "data": [0, 20, 15], "color": "#3B82F6"}
    ],
    "labels": ["Mon", "Tue", "Wed"]
  },
  "options": {
    "stacked": true,
    "show_legend": true
  }
}
```

#### **Pie Charts**
```javascript
{
  "chart_type": "pie",
  "title": "Sleep Stage Distribution",
  "data": {
    "datasets": [{
      "label": "Duration",
      "data": [120, 60, 240, 20]  // Minutes in each stage
    }],
    "labels": ["REM", "Deep", "Light", "Awake"]
  },
  "options": {
    "colors": ["#8B5CF6", "#3B82F6", "#10B981", "#F59E0B"],
    "show_legend": true
  }
}
```

#### **Scatter Plots**
```javascript
{
  "chart_type": "scatter",
  "title": "Steps vs Sleep Quality",
  "data": {
    "datasets": [{
      "label": "Data Points",
      "data": [[8000, 8.5], [12000, 7.2], [6000, 6.8]],  // [x, y] pairs
      "color": "#F59E0B"
    }],
    "labels": []  // Not used for scatter
  },
  "options": {
    "x_axis_label": "Daily Steps",
    "y_axis_label": "Sleep Score",
    "interactive": true
  }
}
```

#### **Mermaid Diagrams**
```javascript
{
  "chart_type": "mermaid",
  "title": "User Authentication Flow",
  "mermaid_code": `
    flowchart LR
      A[User] -->|Enter Credentials| B{Valid?}
      B -->|Yes| C[Check 2FA]
      B -->|No| D[Show Error]
      C -->|Enabled| E[Send Code]
      C -->|Disabled| F[Login Success]
      E -->|Verified| F
  `,
  "options": {
    "interactive": true
  }
}
```

### 8.6 Configuration Options

```json
{
  "chart": {
    "enabled": true,                    // Enable chart generation
    "default_provider": "recharts",     // React: recharts, Kotlin: vico/chartjs
    "interactive": true,                // Enable hover tooltips, zoom
    "show_legend": true,                // Display legend
    "colors": ["#3B82F6", "#10B981"],   // Custom color palette
    "max_data_points": 100              // Limit for performance
  }
}
```

### 8.7 Frontend Support

#### **React Web**
- **Library:** Recharts for data charts, Mermaid.js for diagrams
- **Features:** Responsive, interactive, dark theme support
- **Location:** `storage-react/src/components/Visualization/`

#### **Kotlin Android**
- **Libraries:** Vico (native) for line/area/scatter, Chart.js WebView for bar/pie/mermaid
- **Features:** Native performance, WebView fallbacks for complex charts
- **Location:** `storage-kotlin/app/src/main/java/biz/atamai/betterai/visualization/`

### 8.8 Use Cases

**Health Analytics:**
- "Show my sleep duration over the past month" → Line chart
- "Compare my stress levels by time of day" → Bar chart
- "Break down my last night's sleep stages" → Pie chart

**Medical Data:**
- "Display my glucose levels for the past 3 months" → Line chart
- "Compare my cholesterol changes year-over-year" → Bar chart

**Conceptual Diagrams:**
- "Create a flowchart for user authentication" → Mermaid flowchart
- "Show me a sequence diagram for API communication" → Mermaid sequence

---

## 9. Realtime Audio Conversations

Bidirectional audio streaming for real-time conversations with AI.

### 8.1 Available Providers & Models

#### **OpenAI Realtime API**
- `gpt-realtime` - GA model (recommended, $0.10/min input, $0.20/min output)
- `gpt-realtime-mini` - Cost-effective GA model ($0.05/min input, $0.10/min output)
- `gpt-realtime-preview` - Deprecated, use `gpt-realtime` instead
- `gpt-4o-realtime-preview` - Deprecated, use `gpt-realtime` instead

#### **Google Gemini Live**
- `gemini-2.0-flash-exp` - Default Gemini Live model
- Aliases: `gemini-live`, `gemini-realtime`, `gemini-pro-realtime`

### 8.2 WebSocket Connection

#### **WS** `/chat/ws?token=<jwt>&mode=realtime`

**Connection Flow**:
1. Connect with query parameters:
   ```
   wss://your-backend.com/chat/ws?token=YOUR_JWT&mode=realtime
   ```
2. Backend sends `websocket_ready` event
3. Send initial payload with `requestType: "realtime"`
4. Start sending audio chunks
5. Receive audio responses in real-time

**Initial Payload**:
```json
{
  "requestType": "realtime",
  "settings": {
    "realtime": {
      "model": "gpt-realtime",
      "voice": "alloy",
      "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500
      }
    }
  }
}
```

**Sending Audio**:
```json
{
  "type": "audio",
  "audio": "<base64_encoded_pcm_audio>"
}
```

**Receiving Audio**:
```json
{
  "type": "audio",
  "content": "<base64_encoded_audio>"
}
```

### 8.3 Configuration Options

```json
{
  "realtime": {
    "model": "gpt-realtime",
    "voice": "alloy",
    "turn_detection": {
      "type": "server_vad",            // Voice Activity Detection
      "threshold": 0.5,                // VAD sensitivity (0.0-1.0)
      "prefix_padding_ms": 300,        // Audio before speech starts
      "silence_duration_ms": 500       // Silence to end turn
    }
  }
}
```

**Voices** (OpenAI Realtime):
- `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer`, `verse`, `marin`, `cedar` (10 total)

### 8.4 Features

- **Turn Detection**: Automatic detection when user finishes speaking
- **Interrupt Handling**: User can interrupt AI mid-response
- **Function Calling**: AI can call functions during conversation (OpenAI)
- **Low Latency**: Typical response time < 500ms

---

## 9. Browser Automation

Automate web interactions through natural language—navigate websites, extract information, fill forms, and complete multi-step tasks using AI-powered browser control.

### 9.1 Overview

**How It Works**:
- User submits chat message requesting browser automation (e.g., "Go to GitHub and find the most starred repo")
- Agentic workflow detects browser_automation tool via LLM function calling
- BrowserAutomationService executes task against isolated Chromium instance in dedicated container
- Agent runs up to 100 steps with configurable LLM provider
- Results extracted and returned to LLM for final response synthesis

**Key Capabilities**:
- **Navigate & Interact** - Click links, fill forms, submit data, scroll pages
- **Extract Information** - Read content, tables, structured data from web pages
- **Download Files** - Retrieve documents and media from websites
- **Multi-step Workflows** - Complete complex tasks requiring reasoning across multiple pages
- **Visual Monitoring** - Watch execution via VNC (localhost:5900) during development

**Architecture**:
- Frontend triggers via natural chat → Agentic workflow detects tool need → Backend delegates to isolated browser container → Container runs browser-use Agent → Results returned over WebSocket events

### 9.2 Configuration

**Backend Environment** (`storage-backend` container):
```bash
BROWSER_AUTOMATION_URL=http://browser-automation:8001  # Container endpoint
BROWSER_TASK_TIMEOUT=300                               # Task timeout (seconds, max 1800)
BROWSER_DEFAULT_LLM_PROVIDER=gemini                   # Default LLM (gemini|openai|anthropic)
BROWSER_DEFAULT_LLM_MODEL=gemini-flash-latest         # Default model
BROWSER_DEFAULT_MAX_STEPS=100                         # Max agent steps (1-500)
```

**Browser Automation Container Environment**:
```bash
GOOGLE_API_KEY=...         # For ChatGoogle (Gemini)
OPENAI_API_KEY=...         # For ChatOpenAI
ANTHROPIC_API_KEY=...      # For ChatAnthropic
BROWSER_USE_API_KEY=...    # For ChatBrowserUse (3-5x faster)
```

### 9.3 User Settings

Control browser automation behavior per-request via `settings.browser_automation`:

```json
{
  "enabled": true|false,
  "llm_provider": "gemini|openai|anthropic",
  "llm_model": "model-name",
  "use_vision": "auto|true|false",
  "max_steps": 100,
  "timeout": 300,
  "generate_gif": false,
  "window_width": 1920,
  "window_height": 1080,
  "headless": false
}
```

### 9.4 WebSocket Events

Browser automation sends real-time status events:

```json
// Task started
{"type": "custom_event", "eventType": "browserAutomationStarted",
 "content": {"taskId": "browser_abc123", "task": "Go to github.com..."}}

// Task completed successfully
{"type": "custom_event", "eventType": "browserAutomationCompleted",
 "content": {"taskId": "browser_abc123", "success": true,
             "result": "Found 5 repos...", "executionTime": 45.2, "stepsUsed": 12}}

// Task failed
{"type": "custom_event", "eventType": "browserAutomationError",
 "content": {"taskId": "browser_abc123", "error": "Task timeout", "stepReached": 45}}
```

### 9.5 LLM Provider Selection

| Provider | Speed | Quality | Cost | Vision | Recommended For |
|----------|-------|---------|------|--------|-----------------|
| **Gemini** | Fast | Good | Free tier | Yes | Default - best balance |
| **ChatBrowserUse** | Fastest | Excellent | $$ | Yes | Performance-critical tasks |
| **OpenAI** | Fast | Excellent | $$$ | Yes | Complex reasoning |
| **Anthropic** | Very Fast | Good | $ | No | Budget-constrained |

### 9.6 HTTP Endpoint (Internal)

Browser automation is triggered automatically via agentic workflow when LLM requests the `browser_automation` tool. Direct HTTP calls to the browser-automation container are not part of the public API surface.

**Health Check**:
```
GET http://browser-automation:8001/health
```

**List Providers**:
```
GET http://browser-automation:8001/providers
```

### 9.7 Implementation Details

- **Tool Location**: `core/tools/internal/browser_automation.py`
- **Service**: `features/browser/service.py`
- **Container Image**: `betterai/browser-automation:latest`
- **VNC Display**: `:99` (port 5900 for monitoring)
- **Container Timeout**: Enforced 30-1800 second range

**For comprehensive details, see**: `DocumentationApp/browser-automation-handbook.md`

---

## 10.5 Proactive Agent (Sherlock & Bugsy)

A multi-character AI framework powered by Claude Code CLI that enables proactive, personalized AI assistants. The system supports multiple AI personas with different capabilities and communication styles.

### 10.5.1 Overview

**Architecture** (v2.0 Unified WebSocket):
- Frontend apps (Kotlin/React) send messages via **unified WebSocket** (`/chat/ws?mode=proactive`)
- Backend saves message, pushes to all connected clients (multi-client sync), queues to SQS
- Poller scripts on development server consume messages and invoke Claude Code CLI
- Responses posted back to backend via internal API
- Push notifications delivered to all connected WebSocket clients
- Multi-client synchronization with deduplication ensures consistency

**Characters**:

| Character | Persona | Capabilities |
|-----------|---------|--------------|
| **Sherlock** | Detective with Sherlock Holmes personality | Proactive heartbeats (15-min check-ins), personality files, memory persistence, weather/calendar integration |
| **Bugsy** | Development assistant | Codebase Q&A, Claude Code with full edit permissions, no heartbeats |

**Key Features**:
- Real-time streaming responses via WebSocket
- Session persistence with Claude Code `--resume` flag
- Multi-character routing via SQS with character filtering
- WebSocket push notifications for instant message delivery
- Offline resilience with database persistence and sync
- **TTS Auto-Execute**: Streaming audio responses when enabled (ElevenLabs)

### 10.5.2 HTTP Endpoints

#### **GET** `/api/v1/proactive-agent/health`
Health check for the proactive agent service.

**Response**:
```json
{
  "status": "healthy",
  "service": "proactive_agent",
  "active_ws_connections": 2
}
```

#### **GET** `/api/v1/proactive-agent/session`
Get or create a session for a user.

**Query Parameters**:
- `user_id` (required): User ID

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "uuid-session-id",
    "claude_session_id": "claude-code-session-id-or-null"
  }
}
```

#### **GET** `/api/v1/proactive-agent/messages/{session_id}/poll`
Poll for new messages (responses from agent).

**Query Parameters**:
- `user_id` (required): User ID
- `since` (optional): ISO 8601 timestamp to get messages since

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": "message-id",
      "content": "The weather in Barcelona is sunny, 12°C...",
      "created_at": "2025-12-14T10:01:00Z"
    }
  ]
}
```

#### **POST** `/api/v1/proactive-agent/notifications`
Receive proactive notification from heartbeat script or poller (server-to-server, internal).

**Headers**:
- `X-Internal-Api-Key`: Internal API key for server-to-server auth

**Request**:
```json
{
  "user_id": 1,
  "session_id": "uuid",
  "content": "Memory usage at 78%. Not critical yet, but worth noting.",
  "direction": "heartbeat",
  "source": "heartbeat",
  "is_heartbeat_ok": false,
  "ai_character_name": "sherlock"
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "message_id": 12345,
    "pushed_via_ws": true
  }
}
```

#### **WS** `/api/v1/proactive-agent/ws/poller-stream`
WebSocket endpoint for Python poller to stream NDJSON from Claude Code (server-to-server, internal).

**Authentication**: `X-Internal-Api-Key` header

**Init Message** (Poller → Backend):
```json
{
  "type": "init",
  "user_id": 1,
  "session_id": "uuid",
  "ai_character_name": "sherlock",
  "source": "text",
  "tts_settings": {"voice": "sherlock", "tts_auto_execute": true},
  "claude_session_id": "existing-session-id-or-null"
}
```

**Streaming**: After init, poller sends raw NDJSON lines from Claude CLI. Backend parses and emits events to frontends.

**Close Messages**:
- `{"type": "complete", "exit_code": 0}` - Stream finished successfully
- `{"type": "error", "code": "...", "message": "..."}` - Claude error (rate limit, auth, etc.)

### 10.5.3 WebSocket Unified Interface {#1053-websocket-unified-interface}

#### **WS** `/chat/ws?mode=proactive`
Unified WebSocket for all proactive agent communication (send + receive).

**Query Parameters**:
- `mode=proactive` (required): Enable proactive mode
- `user_id` (required): User ID
- `session_id` (required): Session ID
- `token` (required): JWT authentication token

**Client → Server Messages**:

| Type | Purpose | Payload |
|------|---------|---------|
| `send_message` | Send message to character | `{"type": "send_message", "content": "...", "source": "text", "ai_character_name": "sherlock", "tts_settings": {...}}` |
| `pong` | Response to ping | `{"type": "pong"}` |
| `sync` | Request missed messages | `{"type": "sync", "last_seen_at": "2025-12-14T10:00:00Z"}` |

**Server → Client Messages**:

| Type | Purpose |
|------|---------|
| `connected` | Connection established, includes `ping_interval` |
| `ping` | Keepalive (every 30s) |
| `message_sent` | ACK for send_message: `{"db_message_id": "...", "session_id": "...", "queued": true}` |
| `send_error` | Error for send_message: `{"error": "Message too long"}` |
| `notification` | Message from agent or multi-client sync |
| `stream_start` | Streaming response begun |
| `text_chunk` | Content chunk during streaming |
| `thinking_chunk` | Reasoning chunk during streaming |
| `stream_end` | Streaming complete, includes `message_id` and `audio_file_url` |
| `sync_complete` | Response to sync request with missed messages |
| `tts_started` | TTS audio streaming begun (when `tts_settings` enabled) |
| `audio_chunk` | Base64-encoded PCM audio chunk |
| `tts_completed` | TTS audio streaming finished |

**Send Message Example**:
```javascript
// Send message to Sherlock
websocket.send(JSON.stringify({
  type: "send_message",
  content: "Hey Sherlock, what's the weather?",
  source: "text",
  ai_character_name: "sherlock"
}));

// Server responds with ACK:
// {"type": "message_sent", "db_message_id": "abc-123", "session_id": "uuid", "queued": true}
```

**Multi-Client Synchronization**: When a message is sent from one client, it's pushed to ALL connected clients for that user. The sending client should implement deduplication using the `db_message_id`.

### 10.5.4 Configuration

**Environment Variables**:
- `AWS_SQS_PROACTIVE_AGENT_QUEUE_URL`: SQS queue URL for message delivery

**Message Limits**:
- User messages: 1-30,000 characters
- Agent notifications: 1-30,000 characters

### 10.5.5 Implementation Details

- **Feature Location**: `features/proactive_agent/`
- **WebSocket Handler**: `features/chat/services/proactive_handler.py`
- **Connection Registry**: `core/connections/proactive_registry.py`
- **Audio Intercept**: `features/proactive_agent/audio_intercept.py`
- **Streaming Registry**: `features/proactive_agent/streaming_registry.py` (TTS session management)
- **Database**: Reuses `ChatSessionsNG`/`ChatMessagesNG` with `ai_character_name` filter

### 10.5.6 TTS Auto-Execute

When `tts_settings` is included in the `send_message` payload, Sherlock's response will be simultaneously converted to streaming audio using ElevenLabs.

**TTS Settings Structure**:
```json
{
  "tts_settings": {
    "voice": "sherlock",
    "model": "eleven_monolingual_v1",
    "tts_auto_execute": true
  }
}
```

**Flow**:
1. Client sends `send_message` with `tts_settings`
2. Message queued to SQS with TTS configuration
3. Poller invokes Claude Code, streams `text_chunk` events
4. Backend starts TTS orchestration on `stream_start`
5. Text chunks duplicated to ElevenLabs TTS queue
6. Audio chunks streamed to client via `audio_chunk` events
7. On `stream_end`, audio file URL included in response

**Events** (when TTS enabled):
- `tts_started` - TTS streaming begun
- `audio_chunk` - Base64-encoded PCM audio chunks
- `tts_completed` - TTS streaming finished
- `stream_end` - Includes `audio_file_url` for persisted audio

**For comprehensive details, see**: `DocumentationApp/sherlock-technical-handbook.md`

---

## 10. Semantic Search (Context Enhancement)

Enhance user prompts with intelligent context retrieval using a dual-index architecture supporting both message-level and session-level search. When enabled, the system automatically enriches prompts with relevant content from previous conversations, creating a powerful "memory" system for AI interactions.

### 10.1 Overview

**How It Works**:
1. All chat messages and session summaries are indexed in real-time across dual indexes (message-level + session-level)
2. When you send a new message, the system performs hybrid search (dense + sparse vectors) based on the selected mode
3. Results are fused using Reciprocal Rank Fusion (RRF) for optimal ranking
4. Relevant context is prepended to your prompt before sending to the AI
5. The AI receives enriched context, enabling it to reference past discussions and maintain continuity

**Key Features**:
- **Dual-index architecture**: Message-level (individual messages) + Session-level (conversation summaries)
- **Hybrid search**: Combines dense vectors (OpenAI embeddings) + sparse vectors (BM25) with RRF fusion
- **6 search modes**: Hybrid, Semantic, Keyword, Session Hybrid, Session Semantic, Multi-Tier
- Automatic indexing of all messages and session summaries in real-time
- Advanced filtering (tags, dates, message types, sessions)
- Token budget management to prevent context overflow
- Non-blocking, resilient architecture with circuit breakers
- Zero-cost storage (Qdrant Cloud free 1GB tier)

**Technology Stack**:
- **Vector Database**: Qdrant Cloud (free 1GB tier)
- **Embeddings**: OpenAI `text-embedding-3-small` (384 dimensions)
- **Search Algorithm**: Hybrid search with Reciprocal Rank Fusion (RRF)
- **Cost**: ~$0.02 per 10,000 messages indexed

### 10.2 Search Modes and Configuration

Semantic search supports 6 different modes optimized for various query types and use cases. Configuration is done via the `semantic` object in `userSettings`.

#### Search Modes Overview

| Mode | Description | Best For | Speed | Supports Filters |
|------|-------------|----------|-------|------------------|
| **hybrid** (default) | Dense + sparse vectors with RRF fusion | General-purpose, mixed queries | ~250ms | All message filters |
| **semantic** | Dense vectors only, cosine similarity | Conceptual questions, precision | ~200ms | All message filters |
| **keyword** | Sparse vectors only (BM25) | Exact terms, code, IDs | ~50ms | All message filters |
| **session_hybrid** | Session summaries, hybrid search | Topic discovery, conversations | ~180ms | Limit only |
| **session_semantic** | Session summaries, semantic search | Precise topic search | ~150ms | Limit only |
| **multi_tier** | Sessions → Messages drill-down | Comprehensive topic discovery | ~300ms | top_sessions, messages_per_session |

**Basic Enable/Disable**:
```json
{
  "requestType": "text",
  "prompt": "What did we discuss about the project last week?",
  "userSettings": {
    "semantic": {
      "enabled": true  // Enable with default hybrid mode
    }
  }
}
```

**With Custom Mode and Parameters**:
```json
{
  "userSettings": {
    "semantic": {
      "enabled": true,
      "search_mode": "hybrid",     // Mode: hybrid, semantic, keyword, session_hybrid, session_semantic, multi_tier
      "limit": 15,                 // Return up to 15 results (default: 10)
      "threshold": 0.7             // Similarity threshold for semantic modes (default: 0.7, ignored in hybrid/keyword)
    }
  }
}
```

### 10.3 Search Parameters and Filters

Configure search behavior with parameters and filters. Support varies by mode - see the mode comparison table in section 10.2.

#### Core Parameters

**Limit**: Maximum number of results to return (default: 10, range: 1-50)
```json
{
  "semantic": {
    "limit": 20
  }
}
```

**Threshold**: Minimum similarity score for semantic modes (default: 0.7, range: 0.0-1.0, ignored in hybrid/keyword modes)
```json
{
  "semantic": {
    "threshold": 0.8  // Higher precision, fewer results
  }
}
```

**Multi-Tier Parameters**: For `multi_tier` mode only
```json
{
  "semantic": {
    "search_mode": "multi_tier",
    "top_sessions": 3,        // Sessions to search first (default: 3)
    "messages_per_session": 5  // Messages to retrieve per session (default: 5)
  }
}
```

#### Filters (Message-Level Modes Only)

Session-level modes (session_hybrid, session_semantic, multi_tier) ignore message-level filters.

**Filter by Message Type**: Search user messages, AI responses, or both
```json
{
  "semantic": {
    "message_type": "user"  // "user", "assistant", "both" (default)
  }
}
```

**Filter by Tags**: Search within specific topic categories
```json
{
  "semantic": {
    "tags": ["work", "project-alpha"]  // Array of tags
  }
}
```

**Filter by Date Range**: Search messages from specific time periods
```json
{
  "semantic": {
    "date_range": {
      "start": "2024-11-01",  // YYYY-MM-DD format
      "end": "2024-11-30"     // Inclusive
    }
  }
}
```

**Filter by Session IDs**: Search within specific conversation threads
```json
{
  "semantic": {
    "session_ids": ["session-abc123", "session-def456"]
  }
}
```

#### Combined Configuration Example

```json
{
  "prompt": "What action items did I mention for the project?",
  "userSettings": {
    "semantic": {
      "enabled": true,
      "search_mode": "hybrid",
      "message_type": "user",
      "tags": ["work", "project-alpha"],
      "date_range": {
        "start": "2024-11-01",
        "end": "2024-11-30"
      },
      "limit": 20,
      "threshold": 0.8
    }
  }
}
```

### 10.4 WebSocket Events

When semantic context is added to your prompt, the backend sends a notification event:

**Event Format**:
```json
{
  "type": "custom_event",
  "content": {
    "type": "semanticContextAdded",
    "resultCount": 5,              // Number of messages found
    "tokensUsed": 150,             // Tokens used for context
    "timestamp": "2024-11-15T12:34:56.789Z"
  }
}
```

**With Filters Applied**:
```json
{
  "type": "custom_event",
  "content": {
    "type": "semanticContextAdded",
    "resultCount": 3,
    "tokensUsed": 120,
    "timestamp": "2024-11-15T12:34:56.789Z",
    "filtersApplied": {
      "message_type": "user",
      "tags": ["work"],
      "date_range": {
        "start": "2024-11-01",
        "end": "2024-11-30"
      }
    }
  }
}
```

**Frontend Usage**:
```javascript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'customEvent' &&
      msg.content.type === 'semanticContextAdded') {
    // Display notification
    showNotification(
      `Using context from ${msg.content.resultCount} previous messages`
    );

    // Show filters if applied
    if (msg.content.filtersApplied) {
      console.log('Filters:', msg.content.filtersApplied);
    }
  }
};
```

### 10.6 Context Format

When semantic search finds relevant messages, they're formatted and prepended to your prompt:

**Example Context Added**:
```
<semantic_context>
You are continuing a conversation. Here is relevant context from previous discussions:

## Session: "Project Planning" (2024-11-10)
**You asked:** "What should be our Q4 priorities?"
**AI suggested:** "Focus on product stability and user onboarding improvements..."

## Session: "Architecture Review" (2024-11-08)
**You said:** "We need to refactor the authentication system"
**AI responded:** "Consider implementing OAuth 2.0 with refresh tokens..."

</semantic_context>

[Your original prompt follows...]
```

**Token Budget**:
- Maximum context tokens: 4000 (configurable)
- System automatically truncates if too many results
- Most relevant results prioritized (highest similarity scores first)
- Uses `tiktoken` for accurate token counting

### 10.6 HTTP Endpoints

Semantic search integrates automatically with all chat endpoints when enabled via `userSettings`.

#### **POST** `/chat/`
Non-streaming with semantic context:

**Request**:
```json
{
  "prompt": "What did we discuss about the API design?",
  "customer_id": 123,
  "settings": {
    "text": {"model": "gpt-5"}
  },
  "userSettings": {
    "semantic": {
      "enabled": true,
      "search_mode": "hybrid",
      "tags": ["api", "design"],
      "limit": 10
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "code": 200,
  "data": {
    "text": "Based on our previous discussions about REST API design...",
    "model": "gpt-5",
    "session_id": "abc123",
    "metadata": {
      "semantic_context_added": true,
      "semantic_result_count": 5,
      "semantic_tokens_used": 150
    }
  }
}
```

#### **POST** `/chat/stream`
SSE streaming with semantic context:

**Request**: Same as `/chat/`

**Response Events**:
```
data: {"type": "custom_event", "eventType": "semanticContextAdded", "content": {"resultCount": 5}}
data: {"type": "text_chunk", "content": "Based on our previous"}
data: {"type": "text_chunk", "content": " discussions..."}
data: {"type": "text_completed", "content": ""}
data: {"type": "tts_not_requested", "content": ""}
```

### 10.7 WebSocket Integration

Semantic search works seamlessly in all WebSocket workflows:

**Text Workflow with Semantic Search**:
```javascript
const ws = new WebSocket('wss://your-backend.com/chat/ws?token=YOUR_JWT');

ws.onopen = () => {
  // Wait for websocket_ready events...
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  if (msg.type === 'websocket_ready' && msg.session_id) {
    // Send payload with semantic search enabled
    ws.send(JSON.stringify({
      requestType: 'text',
      prompt: 'What were our Q4 goals?',
      settings: {
        text: {model: 'gpt-5'}
      },
      userSettings: {
        semantic: {
          enabled: true,
          search_mode: 'session_hybrid',
          tags: ['work', 'planning'],
          message_type: 'both',
          limit: 15,
          threshold: 0.7
        }
      }
    }));
  }

  // Handle semanticContextAdded event
  if (msg.type === 'customEvent' &&
      msg.content.type === 'semanticContextAdded') {
    console.log(`Found ${msg.content.resultCount} relevant messages`);
    console.log(`Using ${msg.content.tokensUsed} tokens for context`);
  }

  // Handle text chunks
  if (msg.type === 'text') {
    appendText(msg.content);
  }
};
```

**Audio Workflow with Semantic Search**:
```json
{
  "requestType": "audio",
  "settings": {
    "audio": {
      "provider": "deepgram",
      "action": "transcribe"
    },
    "text": {
      "model": "gpt-4o"
    }
  },
  "userSettings": {
    "semantic": {
      "enabled": true,
      "search_mode": "keyword",
      "limit": 10,
      "threshold": 0.1
    }
  }
}
```

### 10.8 Performance & Costs

**Latency by Mode**:
- **Keyword**: ~50ms (no embeddings)
- **Semantic**: ~200ms (dense vectors only)
- **Hybrid**: ~250ms (dense + sparse fusion)
- **Session Semantic**: ~150ms (session summaries)
- **Session Hybrid**: ~180ms (session summaries)
- **Multi-Tier**: ~300ms (session search + message drill-down)
- P95 latency: <1 second for all modes
- Total timeout: 15 seconds (configurable)
- Non-blocking indexing: 0ms impact on message creation

**Cost Breakdown**:
- **Embeddings**: $0.02 per 1 million tokens (OpenAI text-embedding-3-small)
- **Storage**: Free (Qdrant Cloud 1GB tier + MySQL for summaries)
- **Example**: 10,000 messages ≈ 1M tokens ≈ $0.02 one-time setup cost

**Token Usage**:
- Average message: ~100 tokens
- Average context: 150-500 tokens per search
- Automatic budget management prevents overflow (4000 token limit)

**Rate Limits**:
- Default: 60 searches per minute per customer
- Configurable via backend settings
- Graceful degradation on rate limit (returns empty results)

### 10.11 Best Practices

#### Tagging Strategy

Implement consistent tagging for better search results:

```javascript
// Good: Consistent categories
tags: ["work", "project-alpha", "architecture"]

// Avoid: Random, one-off tags
tags: ["misc", "stuff", "random-thought"]
```

**Recommended Categories**:
- **Topics**: work, personal, research, learning
- **Projects**: project-alpha, project-beta
- **Types**: decision, question, action-item, idea

#### Search Optimization

**Start broad, then narrow**:
```javascript
// Step 1: Broad search
{threshold: 0.6, limit: 20}

// Step 2: If too many results, add filters
{threshold: 0.75, tags: ["work"], limit: 10}

// Step 3: Precise search
{threshold: 0.85, tags: ["work"], messageType: "user"}
```

#### Context Management

**Adjust limit based on query type**:
- Simple questions: `limit: 5-10`
- Research queries: `limit: 15-30`
- Specific recall: `limit: 3-5` with high threshold

#### Frontend UX

**Show users when context is being used**:
```javascript
if (msg.content.type === 'semanticContextAdded') {
  showBadge(`📚 Using context from ${msg.content.resultCount} messages`);

  if (msg.content.filtersApplied?.tags) {
    showBadge(`🏷️ Tags: ${msg.content.filtersApplied.tags.join(', ')}`);
  }
}
```

### 10.12 Troubleshooting

**No results returned**:
```json
// Try lowering threshold
{"threshold": 0.6}

// Remove filters
{"semantic": {"limit": 20}}  // No other filters
```

**Too many irrelevant results**:
```json
// Increase threshold
{"threshold": 0.85}

// Add filters
{"tags": ["specific-topic"], "messageType": "user"}
```

**Context not appearing**:
- Check `semantic_enabled: true` in `userSettings.general`
- Verify messages are indexed (check backend logs)
- Ensure `SEMANTIC_SEARCH_ENABLED=true` in backend environment

**High latency**:
- Reduce `limit` to fetch fewer results
- Increase `threshold` for more selective search
- Check backend configuration timeouts

### 10.13 Technical Details

**Architecture**:
- **Provider**: Qdrant Cloud (vector database)
- **Embeddings**: OpenAI `text-embedding-3-small` (384 dimensions)
- **Indexing**: Automatic, non-blocking background tasks
- **Search**: Cosine similarity with metadata filtering

**Automatic Indexing**:
- All messages indexed on creation/edit
- Uses `asyncio.create_task()` for non-blocking operation
- Includes message content, metadata (customer_id, session_id, tags, type)
- Failures logged but don't block message creation

**Circuit Breaker**:
- Protects against cascading failures
- Auto-recovery after timeout
- Graceful degradation on provider issues

**Token Budget**:
- Uses `tiktoken` for accurate token counting
- Maximum context: 4000 tokens (configurable)
- Results truncated intelligently if over budget
- Prioritizes highest similarity scores

### 10.14 Configuration Reference

**Complete Settings Schema**:
```json
{
  "userSettings": {
    "general": {
      "semantic_enabled": true
    },
    "semantic": {
      "limit": 10,
      "threshold": 0.7,
      "messageType": "user|assistant|both",
      "tags": ["tag1", "tag2"],
      "dateRange": {
        "start": "YYYY-MM-DD",
        "end": "YYYY-MM-DD"
      },
      "sessionIds": ["session-id-1", "session-id-2"]
    }
  }
}
```

**Backend Environment Variables**:
```bash
# Master switches
SEMANTIC_SEARCH_ENABLED=true          # Enable search
SEMANTIC_INDEXING_ENABLED=true        # Enable indexing

# Qdrant connection
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=chat_messages

# Search parameters
SEMANTIC_SEARCH_DEFAULT_LIMIT=10
SEMANTIC_SEARCH_DEFAULT_THRESHOLD=0.7
SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS=4000

# Timeouts
SEMANTIC_SEARCH_TIMEOUT=10.0
SEMANTIC_TOTAL_TIMEOUT=15.0
```

**📖 For complete documentation, see**:
- `DocumentationApp/semantic-search-handbook.md` - Full developer guide
- `DocumentationApp/semantic-search-settings-guide.md` - Detailed settings reference

---

## 11. Health Data (Garmin)

Access and analyze Garmin fitness and health metrics.

### 11.1 Available Datasets

- **Activity** - Steps, distance, calories, heart rate
- **Sleep** - Duration, stages (REM, deep, light), quality
- **Wellness** - Stress, body battery, respiration

### 11.2 HTTP Endpoint

#### **GET** `/api/v1/garmin/analysis/overview`
Retrieve aggregated Garmin health data.

**Query Parameters**:
- `customer_id` (required) - User identifier
- `start_date` (optional) - ISO date (e.g., `2025-01-01`)
- `end_date` (optional) - ISO date
- `include_optimized` (optional) - Boolean, default `true`
- `datasets` (optional) - Array of dataset names

**Example**:
```
GET /api/v1/garmin/analysis/overview?customer_id=123&start_date=2025-01-01&end_date=2025-01-31&datasets=activity,sleep
```

**cURL Example**:
```bash
curl "https://your-backend.com/api/v1/garmin/analysis/overview?customer_id=123&start_date=2025-01-01" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response**:
```json
{
  "success": true,
  "message": "Retrieved Garmin analysis overview",
  "data": {
    "activity": [
      {
        "date": "2025-01-15",
        "steps": 12534,
        "distance_meters": 8932,
        "calories": 2345,
        "active_minutes": 67,
        "heart_rate_avg": 72,
        "heart_rate_max": 145
      }
    ],
    "sleep": [
      {
        "date": "2025-01-15",
        "duration_hours": 7.5,
        "deep_sleep_minutes": 98,
        "light_sleep_minutes": 234,
        "rem_sleep_minutes": 118,
        "awake_minutes": 12,
        "sleep_score": 82
      }
    ],
    "wellness": [
      {
        "date": "2025-01-15",
        "stress_avg": 35,
        "body_battery_max": 95,
        "body_battery_min": 22,
        "respiration_rate": 14
      }
    ]
  },
  "meta": {
    "customer_id": 123,
    "query": {
      "start_date": "2025-01-01",
      "end_date": "2025-01-31"
    },
    "datasets": ["activity", "sleep", "wellness"],
    "total_days": 31
  }
}
```

---

## 10. Blood Test Data

Access and manage blood test results.

### 12.1 HTTP Endpoint

#### **GET** `/api/v1/blood/tests`
List blood test records with optional filtering.

**Query Parameters**:
- `start_date` (optional) - ISO date
- `end_date` (optional) - ISO date
- `category` (optional) - Test category (e.g., "Glucose", "Cholesterol")

**Example**:
```
GET /api/v1/blood/tests?start_date=2024-01-01&category=Glucose
```

**Response**:
```json
{
  "success": true,
  "message": "Retrieved blood tests",
  "data": {
    "items": [
      {
        "id": 1,
        "test_date": "2025-01-15",
        "result_value": "5.2",
        "result_unit": "mmol/L",
        "reference_range": "3.9-5.6",
        "category": "Glucose",
        "test_name": "Fasting Blood Glucose",
        "short_explanation": "Blood sugar level after fasting",
        "long_explanation": "Measures glucose levels after 8-12 hours of fasting..."
      },
      {
        "id": 2,
        "test_date": "2025-01-15",
        "result_value": "180",
        "result_unit": "mg/dL",
        "reference_range": "<200",
        "category": "Cholesterol",
        "test_name": "Total Cholesterol",
        "short_explanation": "Total cholesterol in blood",
        "long_explanation": "Sum of all cholesterol types..."
      }
    ],
    "total_count": 2,
    "latest_test_date": "2025-01-15"
  },
  "meta": {
    "total_count": 2,
    "latest_test_date": "2025-01-15",
    "filters": {
      "start_date": "2024-01-01",
      "category": "Glucose"
    }
  }
}
```

---

## 11. UFC Fighter Data

Access UFC fighter information and manage subscriptions.

### 14.1 HTTP Endpoints

#### **POST** `/api/v1/ufc/fighters`
Create a fighter record.

**Request**:
```json
{
  "name": "Jon Jones",
  "weight_class": "Heavyweight",
  "record": "27-1-0"
}
```

#### **POST** `/api/v1/ufc/fighters/queue`
Queue a fighter for asynchronous data enrichment.

**Request**:
```json
{
  "full_name": "Jon Jones",
  "weight_class": "Heavyweight"
}
```

#### **POST** `/api/v1/ufc/subscriptions`
Create a subscription to follow a fighter.

**Request**:
```json
{
  "fighter_id": 123
}
```

#### **GET** `/api/v1/ufc/subscriptions`
List user subscriptions.

---

## 12. File Upload

Upload files for use in chat workflows (audio, images, documents).

### 12.1 HTTP Endpoint

#### **POST** `/api/v1/storage/upload`
Upload a file to S3 storage.

**Request**: `multipart/form-data`
```
file: <file>                    (Required)
category: "audio|image|video|document"
action: "upload"
customerId: 123
```

**Supported File Types**:
- **Audio**: mp3, wav, m4a, opus, webm, mpeg, mpga, pcm
- **Image**: jpg, jpeg, png, gif, webp
- **Video**: mp4, webm
- **Documents**: pdf, txt

**cURL Example**:
```bash
curl -X POST "https://your-backend.com/api/v1/storage/upload" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "file=@document.pdf" \
  -F "category=document" \
  -F "action=upload" \
  -F "customerId=123"
```

**Response**:
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "data": {
    "url": "https://s3.amazonaws.com/bucket/123/document.pdf",
    "result": "https://s3.amazonaws.com/bucket/123/document.pdf",
    "filename": "document.pdf"
  },
  "meta": {
    "category": "document",
    "action": "upload",
    "extension": "pdf",
    "content_type": "application/pdf"
  }
}
```

---

## 13. WebSocket Communication

WebSocket endpoints provide real-time streaming for chat, audio, and TTS workflows.

### 13.1 Connection & Authentication

#### **WS** `/chat/ws?token=<jwt>`

**Connection**:
```javascript
const ws = new WebSocket('wss://your-backend.com/chat/ws?token=YOUR_JWT');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Event:', message.type, message.content);
};
```

**Connection Flow**:
1. Client connects with JWT token
2. Backend sends: `{"type": "websocket_ready", "content": "Backend ready", "version": "2.0"}`
3. Backend authenticates and sends: `{"type": "websocket_ready", "content": "Backend ready", "session_id": "abc123"}`
4. Client sends initial payload
5. Backend processes and streams events
6. Completion events sent: `text_completed` + `tts_completed` (or `tts_not_requested`)
7. Connection remains open for reuse

### 15.2 Workflow Types

WebSocket supports multiple workflow types based on `requestType`:

#### 13.2.1 Text Workflow
**requestType**: `"text"` (default)

**Initial Payload**:
```json
{
  "requestType": "text",
  "prompt": "What is quantum computing?",
  "settings": {
    "text": {
      "model": "gpt-5",
      "temperature": 0.7
    },
    "tts": {
      "enabled": false
    }
  }
}
```

**Events Received**:
1. `websocket_ready` (x2)
2. `working`
3. `custom_event` → `aiTextModelInUse`
4. `text_chunk` (multiple chunks)
5. `tool_start` (only when a provider pauses to request a tool action)
6. `text_completed` *(emitted after the tool call round-trip finishes)*
7. `tts_started` *(only when `tts_auto_execute` streaming is enabled)*
8. `audio_chunk` (multiple chunks, only when streaming TTS is active)
9. `tts_generation_completed` *(streaming only)*
10. `tts_completed` or `tts_not_requested`
11. `custom_event` → `ttsFileUploaded` *(optional; emitted when persisted audio is available)*

**Completion Model**: Clients track two flags (`textCompleted` + `ttsCompleted`) and consider the workflow complete when both are true.

#### 13.2.2 Audio Workflow
**requestType**: `"audio"`

Stream audio chunks for transcription, then generate text response.

**Initial Payload**:
```json
{
  "requestType": "audio",
  "settings": {
    "audio": {
      "provider": "deepgram",
      "action": "transcribe",
      "language": "en"
    },
    "text": {
      "model": "gpt-4o"
    }
  }
}
```

**Send Audio Chunks**:
```json
{
  "type": "audio",
  "audio": "<base64_encoded_pcm_audio>"
}
```

**Signal Recording Finished**:
```json
{
  "type": "RecordingFinished"
}
```

**Events Received**:
1. `websocket_ready` (x2)
2. `working`
3. `transcription` (incremental chunks)
4. `text_chunk` (AI response chunks)
5. `tts_started` *(streaming TTS only)*
6. `audio_chunk` (TTS audio chunks, if enabled)
7. `tts_generation_completed` *(streaming TTS only)*
8. `tts_completed` or `tts_not_requested`
9. `custom_event` → `ttsFileUploaded` *(optional)*
10. `text_completed`

**Completion Model**: Clients track two flags (`textCompleted` + `ttsCompleted`) and consider the workflow complete when both are true.

#### 13.2.3 Audio Direct Workflow
**requestType**: `"audio_direct"`

Send audio directly to Gemini multimodal model without separate transcription step.

**Initial Payload**:
```json
{
  "requestType": "audio_direct",
  "settings": {
    "text": {
      "model": "gemini-flash"
    }
  }
}
```

**Send Audio Chunks**: Same as audio workflow

**Events**: Similar to audio workflow but no separate `transcription` events

#### 13.2.4 TTS Workflow
**requestType**: `"tts"`

Convert text to speech only (no text generation).

**Initial Payload**:
```json
{
  "requestType": "tts",
  "prompt": "Hello, this is a test of text to speech.",
  "settings": {
    "tts": {
      "provider": "elevenlabs",
      "voice": "alloy"
    }
  }
}
```

**Events Received**:
1. `websocket_ready` (x2)
2. `working`
3. `text_not_requested`
4. `tts_started`
5. `audio_chunk` (multiple chunks)
6. `tts_generation_completed`
7. `tts_completed`
8. `custom_event` → `ttsFileUploaded` *(optional)*

**Completion Model**: Clients receive `text_not_requested` + `tts_completed` to signal workflow completion.

#### 13.2.5 Image Workflow
**requestType**: `"image"`

Generate an image and optionally include it in chat context.

**Initial Payload**:
```json
{
  "requestType": "image",
  "prompt": "A beautiful mountain landscape",
  "settings": {
    "image": {
      "provider": "openai",
      "model": "dall-e-3",
      "size": "1024x1024",
      "enabled": true
    },
    "text": {
      "model": "gpt-4o"
    }
  }
}
```

**Events Received**:
1. `websocket_ready` (x2)
2. `working`
3. `custom_event` → `imageGenerationStarted`
4. `custom_event` → `image` (with image URL)
5. `text_chunk` (optional description/commentary)
6. `text_completed`
7. `tts_not_requested`

**Completion Model**: Clients receive `text_completed` + `tts_not_requested` to signal workflow completion.

#### 13.2.6 Realtime Workflow
**requestType**: `"realtime"`

Bidirectional audio streaming. See [Realtime Audio Conversations](#8-realtime-audio-conversations).

### 15.3 Event Types Reference

#### 13.3.1 Connection Events

**`websocket_ready`**
Sent twice: once from switchboard, once after authentication.

```json
{
  "type": "websocket_ready",
  "content": "Backend ready",
  "version": "2.0",
  "session_id": "abc123"  // Only in second emission
}
```

**`working`**
Acknowledgement that workflow started processing.

```json
{
  "type": "working",
  "content": "Processing your request"
}
```

#### 13.3.2 Content Events

**`text_chunk`**
Streaming text chunks from AI model.

```json
{
  "type": "text_chunk",
  "content": "This is a chunk of generated text"
}
```

**`tool_start`**
Provider paused generation to request an external tool action. Clients must execute the tool and resume the conversation before
`text_completed` is emitted.

```json
{
  "type": "tool_start",
  "content": {
    "name": "webSearch",
    "arguments": {"query": "latest headlines"}
  }
}
```

**`thinking_chunk`**
Reasoning content from reasoning models.

```json
{
  "type": "thinking_chunk",
  "content": "Step-by-step reasoning content"
}
```

**`audio_chunk`**
Audio chunk data (base64 encoded).

```json
{
  "type": "audio_chunk",
  "content": "iVBORw0KGgoAAAANSUhEUgAA..."
}
```

**`tts_started`**
Sent once when queue-based streaming begins. Includes provider/model metadata and current text chunk duplication count.

```json
{
  "type": "tts_started",
  "content": {
    "provider": "elevenlabs",
    "model": "eleven_multilingual_v2",
    "voice": "alloy",
    "format": "pcm_24000",
    "textChunkCount": 3
  }
}
```

**`tts_generation_completed`**
Emitted after the final streaming chunk is delivered.

```json
{
  "type": "tts_generation_completed",
  "content": {
    "provider": "elevenlabs",
    "model": "eleven_multilingual_v2",
    "voice": "alloy",
    "format": "pcm_24000",
    "audioChunkCount": 14,
    "textChunkCount": 7
  }
}
```

**`transcription`**
Transcribed text from audio input.

```json
{
  "type": "transcription",
  "content": "Hello, this is transcribed audio"
}
```

**`translation`**
Translated audio content (to English).

```json
{
  "type": "translation",
  "content": "Hello, this is translated text"
}
```

#### 13.3.3 Completion Events (Dual-Flag Model)

Text and TTS complete independently. Clients track two boolean flags:

```javascript
let textCompleted = false;
let ttsCompleted = false;

// On text_completed or text_not_requested → textCompleted = true
// On tts_completed or tts_not_requested → ttsCompleted = true
// Workflow complete when BOTH are true
```

**1. `text_completed` or `text_not_requested`** *(`text_completed` is deferred while any `tool_start` is awaiting a client response)*
```json
{"type": "text_completed", "content": ""}
// OR
{"type": "text_not_requested", "content": ""}
```

**2. `tts_completed` or `tts_not_requested`**
```json
{"type": "tts_completed", "content": ""}
// OR
{"type": "tts_not_requested", "content": ""}
```

*Streaming note*: When `tts_auto_execute` is active, expect `tts_started` and `tts_generation_completed` events before the final `tts_completed` marker.

**Frontend Implementation Note**: Your client should track both flags and consider the workflow complete when `textCompleted && ttsCompleted` is true. The old `complete` and `fullProcessComplete` events have been removed.

#### 13.3.4 Claude Code Events

**`claudeSession`**
Session metadata from Claude Code sidecar.

```json
{
  "type": "claudeSession",
  "content": {
    "sessionId": "session_abc123",
    "metadata": {...}
  }
}
```

**`claudeToolUse`**
Tool usage notification.

```json
{
  "type": "claudeToolUse",
  "content": {
    "tool": "read_file",
    "input": {
      "path": "/path/to/file.py"
    }
  }
}
```

**`claudeEvent`**
General Claude events.

```json
{
  "type": "claudeEvent",
  "content": {...}
}
```

**Custom Event Format** - `claudeCodeFinalResult`:
```json
{
  "type": "custom_event",
  "eventType": "claudeCodeFinalResult",
  "content": {
    "summary": "Completed code analysis",
    "toolsUsed": ["read_file", "grep"],
    "filesModified": 3
  }
}
```

#### 13.3.5 Custom Events

**`customEvent`**
Container for specialized event data.

```json
{
  "type": "custom_event",
  "eventType": "specificEventType",
  "content": {...}
}
```

**Custom Event Types**:

**1. `aiTextModelInUse`** - Model discovery
```json
{
  "type": "custom_event",
  "content": {
    "type": "aiTextModelInUse",
    "message": "aiTextModelReceived",
    "aiTextModel": "gpt-5",
    "provider": "openai"
  }
}
```

For Claude Code:
```json
{
  "type": "custom_event",
  "content": {
    "type": "aiTextModelInUse",
    "message": "aiTextModelReceived",
    "aiTextModel": "claude-code",
    "provider": "anthropic",
    "actualModel": "claude-sonnet-4.5"
  }
}
```

**2. `image`** - Image generation result

Started:
```json
{
  "type": "custom_event",
  "content": {
    "type": "image",
    "message": "imageGenerationStarted"
  }
}
```

Generated:
```json
{
  "type": "custom_event",
  "content": {
    "type": "image",
    "message": "imageGenerated",
    "imageUrl": "https://s3.../image.png",
    "generatedBy": "openai",
    "sessionId": "abc123",
    "localMessageId": "msg_456",
    "imageGenerationSettings": "{...}",
    "imageGenerationRequest": "{...}"
  }
}
```

**3. `citations`** - Web search citations (Perplexity models)
```json
{
  "type": "custom_event",
  "content": {
    "type": "citations",
    "message": "citationsReceived",
    "citations": "[{\"url\": \"...\", \"title\": \"...\"}]",
    "sessionId": "abc123",
    "localMessageId": "msg_456"
  }
}
```

**4. `reasoning`** - Reasoning content
```json
{
  "type": "custom_event",
  "content": {
    "type": "reasoning",
    "message": "reasoningReceived",
    "reasoning": "Full reasoning text...",
    "sessionId": "abc123",
    "localMessageId": "msg_456"
  }
}
```

**5. `textTimings`** - Performance metrics
```json
{
  "type": "custom_event",
  "eventType": "textTimings",
  "content": {
    "textRequestSentTime": 1234567890.123,
    "textFirstResponseTime": 1234567891.456,
    "textFirstTokenLatency": 1.333
  }
}
```

**6. `promptEnhanced`** - Clarification workflow enhanced prompt
```json
{
  "type": "custom_event",
  "eventType": "promptEnhanced",
  "content": {
    "original_prompt": "...",
    "enhanced_prompt": "..."
  }
}
```

**7. `clarificationQuestions`** - AI requests clarification
```json
{
  "type": "custom_event",
  "eventType": "clarificationQuestions",
  "content": {
    "questions": [
      "What size would you like?",
      "What color scheme do you prefer?"
    ]
  }
}
```

**8. `textGenerationCompleted`** - Final summary
```json
{
  "type": "custom_event",
  "eventType": "textGenerationCompleted",
  "content": {
    "full_response": "Complete generated text",
    "metadata": {...}
  }
}
```

**9. `ttsFileUploaded`** - Persisted audio ready for download
```json
{
  "type": "custom_event",
  "eventType": "ttsFileUploaded",
  "content": {
    "provider": "elevenlabs",
    "model": "eleven_multilingual_v2",
    "voice": "alloy",
    "format": "mp3",
    "audioChunkCount": 18,
    "textChunkCount": 9,
    "url": "https://s3.../tts/audio.mp3"
  }
}
```

#### 13.3.6 Error Events

**`error`**
Error occurred during processing.

```json
{
  "type": "error",
  "content": "Error message describing what went wrong",
  "stage": "validation",  // validation|text|stt|tts|image|video
  "session_id": "abc123"
}
```

**Error Stages**:
- `validation` - Input validation failed
- `text` - Text generation error
- `stt` - Speech-to-text error
- `tts` - Text-to-speech error
- `image` - Image generation error
- `video` - Video generation error

#### 13.3.7 Control Events

**Client → Server**:

**`ping`** - Heartbeat check
```json
{"type": "ping"}
```

**`close_session`** - Request session termination
```json
{"type": "close_session"}
```

**Server → Client**:

**`pong`** - Heartbeat response
```json
{
  "type": "pong",
  "timestamp": "2025-10-30T12:34:56.789Z"
}
```

**`heartbeat`** - Keep-alive signal
```json
{"type": "heartbeat"}
```

### 15.4 Complete WebSocket Example

**JavaScript Client**:
```javascript
// Connect
const ws = new WebSocket('wss://your-backend.com/chat/ws?token=YOUR_JWT');

// Track completion state (dual-flag model)
let textCompleted = false;
let ttsCompleted = false;

function checkCompletion() {
  if (textCompleted && ttsCompleted) {
    console.log('Workflow fully complete');
    onWorkflowComplete();
  }
}

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);

  switch(msg.type) {
    case 'websocket_ready':
      if (msg.session_id) {
        // Authenticated, send initial payload
        ws.send(JSON.stringify({
          requestType: 'text',
          prompt: 'Explain quantum computing',
          settings: {
            text: { model: 'gpt-5' },
            tts: { enabled: false }
          }
        }));
      }
      break;

    case 'working':
      console.log('Processing started');
      break;

    case 'text_chunk':
      // Append text chunk to UI
      appendText(msg.content);
      break;

    case 'thinking_chunk':
      // Display reasoning content
      showReasoning(msg.content);
      break;

    case 'tts_started':
      updateTtsStatus('streaming', msg.content);
      break;

    case 'tts_generation_completed':
      updateTtsStatus('completed', msg.content);
      break;

    case 'audio_chunk':
      // Play audio chunk
      playAudio(msg.content);
      break;

    case 'text_completed':
    case 'text_not_requested':
      textCompleted = true;
      checkCompletion();
      break;

    case 'tts_completed':
    case 'tts_not_requested':
      ttsCompleted = true;
      checkCompletion();
      break;

    case 'custom_event': {
      const eventType = msg.eventType ?? msg.content?.type;
      if (eventType === 'aiTextModelInUse') {
        console.log('Using model:', msg.content.aiTextModel);
      } else if (eventType === 'ttsFileUploaded') {
        cacheTtsDownload(msg.content.url, msg.content);
      }
      break;
    }

    case 'error':
      console.error('Error at stage', msg.stage, ':', msg.content);
      handleError(msg);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Connection closed');
};
```

**Python Client**:
```python
import websockets
import json
import asyncio

async def chat_websocket():
    uri = "wss://your-backend.com/chat/ws?token=YOUR_JWT"

    async with websockets.connect(uri) as ws:
        # Wait for ready signals
        ready_count = 0
        while ready_count < 2:
            msg = json.loads(await ws.recv())
            if msg['type'] == 'websocket_ready':
                ready_count += 1
                if msg.get('session_id'):
                    # Authenticated, send payload
                    await ws.send(json.dumps({
                        'requestType': 'text',
                        'prompt': 'Explain quantum computing',
                        'settings': {
                            'text': {'model': 'gpt-5'}
                        }
                    }))

        # Track completion state (dual-flag model)
        text_completed = False
        tts_completed = False

        async for message in ws:
            msg = json.loads(message)

            if msg['type'] == 'text_chunk':
                print(msg['content'], end='', flush=True)

            elif msg['type'] == 'tts_started':
                content = msg.get('content', {})
                print(
                    f"\nTTS streaming via {content.get('provider')}"
                    f" ({content.get('voice')})"
                )

            elif msg['type'] == 'tts_generation_completed':
                content = msg.get('content', {})
                print(
                    f"\nTTS chunks: {content.get('audioChunkCount')}"
                    f" (text chunks: {content.get('textChunkCount')})"
                )

            elif msg['type'] in ['text_completed', 'text_not_requested']:
                text_completed = True
                if text_completed and tts_completed:
                    break

            elif msg['type'] in ['tts_completed', 'tts_not_requested']:
                tts_completed = True
                if text_completed and tts_completed:
                    break

            elif msg['type'] == 'custom_event':
                event_type = msg.get('eventType') or msg.get('content', {}).get('type')
                if event_type == 'aiTextModelInUse':
                    print(f"\nUsing model: {msg['content'].get('aiTextModel')}")
                elif event_type == 'ttsFileUploaded':
                    print(f"\nTTS download available: {msg['content'].get('url')}")

            elif msg['type'] == 'error':
                print(f"\nError: {msg['content']}")
                break

asyncio.run(chat_websocket())
```

---

## 14. Error Handling

### 14.1 HTTP Error Responses

**Standard Error Format**:
```json
{
  "success": false,
  "code": 400,
  "message": "Validation error: Invalid model name",
  "data": {
    "errors": [
      {
        "field": "settings.text.model",
        "message": "Model 'invalid-model' not found",
        "code": "INVALID_MODEL"
      }
    ]
  }
}
```

**HTTP Status Codes**:
- `400` - Bad Request (validation errors, malformed input)
- `401` - Unauthorized (missing or invalid JWT token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error (backend error)
- `502` - Bad Gateway (provider API error)
- `503` - Service Unavailable (provider temporarily down)

### 14.2 WebSocket Error Events

**Error Event Format**:
```json
{
  "type": "error",
  "content": "Detailed error message",
  "stage": "text",
  "session_id": "abc123",
  "error_code": "PROVIDER_ERROR"
}
```

**Common Error Codes**:
- `VALIDATION_ERROR` - Input validation failed
- `AUTHENTICATION_ERROR` - Token invalid or expired
- `PROVIDER_ERROR` - AI provider API error
- `RATE_LIMIT_ERROR` - Provider rate limit exceeded
- `TIMEOUT_ERROR` - Request timeout
- `CONFIGURATION_ERROR` - Invalid settings
- `INSUFFICIENT_CREDITS` - Account balance too low

### 14.3 Retry Strategy

**Recommended Retry Logic**:
```javascript
async function retryRequest(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error.code === 429) {
        // Rate limit - exponential backoff
        await sleep(Math.pow(2, i) * 1000);
      } else if (error.code >= 500) {
        // Server error - retry
        await sleep(1000);
      } else {
        // Client error - don't retry
        throw error;
      }
    }
  }
  throw new Error('Max retries exceeded');
}
```

---

## 15. Rate Limits & Best Practices

### 15.1 Rate Limits

**HTTP Endpoints**:
- Default: 100 requests/minute per customer
- Burst: 20 requests/second

**WebSocket**:
- 10 concurrent connections per customer
- No message rate limit (provider-dependent)

**Provider-Specific**:
- OpenAI: Varies by model and tier
- Anthropic: Varies by plan
- See provider documentation for details

### 15.2 Best Practices

#### Optimize Token Usage
- Use appropriate models for tasks (don't use o3-pro for simple queries)
- Set reasonable `max_tokens` limits
- Cache responses when possible

#### Efficient Streaming
- Use WebSocket for multiple requests to avoid reconnection overhead
- Reuse connections when possible
- Handle backpressure on frontend to avoid buffer overflow

#### Error Handling
- Always check for `error` events in WebSocket streams
- Implement exponential backoff for retries
- Log errors with session IDs for debugging

#### Audio Processing
- For streaming audio: Send chunks of 100-500ms
- Use appropriate sample rates (16kHz for most providers)
- Encode audio as base64 for WebSocket transmission

#### Image/Video Generation
- Generate images asynchronously and poll for results
- Cache generated media to S3 URLs
- Use appropriate sizes to balance quality and generation time

#### Security
- Never expose JWT tokens in logs or client-side code
- Rotate tokens regularly
- Use HTTPS/WSS for all connections

---

## 16. WebSocket Communication

The backend supports WebSocket connections for real-time, bidirectional communication with AI models, enabling streaming responses, tool execution tracking, and workflow cancellation.

### 16.1 WebSocket Endpoint

#### **WS** `/chat/ws?token=<jwt>`

**Connection Flow**:
1. Connect with JWT token in query parameters
2. Send initial payload with `requestType`
3. Receive streaming events in real-time
4. Send cancellation messages if needed
5. Close connection when done

**Supported Request Types**:
- `"text"` - Standard chat with streaming
- `"realtime"` - Voice conversations (see [Realtime Audio Conversations](#9-realtime-audio-conversations))

**Initial Payload Example**:
```json
{
  "requestType": "text",
  "prompt": "What is the weather like?",
  "customer_id": 123,
  "session_id": "optional-session-id",
  "settings": {
    "text": {
      "model": "gpt-5",
      "stream": true
    }
  }
}
```

**Streaming Events**:
- `{"type": "text_chunk", "content": "chunk"}` - Text chunks
- `{"type": "tool_start", "content": {...}}` - Tool execution
- `{"type": "tool_result", "content": {...}}` - Tool results
- `{"type": "custom_event", "eventType": "iterationStarted"}` - Agentic workflow iteration
- `{"type": "text_completed"}` + `{"type": "tts_completed"}` - Completion (dual-flag model)

### 16.2 Workflow Cancellation

Cancel long-running workflows (e.g., agentic loops, tool executions) by sending a cancellation message via WebSocket.

**Cancellation Message**:
```json
{
  "type": "cancel",
  "session_id": "abc123"
}
```

**Response**:
```json
{
  "type": "cancelled",
  "session_id": "abc123",
  "message": "Request cancelled by user"
}
```

**Features**:
- Immediate termination of ongoing operations
- Resource cleanup (close connections, abort tasks)
- Graceful error handling for partial responses
- Applicable to text chat, agentic workflows, and tool executions

**Implementation Details**:
- Uses cancellation tokens for cooperative cancellation
- Handles nested workflows and concurrent operations
- Converts cancellations to user-friendly responses

---

## Appendix A: Complete Settings Schema

```json
{
  "settings": {
    "text": {
      "model": "string",
      "temperature": 0.0,
      "max_tokens": 2000,
      "reasoning_effort": "low|medium|high",
      "top_p": 1.0,
      "frequency_penalty": 0.0,
      "presence_penalty": 0.0,
      "stream": true
    },
    "audio": {
      "provider": "deepgram|openai|gemini|gemini_streaming",
      "action": "transcribe|translate",
      "language": "en",
      "model": "nova-2|whisper-1",
      "enable_speaker_diarization": false
    },
    "tts": {
      "provider": "openai|elevenlabs",
      "model": "tts-1|tts-1-hd|eleven_multilingual_v2",
      "voice": "alloy|echo|fable|onyx|nova|shimmer",
      "format": "mp3|opus|aac|flac|wav|pcm",
      "speed": 1.0,
      "enabled": true
    },
    "image": {
      "provider": "openai|stability|flux|gemini|xai",
      "model": "dall-e-3|stable-diffusion-xl|flux-pro",
      "size": "1024x1024|1792x1024|1024x1792",
      "quality": "standard|hd",
      "style": "natural|vivid",
      "n": 1,
      "cfg_scale": 7,
      "steps": 50,
      "sampler": "k_euler",
      "enabled": true
    },
    "video": {
      "provider": "gemini|openai",
      "model": "veo-3.1-fast|veo-3.1-quality",
      "duration_seconds": 5,
      "aspect_ratio": "16:9|9:16|1:1",
      "camera_motion": "static|pan_left|pan_right|zoom_in|zoom_out",
      "enabled": true
    },
    "realtime": {
      "model": "gpt-4o-realtime-preview|gemini-2.0-flash-live",
      "voice": "alloy|echo|shimmer",
      "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 500
      }
    }
  }
}
```

---

## Appendix B: Quick Reference

### Text Generation
```bash
# Non-streaming
curl -X POST "https://api.example.com/chat/" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","customer_id":123,"settings":{"text":{"model":"gpt-5"}}}'

# Streaming
curl -X POST "https://api.example.com/chat/stream" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","customer_id":123,"settings":{"text":{"model":"gpt-5"}}}'
```

### Audio Transcription
```bash
curl -X POST "https://api.example.com/api/v1/audio/transcribe" \
  -H "Authorization: Bearer TOKEN" \
  -F "file=@audio.mp3" \
  -F "action=transcribe" \
  -F "customerId=123" \
  -F 'userSettings={"audio":{"provider":"deepgram"}}'
```

### TTS
```bash
curl -X POST "https://api.example.com/api/v1/tts/generate" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello","action":"generate","customer_id":123,"user_settings":{"tts":{"provider":"openai","voice":"alloy"}}}'
```

### Image Generation
```bash
curl -X POST "https://api.example.com/image/generate" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"A cat","customer_id":123,"settings":{"image":{"provider":"openai"}}}'
```

### WebSocket
```javascript
const ws = new WebSocket('wss://api.example.com/chat/ws?token=TOKEN');
ws.onopen = () => {
  ws.send(JSON.stringify({
    requestType: 'text',
    prompt: 'Hello',
    settings: {text: {model: 'gpt-5'}}
  }));
};
```
