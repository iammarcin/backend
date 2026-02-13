## Component Overview

This is **storage-backend** - a FastAPI-based backend service providing AI-powered chat, audio transcription, image/video generation, and health data APIs for the BetterAI platform.

**Key characteristics:**
- Python 3.10+ with FastAPI, SQLAlchemy (async), and Pydantic v2
- Multi-provider AI integration (OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, xAI, etc.)
- WebSocket and SSE streaming for real-time chat/audio
- Multiple MySQL databases (main, Garmin, blood, UFC)
- Layered architecture: `core/` → `features/` → `infrastructure/`

## Architecture Overview

### Layered Structure

The codebase follows strict separation of concerns:

```
core/              - Cross-cutting infrastructure (not feature-specific)
├── providers/     - AI provider registry & factory (text, image, video, audio, TTS, realtime)
├── clients/       - External service clients (Claude sidecar, AI SDKs)
├── streaming/     - WebSocket/SSE streaming manager
├── observability/ - Metrics collection and WebSocket logging
├── config.py      - Environment variable configuration
├── exceptions.py  - Typed exception hierarchy
└── pydantic_schemas/ - API envelope schemas

features/          - Domain-specific business logic (each feature is self-contained)
├── chat/          - Chat sessions, messages, WebSocket/SSE endpoints
├── realtime/      - Realtime voice chat (OpenAI Realtime API, Gemini Live)
├── audio/         - Speech-to-text (Deepgram, OpenAI, Gemini)
├── image/         - Image generation (OpenAI, Stability, Flux, Gemini)
├── video/         - Video generation (Gemini Veo, OpenAI Sora)
├── tts/           - Text-to-speech (OpenAI, ElevenLabs)
├── semantic_search/ - Semantic search with vector embeddings (Qdrant + OpenAI)
├── admin/         - Model registry inspection endpoints
├── storage/       - S3 file upload and attachment handling
├── legacy_compat/ - Legacy API compatibility for old mobile clients
└── db/            - Database-backed features (blood, garmin, ufc)

infrastructure/    - External integrations (not tied to specific features)
├── db/            - MySQL session factories & helpers
└── aws/           - S3 storage, SQS queue services

services/          - Shared application services
└── temporary_storage.py - Temp file staging for uploads
```

### Provider Registry Pattern

**Critical concept:** Providers are registered at import time and resolved via factory functions.

1. **Configuration** (`config/providers/<provider>/models.py`):
   - Model definitions organized by provider
   - `ModelConfig` with capabilities (reasoning, audio input, API type)

2. **Registration** (`core/providers/__init__.py`):
   ```python
   register_text_provider("openai", OpenAITextProvider)
   register_realtime_provider("google", GoogleRealtimeProvider)
   ```

3. **Resolution** (`core/providers/factory.py`):
   ```python
   provider = get_text_provider(settings)  # Uses model registry
   provider = get_realtime_provider("gpt-4o-realtime")  # Direct by name
   ```

4. **Model Registry** (`core/providers/registry/`):
   - Maps model names → provider + capabilities
   - Handles aliases (e.g., "gemini" → actual model ID)
   - Attaches `ModelConfig` with reasoning flags, temperature limits, API type

**Note:** Complex providers may have subdirectories (e.g., `text/openai_responses/`, `text/gemini/`) for modular organization.

**When adding a new provider:**
1. Define model configs in `config/providers/<provider>/models.py`
2. Aggregate in `config/providers/__init__.py`
3. Implement provider class in `core/providers/<category>/`
4. Register in `core/providers/__init__.py`
5. Add unit tests in `tests/unit/core/providers/`

### Streaming Architecture

**StreamingManager** (`core/streaming/manager.py`) enforces **token-based completion ownership**:

- `create_completion_token()` must be called once by the top-level dispatcher
- The returned token is passed down the workflow call stack (`completion_token` parameters)
- Only the code holding the token may call `await manager.signal_completion(token=token)`
- Services and providers never call `signal_completion()` — they stream events and return
- Attempting to complete without the token raises `CompletionOwnershipError`

**Token lifecycle:**
1. Dispatcher creates token: `token = manager.create_completion_token()`
2. Workflow executor receives token and completes after sub-workflows finish
3. Helpers/services without the token cannot complete — misuse raises at runtime
4. Duplicate `signal_completion(token=token)` calls are idempotent

**Frontend Event Contract:** Workflow executors MUST send completion events (`textCompleted`, `ttsNotRequested`, etc.) in `finally` blocks BEFORE calling `signal_completion()`. See `websocket-events-handbook.md` for the complete event contract.

### Client Initialization

**All AI SDKs** are initialized at import time in `core/clients/ai.py`:

- Initializes OpenAI, Anthropic, Gemini, Groq, Perplexity, DeepSeek, xAI clients
- Exposes global `ai_clients` dict for provider access
- Environment variables required (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Cleanup logic with atexit handlers

## WebSocket Communication

### Connection Flow

1. Client connects to `/chat/ws?token=<jwt-token>`
2. Switchboard sends `{"type": "websocketReady", "version": "2.0"}`
3. Client sends initial payload (requestType, prompt, settings)
4. Backend authenticates, creates `WorkflowSession`, sends `{"type": "websocketReady", "session_id": "..."}`
5. Backend dispatches workflow and streams events
6. Completion events (`textCompleted`, `ttsNotRequested`, `complete`, `fullProcessComplete`) close the stream

### Critical Event Types

**Connection:** `websocketReady`, `working`, `closing`
**Content:** `text`, `reasoning`, `audio`, `transcription`
**Model Discovery:** `customEvent` → `aiTextModelInUse`
**Completion (REQUIRED):** `textCompleted`/`textNotRequested`, `ttsCompleted`/`ttsNotRequested`, `complete`, `fullProcessComplete`
**Database:** `dbOperationExecuted`
**Errors:** `error` (with `stage` field)

**For complete event catalog and frontend contract requirements, see `DocumentationApp/websocket-events-handbook.md`**

## Core Infrastructure

### AWS Services

**S3 Storage** (`infrastructure/aws/storage.py`):
- File upload handling (TTS audio, user attachments)

**SQS Queues** (`infrastructure/aws/queue.py`)

### Observability
**General logging** `core/logging.py`
**Metrics Collection** (`core/observability/metrics.py`)
**WebSocket Logging** (`core/observability/websocket_logging.py`)

## Features

### Chat
- Standard text chat with streaming
- WebSocket endpoint: `/chat/ws`
- Services: history, streaming, workflow orchestration
- Repositories: sessions, messages, prompts

### Semantic Search
- Three search modes (`semantic`, `hybrid`, `keyword`) selectable via `userSettings.semantic.semantic_search_mode`. 
- `MultiCollectionSemanticProvider` wraps the Qdrant provider and writes every message to both dense-only and dense + sparse collections while reusing the same embedding and deleting duplicates via content hashes.
- Deduplication occurs before indexing (SHA-256 of content) 

### Realtime Chat
- Low-latency voice conversations (OpenAI Realtime API, Gemini Live)
- Duplex audio streaming with interruption support

### Batch API
- Asynchronous batch processing for text generation with 50% cost savings
- Support for OpenAI, Anthropic, and Gemini batch endpoints 
- See `DocumentationApp/batch-api-handbook.md` for full usage guide

### Audio
- Speech-to-text (Deepgram, OpenAI, Gemini)
- Static and streaming transcription
- Audio direct mode (Gemini multimodal)

### Image, Video, TTS
- Image generation (OpenAI, Flux, Gemini, xAI)
- Video generation (Gemini Veo, OpenAI Sora)
- Text-to-speech (OpenAI, ElevenLabs)

### Storage
- S3 file upload endpoint: `/api/v1/storage/upload`

## Database Architecture

Four separate MySQL databases with async SQLAlchemy:

- **Main DB** (`MAIN_DB_URL`): Chat sessions, messages, 
- **Garmin DB** (`GARMIN_DB_URL`): Garmin health metrics
- **Blood DB** (`BLOOD_DB_URL`): Blood test results
- **UFC DB** (`UFC_DB_URL`): UFC fighter data, subscriptions

**Session management:**
- Engines/factories created at import in `infrastructure/db/mysql.py`
- FastAPI dependencies yield scoped sessions via `session_scope()`
- Repositories **never commit** - handled by dependency scope
- Missing DB URLs raise `ConfigurationError` on first access

## Feature Module Pattern

Each feature follows consistent structure:

```
features/<domain>/
├── routes.py         - FastAPI router (HTTP/WebSocket)
├── service.py        - Business logic orchestration
├── dependencies.py   - FastAPI dependency providers
├── schemas/          - Pydantic request/response models
├── db_models.py      - SQLAlchemy ORM models (if DB-backed)
├── repositories/     - Database CRUD operations
└── utils/            - Feature-specific helpers
```

**Key principles:**
- Routes call services, not repositories directly
- Services orchestrate providers + repositories
- Repositories handle database operations only
- All responses use `api_ok()` / `api_error()` envelopes

## Development Patterns

### Working with Providers

Providers must inherit from base classes:
- `BaseTextProvider` - streaming text generation
- `BaseImageProvider` - image generation
- `BaseVideoProvider` - video generation
- `BaseTTSProvider` - text-to-speech
- `BaseAudioProvider` - speech-to-text
- `BaseRealtimeProvider` - realtime voice chat

All implement async methods and raise typed exceptions (`ProviderError`, `ValidationError`).

## Configuration Architecture (IMPORTANT!)

**All major configuration is centralized in `config/` directory, organized by feature domain.**

### Configuration Discipline

When working on any feature, **always** put configuration in `config/`:

1. **Find the right domain:** `config/audio/`, `config/tts/`, `config/video/`, etc.
2. **Separate values from logic:**
   - `defaults.py` - Parameter values (temperature=0.7, model="gpt-4", etc.)
   - `utils/` - Helper functions (getters, setters, validators)

## Testing Strategy

### Test Organization

- **`tests/api/`** - Route tests with `httpx.AsyncClient`, dependency overrides
- **`tests/features/`** - Service tests with mocked providers
- **`tests/integration/`** - End-to-end flows (some with Testcontainers)
- **`tests/unit/`** - Pure unit tests for core/infrastructure
- **`tests/manual/`** - Manual validation scripts (require running server)

## Documentation

**Available Handbooks** (`DocumentationApp/`):
- **`storage-backend-ng-developer-handbook.md`** - Comprehensive architecture guide
- **`storage-backend-ng-database-handbook.md`** - Database setup and ORM details
- **`storage-backend-ng-databases-others-handbook.md`** - Garmin/Blood/UFC databases
- **`testing-guide-handbook.md`** - Testing strategy and E2E scripts
- **`text-providers-config-handbook.md`** - Provider configuration details
- **`websocket-events-handbook.md`** - Complete WebSocket event catalog and frontend contract
- **`semantic-search-handbook.md`** - Semantic search architecture, configuration, and usage
- **`realtime-chat-handbook.md`** - Realtime mode

## Code File Discipline

- Python code files should stay within **200–250 lines**
- If a file grows beyond that, split responsibilities into helpers or tools
- Apply the same cap to new utility or handler files

## Code Reuse

**Before implementing, search for existing similar code first.** If found, challenge the approach and suggest extending it. Prefer extending existing functions/components over creating new ones. Be proactive - minimal code is the goal.

## Code Review Guidelines

**When reviewing implementations, read:**
- `DocumentationApp/CODE-REVIEW-INSTRUCTIONS.md` - FastAPI-specific review checklist

Key checks: Routes registered, dependencies wired, providers registered, all async awaited, schemas match API contract.

## Troubleshooting Guidelines

**When debugging bugs or unexpected behavior, read:**
- `DocumentationApp/TROUBLESHOOTING-GUIDELINES.md` - Systematic analysis framework

**The 6-step framework:**
1. Map the system (components, states, transitions)
2. Trace ALL paths (happy, error, crash, timeout, concurrent)
3. Verify data at every boundary (types, formats, values)
4. Check state machine completeness (stuck states, crash recovery)
5. Verify documentation matches reality
6. Check resource lifecycle (creation, cleanup, interruption)

**Key principle:** Complete the full analysis even when you think you know the answer. Look for issues UNLIKE your initial hypothesis.

## Docker Environment Reminder

**IMPORTANT** This repository runs inside Docker containers.

- After **every** change that could impact backend behavior, immediately review the backend logs
- Note that auto-reload is enabled, so you don't need to rebuild/restart after changes.

**Check logs:**
```bash
docker logs backend
```

## Field Naming Rules

- **snake_case only** - DB columns, Pydantic schemas, response dicts, WebSocket payloads.
- **One name per field** - Column name = schema field = API response key.
- **No dual emission** - Never emit both `foo_bar` and `fooBar`.
- **No camelCase converters** - Fix at source, not with mappers.
