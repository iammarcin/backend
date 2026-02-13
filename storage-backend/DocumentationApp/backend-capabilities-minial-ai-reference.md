# Backend Capabilities - AI Reference

Version: 2.6
Last Updated: 2026-01-12

**Purpose:** Token-efficient reference for AI tools to understand available backend features.

## Features (18 Total)

1. **Chat** - Text conversation, WebSocket/SSE streaming, batch processing, 40+ models across 8 providers
2. **Agentic Workflow** - Multi-iteration internal tool loop (image/video/text/browser)
3. **Realtime** - Voice conversations (OpenAI Realtime, Gemini Live), bidirectional audio streaming
4. **Audio** - Speech-to-text (Deepgram, OpenAI, Gemini), streaming & batch
5. **Image** - Generation (OpenAI DALL-E, Stability, Flux, Gemini, xAI)
6. **Video** - Generation (Gemini Veo, OpenAI Sora, KlingAI), text-to-video, image-to-video, video extension, native audio
7. **Charts** - Interactive data visualizations and diagrams (bar, line, pie, area, scatter, mermaid)
8. **TTS** - Text-to-speech (OpenAI, ElevenLabs), streaming & sync, multiple voices/formats
9. **Browser Automation** - Web navigation, extraction, form filling, multi-step workflows via browser-use Agent
10. **Proactive Agent** - Multi-character AI framework (Sherlock/Bugsy) powered by Claude Code CLI, WebSocket push notifications, real-time streaming
11. **Semantic Search** - Vector search with Qdrant + OpenAI embeddings, tag/date filtering
12. **Storage** - S3 file upload
13. **Garmin** - Health/activity data aggregation
14. **Blood** - Test result tracking and analysis
15. **UFC** - Fighter data, subscriptions, async enrichment
16. **Admin** - Model registry inspection, health checks
17. **WebSocket Cancellation** - Cancel long-running workflows via WebSocket signaling
18. **Batch** - Asynchronous batch processing for large volumes of text generation requests, 50% cost reduction, 24-hour turnaround, supports OpenAI, Anthropic, Gemini

## Providers & Models

### Text Generation

**OpenAI:** o3, o3-pro, o4-mini, o3-mini, gpt-5-pro, gpt-5.1 (replaces gpt-5), gpt-5-mini, gpt-5-nano, gpt-4o, gpt-4o-mini, gpt-4.1, gpt-4.1-mini, gpt-4.1-nano

**Anthropic:** claude-sonnet (4.5), claude-opus (4.1), claude-haiku (4.5), claude-sidecar

**Google:** gemini-3-pro-preview (NEW), gemini-pro (2.5), gemini-flash (2.5)

**xAI:** grok-4, grok-4-mini

**Groq:** gpt-oss-120b, llama-3.3-70b

**Perplexity:** sonar-deep-research, sonar-reason-pro, sonar-reason, sonar-pro, sonar

**DeepSeek:** deepseek-chat, deepseek-reason

### Realtime (Voice)

**OpenAI:** gpt-realtime (GA, recommended), gpt-realtime-mini (GA), gpt-realtime-preview (deprecated), gpt-4o-realtime-preview (deprecated)
- Features: Audio I/O, VAD, Function Calling
- Voices: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar (10 total)
- Cost: gpt-realtime $0.10/min input, $0.20/min output; gpt-realtime-mini $0.05/min input, $0.10/min output

**OpenAI Streaming STT:** gpt-4o-transcribe ($0.10/min), gpt-4o-mini-transcribe ($0.05/min)

**Google:** gemini-2.0-flash-exp (aliases: gemini-live, gemini-realtime)

### Audio (STT)

**Providers:**
- Deepgram: nova-3 (default) - Real-time streaming, speaker diarization, 50+ languages
- OpenAI Whisper: whisper-1 - Batch transcription, 98 languages, $0.006/min
- OpenAI Streaming: gpt-4o-transcribe ($0.10/min), gpt-4o-mini-transcribe ($0.05/min) - Real-time WebSocket
- Gemini: gemini-2.5-pro, gemini-2.5-flash - Multimodal audio understanding, translation

**Endpoints:** `POST /api/v1/audio/transcribe` (static), `WS /api/v1/audio/transcribe-stream` (streaming)

### Image

**Models:**
- OpenAI: gpt-image-1.5 (default), gpt-image-1, gpt-image-1-mini, dall-e-3 (legacy). Aliases: openai-1.5, openai-1
- Flux: flux-2-pro (default), flux-2-max, flux-2-flex, flux-dev (legacy), flux-kontext-pro. Aliases: flux-pro, flux-max, flux-flex, flux-1
- Stability: core (default), sd3.5, sd3, sdxl (legacy)
- Gemini: gemini-3-pro-image-preview (Nano Banana Pro), gemini-2.5-flash-image (default). Aliases: gemini-pro, nano-banana, nano-banana-pro
- xAI: grok-2-image

**Endpoint:** `POST /image/generate`

**Sizes:** Up to 2048x2048 (Flux), 1024x1024/1792x1024/1024x1792 (OpenAI)

**Quality:** standard, hd (OpenAI); low, medium, high, auto (all providers)

**Style:** natural, vivid (OpenAI)

**Image-to-Image:** Flux supports transforming existing images via `image_url` parameter

### Video

**Models:**
- Gemini: veo-3.1-fast-generate-preview (default, alias: veo-3.1-fast), veo-3.1-generate-preview (alias: veo-3.1, veo-3.1-quality)
  - Resolutions: 720p, 1080p
  - Features: text-to-video, image-to-video, person generation modes
- OpenAI: sora-2
  - Durations: 4, 8, 12 seconds
  - Sizes: 1280x720, 720x1280, 1024x1792, 1792x1024
  - Features: text-to-video, image-to-video
- KlingAI (NEW - Most Feature-Rich):
  - V1: kling-v1, kling-v1-5, kling-v1-6 (multi-image)
  - V2: kling-v2-master, kling-v2-1, kling-v2-5, kling-v2-5-turbo
  - V2.6: kling-v2-6, kling-v2-6-pro (native audio generation)
  - O1: kling-o1, kling-o1-pro (unified generation + editing)
  - Durations: 5 or 10 seconds (extendable to 180s)
  - Aspect Ratios: 16:9, 9:16, 1:1
  - Features: text-to-video, image-to-video, multi-image, video extension, avatar/lip-sync, motion brush, camera control, native audio (V2.6/O1)

**Endpoints:** `POST /video/generate`, `POST /video/extend` (KlingAI only)

### TTS

**Models:**
- OpenAI: gpt-4o-tts, gpt-4o-mini-tts (default), tts-1 (legacy), tts-1-hd (legacy)
  - Voices: alloy, echo, fable, onyx, nova, shimmer
  - Speed: 0.25x - 4.0x
- ElevenLabs: eleven_monolingual_v1 (default), eleven_turbo_v2
  - Named voices: sherlock, naval, yuval, elon, hermiona, david, shaan, rick, morty, samantha, allison, amelia, danielle, hope, alice, bill, brian, eric, jessica, sarah, claire, anarita, bianca, will
  - Default: Rachel

**Formats:** mp3, opus, aac, flac, wav, pcm (OpenAI); pcm, pcm_24000, mp3, mp3_44100, mp3_44100_128 (ElevenLabs)

**Endpoints:** `POST /api/v1/tts/generate` (sync), `POST /api/v1/tts/stream` (HTTP stream)

**Highlights:**
- `tts_auto_execute=true` duplicates streaming text into a TTS queue so ElevenLabs audio starts before text completes.【F:docker/storage-backend/core/streaming/manager.py†L33-L118】【F:docker/storage-backend/features/chat/services/streaming/tts_orchestrator.py†L60-L162】
- Fallback automatically buffers text when a provider lacks `supports_input_stream`, preserving compatibility with OpenAI HTTP streaming.【F:docker/storage-backend/features/tts/service_stream_queue_helpers.py†L58-L137】

### Browser Automation

**Capability:** AI-driven web automation via browser-use Agent (navigate, extract, fill forms, download files)

**Trigger:** Agentic workflow detects `browser_automation` tool when LLM requests it (natural chat input)

**Models:**
- Gemini (default) - Free tier, good balance
- ChatBrowserUse - 3-5x faster, optimized for automation
- OpenAI - Complex reasoning capability
- Anthropic - Budget-friendly

**Configuration:**
```bash
BROWSER_AUTOMATION_URL=http://browser-automation:8001
BROWSER_DEFAULT_LLM_PROVIDER=gemini
BROWSER_DEFAULT_MAX_STEPS=100
BROWSER_TASK_TIMEOUT=300
```

**User Settings:** `settings.browser_automation` (enable, timeout, max_steps, llm_provider, vision mode, window size)

**Events:** `browserAutomationStarted`, `browserAutomationCompleted`, `browserAutomationError` via `customEvent`

**Implementation:** `core/tools/internal/browser_automation.py`, `features/browser/service.py`

**Container:** `betterai/browser-automation:latest` (isolated Chromium, VNC at :99)

**For details:** See `DocumentationApp/browser-automation-handbook.md`

### Charts

**Capability:** Interactive data visualizations and diagrams (bar, line, pie, area, scatter, mermaid)

**Trigger:** Agentic workflow detects `chart_generation` tool when LLM decides charts are appropriate

**Chart Types:**
- Line charts (trends over time)
- Bar charts (comparisons)
- Pie charts (proportions)
- Area charts (cumulative data)
- Scatter plots (correlations)
- Mermaid diagrams (flowcharts, graphs)

**Data Sources:**
- Real databases (Garmin health data, blood tests)
- Generated/synthetic data
- Diagram definitions

**Backend Processing:**
- LLM structures data into ChartPayload format
- Emits WebSocket event: `customEvent` with `eventType: "chartGenerated"`
- No server-side rendering, lightweight payload

**Frontend Rendering:**
- React web: Recharts library
- Kotlin Android: Chart.js via WebView
- Interactive features: hover tooltips, zoom, legend interaction

**Events:** `chartGenerated` via `customEvent`

**Implementation:** `core/tools/internal/chart_events.py`, `features/chat/services/streaming/events/chart_events.py`

**For details:** See `DocumentationApp/charting-system-handbook.md`

### Proactive Agent (Sherlock & Bugsy)

**Capability:** Multi-character AI framework powered by Claude Code CLI with proactive notifications, real-time streaming, and TTS auto-execute

**Characters:**
- **Sherlock** - Detective persona with proactive heartbeats (15-min check-ins), personality files, memory persistence
- **Bugsy** - Development assistant for codebase Q&A with full edit permissions

**Architecture (v2.1):** Frontend → Unified WebSocket → SQS Queue → Claude Code CLI Poller → Backend API → WebSocket Push (multi-client sync) → TTS Streaming (optional)

**Unified WebSocket:** `WS /chat/ws?mode=proactive` - Primary interface for send + receive

**REST Endpoints (Internal):**
- `GET /api/v1/proactive-agent/health` - Health check
- `GET /api/v1/proactive-agent/session` - Get/create session
- `GET /api/v1/proactive-agent/messages/{session_id}/poll` - Poll fallback
- `POST /api/v1/proactive-agent/notifications` - Internal: receive heartbeat notifications
- `WS /api/v1/proactive-agent/ws/poller-stream` - Internal: poller NDJSON streaming

**WebSocket Messages (Client → Server):**
- `send_message` - Send message to character with optional `tts_settings`
- `pong` - Response to ping
- `sync` - Request missed messages

**WebSocket Messages (Server → Client):**
- `connected`, `ping` - Connection lifecycle
- `message_sent` - ACK with `db_message_id` (for deduplication)
- `send_error` - Error for send_message
- `notification` - Agent message or multi-client sync
- `stream_start`, `text_chunk`, `thinking_chunk`, `stream_end` - Real-time streaming
- `tts_started`, `audio_chunk`, `tts_completed` - TTS audio streaming (when enabled)
- `sync_complete` - Offline message sync response

**TTS Auto-Execute:**
- Include `tts_settings: {voice, model, tts_auto_execute: true}` in `send_message`
- Backend orchestrates ElevenLabs streaming in parallel with text
- Audio chunks delivered via `audio_chunk` events (base64 PCM)
- `stream_end` includes `audio_file_url` for persisted audio

**Configuration:**
- `AWS_SQS_PROACTIVE_AGENT_QUEUE_URL` - SQS queue for message routing

**Message Limits:** 1-30,000 characters

**Implementation:** `features/proactive_agent/`, `features/chat/services/proactive_handler.py`, `core/connections/proactive_registry.py`, `features/proactive_agent/streaming_registry.py` (TTS)

**For details:** See `DocumentationApp/sherlock-technical-handbook.md`

### File Upload

**Endpoint:** `POST /api/v1/storage/upload`

**Supported Types:**
- Audio: mp3, wav, m4a, opus, webm, mpeg, mpga, pcm
- Image: jpg, jpeg, png, gif, webp
- Video: mp4, webm
- Documents: pdf, txt

**Storage:** S3 with signed URLs

## Key Endpoints

### Chat
- `POST /chat` - Non-streaming
- `POST /chat/stream` - SSE streaming
- `POST /chat/session-name` - Auto-generate session titles using LLM
- `WS /chat/ws` - WebSocket (classic + realtime mode)
- `POST /api/v1/chat/sessions` - Session management
- `POST /api/v1/chat/messages` - Message management

### Batch API
- `POST /api/v1/batch` - Submit batch job (50% cost savings)
- `GET /api/v1/batch` - List all batch jobs
- `GET /api/v1/batch/{job_id}` - Get job status
- `GET /api/v1/batch/{job_id}/results` - Get completed results
- `POST /api/v1/batch/{job_id}/cancel` - Cancel job

### Realtime
- `WS /chat/ws?mode=realtime` - Voice chat
- `GET /realtime/health` - Health check

### Audio
- `POST /api/v1/audio/transcribe` - Static file
- `WS /api/v1/audio/transcribe-stream` - Streaming

### Image/Video/TTS
- `POST /image/generate`
- `POST /video/generate`
- `POST /api/v1/tts/generate`
- `WS /tts/stream`

### Browser Automation
- Triggered via agentic workflow (no direct endpoint)
- Internal container: `http://browser-automation:8001/health`, `/providers`, `/execute`

### Proactive Agent
- `WS /chat/ws?mode=proactive` - Unified WebSocket (send + receive)
- `GET /api/v1/proactive-agent/health` - Health check
- `GET /api/v1/proactive-agent/session` - Get/create session
- `GET /api/v1/proactive-agent/messages/{session_id}/poll` - Poll fallback

### Storage
- `POST /api/v1/storage/upload` - S3 upload

### Data Services
- `GET /api/v1/garmin/analysis/overview` - Health data
- `GET /api/v1/blood/tests` - Blood tests
- `GET /api/v1/semantic/health` - Semantic search status

### Admin
- `GET /admin/models/openai` - Model registry
- `GET /admin/models/openai/{model}` - Model details

### Legacy (backward compatibility)
- `POST /api/db` - Action-based routing for old mobile clients (`db_new_message`, `db_search_messages`, etc.)
- `POST /api/aws` - Legacy file upload

## WebSocket Request Types

**Valid `requestType` values:**

1. **text** (default) - Standard text chat
2. **audio** - STT → text response
3. **audio_direct** - Audio sent directly to LLM (Gemini multimodal)
4. **tts** - Text-to-speech only
5. **realtime** - Voice conversation (realtime providers)

**Mode detection:** Query params (`?mode=realtime`), headers (`X-Chat-Mode`), model hints, explicit `requestType`

**Streaming TTS events:** `tts_started` → `audio_chunk` → `tts_generation_completed` → `tts_completed`/`tts_not_requested` with optional `tts_file_uploaded` for persisted downloads.【F:docker/storage-backend/features/tts/service_stream_queue.py†L62-L107】

## Request Structure

### Chat HTTP
```json
{
  "customer_id": 123,
  "session_id": "optional",
  "prompt": "text or array",
  "settings": {
    "text": {"model": "gpt-5", "temperature": 0.7, "max_tokens": 2000},
    "tts": {
      "provider": "elevenlabs",
      "tts_auto_execute": true,
      "streaming": true,
      "voice": "alloy"
    }
  }
}
```

### Chat WebSocket
```json
{
  "requestType": "text|audio|realtime",
  "prompt": "text or array",
  "settings": {
    "text": {"model": "gpt-5"},
    "audio": {"provider": "deepgram"},
    "realtime": {"model": "gpt-4o-realtime-preview", "voice": "alloy"},
    "tts": {"provider": "elevenlabs", "tts_auto_execute": true}
  }
}
```

## Model Capabilities

**Key flags:**
- `is_reasoning_model` - Extended thinking (o3, opus, gemini-pro, sonar-reason, deepseek-reason)
- `support_image_input` - Vision (gpt-4o, claude-sonnet, gemini)
- `support_audio_input` - Audio (gemini models)
- `supports_citations` - Web citations (Perplexity models)

**Temperature limits:**
- Most: max 2.0
- Anthropic: max 1.0
- Reasoning models: no temperature control

## Architecture Notes

- **Provider Registry:** Models registered at import, resolved via factory (`core/providers/`)
- **Streaming:** Token-based completion ownership (only token holder can complete)
- **Streaming TTS:** `StreamingManager.register_tts_queue` duplicates text chunks and `TTSOrchestrator` runs ElevenLabs queue streaming alongside text generation.【F:docker/storage-backend/core/streaming/manager.py†L33-L118】【F:docker/storage-backend/features/chat/services/streaming/tts_orchestrator.py†L60-L170】
- **Agentic Loop:** Chat payloads stay in OpenAI Chat Completions format, the backend automatically executes tools + appends tool responses, and integrators only need to persist the combined assistant/tool messages (see `DocumentationApp/agentic-workflow-handbook.md`).
- **Auth:** JWT token required (`Authorization: Bearer <token>`)
- **Databases:** Main (chat), Garmin, Blood, UFC (async SQLAlchemy)
- **Error Types:** `ProviderError`, `ValidationError`, `DatabaseError`, `ConfigurationError`

## Settings Schema (Quick Reference)

```json
{
  "settings": {
    "text": {"model": "string", "temperature": 0.0-2.0, "max_tokens": 2000, "reasoning_effort": "low|medium|high"},
    "audio": {"provider": "deepgram|openai|gemini", "action": "transcribe|translate", "language": "en"},
    "tts": {"provider": "openai|elevenlabs", "model": "string", "voice": "string", "format": "mp3|opus|pcm", "tts_auto_execute": true},
    "image": {"provider": "openai|stability|flux|gemini|xai", "model": "string", "width": 1024, "height": 1024, "quality": "standard|hd"},
    "video": {"provider": "gemini|openai|klingai", "model": "string", "duration_seconds": 5|10, "aspect_ratio": "16:9|9:16|1:1", "mode": "std|pro", "enable_audio": true},
    "realtime": {"model": "string", "voice": "string", "turn_detection": {"type": "server_vad", "threshold": 0.5}}
  },
  "userSettings": {
    "general": {"save_to_s3": true},
    "semantic": {
      "enabled": true,
      "search_mode": "hybrid|semantic|keyword|session_hybrid|session_semantic|multi_tier",
      "limit": 10,
      "threshold": 0.7,
      "tags": ["tag1"],
      "message_type": "user|assistant|both",
      "date_range": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"},
      "session_ids": ["session-123"],
      "top_sessions": 3,
      "messages_per_session": 5
    }
  }
}
```

**See full handbook for complete schema reference and examples.**

## File Locations

- Providers: `core/providers/{text,realtime,audio,image,video,tts}/`
- Models config: `config/providers/<provider>/models.py`
- Features: `features/{chat,realtime,audio,image,video,tts,semantic_search,storage,db}/`
- Routes: `features/<feature>/routes.py`
- Business logic: `features/<feature>/service.py`
