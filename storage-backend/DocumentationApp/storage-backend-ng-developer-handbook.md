# storage-backend-ng Developer Handbook

**Backend location:** `storage-backend`
**Default container name:** `storage-backend`
**Primary port:** `8000`
**Last updated:** 2026-01-12

This handbook is the ground truth for the refactored backend that powers multiple frontends (react/kotlin/etc). It explains how the service boots, how features are organised, and how to extend the codebase without breaking established contracts. Share it with any new agent so they can become effective maintainers without reverse-engineering the project.

## Table of contents
1. [Onboarding snapshot](#onboarding-snapshot)
2. [Directory layout](#directory-layout)
3. [Application startup & observability](#application-startup--observability)
4. [Configuration & environment management](#configuration--environment-management)
5. [Provider & model architecture](#provider--model-architecture)
6. [Core runtime contracts](#core-runtime-contracts)
7. [Feature modules](#feature-modules)
8. [Infrastructure services](#infrastructure-services)
9. [Temporary storage utilities](#temporary-storage-utilities)
10. [Testing strategy](#testing-strategy)
11. [Development guidelines & extension playbooks](#development-guidelines--extension-playbooks)
12. [Troubleshooting & common pitfalls](#troubleshooting--common-pitfalls)

---

## Onboarding snapshot
- Start everything from the project root with `./startDocker.sh`. The script auto-selects the compose file and environment variables for local, sherlock, or production hosts. This spins up multiple containers: backend (`8000`), frontend, and browser automation container (`8001`).
- The FastAPI application is exposed on port `8000`. The health check (`/health`) and OpenAPI docs (`/docs`) are available as soon as the service starts.[F:storage-backend/main.py L25-L72]
- `main.py` mounts routers for admin tooling, chat (classic and realtime), audio, image, S3 storage, video, Garmin, blood, UFC, semantic search, and TTS (HTTP + WebSocket). Wire any new feature through its router module rather than editing the FastAPI factory directly.[F:storage-backend/main.py L34-L125]
- Logging is initialised at import time; you do not need to call `setup_logging` manually in tests or scripts.[F:storage-backend/main.py L8-L22]

## Directory layout
The backend follows a layered structure. Keep new code within these buckets to avoid the sprawl that plagued the legacy service.

| Path | Purpose |
| --- | --- |
| `core/` | Cross-cutting utilities: logging, env config, exception types, provider registry, streaming primitives, API envelope schemas, request logging middleware.[F:storage-backend/core/logging.py L1-L170][F:storage-backend/core/config.py L1-L214][F:storage-backend/core/exceptions.py L1-L44][F:storage-backend/core/pydantic_schemas/__init__.py L1-L22][F:storage-backend/core/streaming/manager.py L1-L70][F:storage-backend/core/observability/request_logging.py|L1-L88] |
| `core/providers/` | Pluggable integrations for text, image, video, audio, realtime, TTS, and auxiliary services (e.g., Withings). Providers register on import; resolution helpers live in `core/providers/resolvers.py` and pull from the shared registries.[F:storage-backend/core/providers/__init__.py L1-L60][F:storage-backend/core/providers/resolvers.py L1-L160][F:storage-backend/core/providers/registry/registry.py L1-L70] |
| `features/` | End-user functionality grouped by domain. Each feature exposes FastAPI routers, dependency helpers, business services, schemas, and utilities. Follow the existing structure when adding new behaviour (e.g., `routes.py`, `service.py`, `dependencies.py`, `schemas/`, `utils/`).[F:storage-backend/features/chat/routes.py L1-L81][F:storage-backend/features/audio/service.py L1-L86][F:storage-backend/features/video/routes.py L1-L56] |
| `features/db/*` | Database-backed domains (blood, Garmin, UFC). Each folder contains SQLAlchemy models, repositories, service logic, and HTTP endpoints that wrap the shared API envelope helpers.[F:storage-backend/features/db/blood/service.py L1-L44][F:storage-backend/features/db/garmin/service.py L1-L84][F:storage-backend/features/db/ufc/routes.py L1-L84] |
| `infrastructure/` | External integrations that are not tied to a single feature: MySQL session factories, AWS clients, S3/SQS helpers.[F:storage-backend/infrastructure/db/mysql.py L1-L121][F:storage-backend/infrastructure/aws/storage.py L1-L82][F:storage-backend/infrastructure/aws/queue.py L1-L78] |
| `services/` | Shared application services. Currently contains the temporary file staging helper used by multiple domains.[F:storage-backend/services/temporary_storage.py L1-L56] |
| `tests/` | End-to-end, integration, feature, and unit tests. Pytest configuration enables asyncio and docker-based suites as opt-in markers.[F:storage-backend/tests/api/ufc/test_auth_routes.py L1-L118][F:storage-backend/pytest.ini L1-L8] |

Avoid creating ad-hoc `utils/` folders at the project root. Add helper code under the relevant feature (`features/<domain>/utils`) or in `core/` when it spans multiple domains.

## Application startup & observability
- `setup_logging` installs console/file handlers, trims path prefixes, and suppresses noisy websocket chatter. Tune log levels via `BACKEND_LOG_LEVEL`, `BACKEND_LOG_CONSOLE_LEVEL`, `BACKEND_LOG_FILE_LEVEL`, and retention via `BACKEND_LOG_RETENTION`.[F:storage-backend/core/logging.py L66-L170]
- Request logging is centralised in `core.observability.register_http_request_logging`, which masks sensitive headers, truncates payload previews, and automatically attaches to the FastAPI app during startup.[F:storage-backend/core/observability/request_logging.py L1-L88][F:storage-backend/core/observability/request_logging.py L90-L142]
- Structured API envelopes and consistent error payloads come from `core.pydantic_schemas` and `core.http.errors`. Use `api_ok`/`api_error` rather than crafting JSON manually.[F:storage-backend/core/pydantic_schemas/api_envelope.py L14-L52][F:storage-backend/core/http/errors.py L1-L44]
- **StreamingManager** (`core/streaming/manager.py`, 253 lines) orchestrates event distribution to multiple consumers (WebSocket, SSE, TTS) with **token-based completion ownership** to prevent race conditions. Key features:
  - `create_completion_token()` - Top-level dispatcher creates a token; only token holder can call `signal_completion()`
  - `send_to_queues()` - Fan-out with modes: "all" (WebSocket + TTS), "frontend_only" (WebSocket + TTS), "tts_only" (TTS only)
  - TTS coordination - Text chunks duplicated to optional TTS queue via `register_tts_queue()` while simultaneously sent to WebSocket consumers
  - Event sanitization - `sanitize_for_json()` handles datetime, UUID, Decimal, and circular references with depth limiting
  - Completion semantics - Both frontend and TTS queues receive completion sentinels (`None`) to unblock subscribers
  - **Critical rule:** Always emit custom events BEFORE calling `manager.signal_completion()` to prevent "Attempted to send to a completed stream" warnings.
- **TTSQueueManager** (`core/streaming/tts_queue_manager.py`, 98 lines) extracted to handle TTS concerns separately: queue registration/deregistration, chunk duplication, and state tracking. Keeps StreamingManager focused on core event distribution.[F:storage-backend/core/streaming/manager.py L50-L299][F:storage-backend/core/streaming/tts_queue_manager.py L1-L98]

## Configuration & environment management
- `core.config` is the single entry point for environment variables. It exposes provider defaults, AWS credentials, Claude sidecar settings, and database URLs with environment-sensitive fallbacks derived from `_DATABASE_DEFAULTS`. Missing critical variables raise `ConfigurationError` to fail fast.[F:storage-backend/core/config.py L1-L214][F:storage-backend/core/config.py L215-L309]
- Importing `core.clients.ai` immediately initialises every available SDK client (OpenAI, Anthropic, Gemini, Groq, Perplexity, DeepSeek, xAI) based on which API keys are present, so only import it when you expect those side effects.[F:storage-backend/core/clients/ai.py L1-L174]
- Database connectivity is managed via `infrastructure.db.mysql`. `create_mysql_engine` validates DSNs, `get_session_dependency` wraps transactions, and `require_*_session_factory` raises configuration errors when environment variables are absent.[F:storage-backend/infrastructure/db/mysql.py L1-L121][F:storage-backend/infrastructure/db/mysql.py L123-L168]

## Configuration Architecture (New!)

All major configuration parameters are centralized in the `config/` directory, organized hierarchically by feature domain. This provides a single source of truth for all settings.

### Configuration Organization

```
config/
├── environment.py          - Environment detection (development, production, sherlock)
├── api_keys.py            - All API key loading
├── defaults.py            - Truly global defaults
│
├── audio/                 - Audio/STT configuration
│   ├── defaults.py       - Cross-provider audio defaults
│   ├── models.py         - Model aliases
│   ├── prompts.py        - Transcription prompts
│   └── providers/        - Provider-specific (Deepgram, OpenAI, Gemini)
│
├── tts/                   - Text-to-speech configuration
│   ├── defaults.py       - TTS defaults
│   └── providers/        - ElevenLabs, OpenAI configs
│
├── realtime/              - Realtime chat configuration
│   ├── defaults.py       - Realtime defaults
│   └── providers/        - OpenAI Realtime, Gemini Live
│
├── image/                 - Image generation configuration
│   ├── defaults.py       - Image defaults
│   ├── aliases.py        - Model aliases
│   └── providers/        - OpenAI, Stability, Flux, Gemini, xAI
│
├── video/                 - Video generation configuration
│   ├── defaults.py       - Video defaults
│   ├── models.py         - Model mappings
│   └── providers/        - Gemini Veo, OpenAI Sora, KlingAI (V1/V2/V2.6/O1)
│
├── semantic_search/       - Semantic search configuration
│   ├── defaults.py       - Search defaults
│   ├── qdrant.py         - Qdrant connection
│   ├── embeddings.py     - Embedding config
│   └── utils/            - Collection resolution
│
├── browser/               - Browser automation configuration
│   ├── defaults.py       - Browser defaults
│   ├── aliases.py        - Model aliases
│   └── cleanup.py        - File retention
│
├── database/              - Database configuration
│   ├── defaults.py       - Pool settings
│   └── urls.py           - Database URLs
│
├── sidecar/               - Claude sidecar configuration
│   └── claude_code.py    - Sidecar connection settings
│
├── text/                  - Text generation (LLM) configuration
│   ├── defaults.py       - Cross-provider text defaults
│   └── providers/        - Per-provider model configs
│       ├── openai/
│       ├── anthropic/
│       ├── gemini/
│       └── ...
│
└── agentic/               - Agentic workflow configuration
    ├── settings.py       - Loop iterations, timeouts
    ├── profiles.py       - Tool profiles
    ├── prompts.py        - Tool descriptions
    └── utils/            - Helper functions
```

### How to Use Configuration

**Import from config/ subdirectories:**
```python
# Audio configuration
from config.audio import DEFAULT_TRANSCRIBE_MODEL
from config.audio.providers import deepgram, gemini, openai

# TTS configuration
from config.tts.providers.elevenlabs import DEFAULT_VOICE_ID

# Video configuration
from config.video.providers.klingai import API_BASE_URL

# Semantic search
from config.semantic_search import get_collection_for_mode

# Database
from config.database import MAIN_DB_URL, POOL_SIZE

# Text providers
from config.text.providers import MODEL_CONFIGS
```

**Backward compatibility:**
`core.config` still works for essential settings:
```python
from core.config import settings, API_KEYS, ENVIRONMENT
```

### Adding New Configuration

When adding new features, follow this pattern:

1. **Create dedicated config directory:** `config/<feature>/`
2. **Separate values from utilities:**
   - `defaults.py` - Human-readable parameter = value
   - `utils/` - Helper functions (getters, setters, validators)
3. **Provider-specific config:** `config/<feature>/providers/<provider>.py`
4. **Update `config/<feature>/__init__.py`:** Export public API
5. **Never hardcode defaults in implementations** - Always reference config/

### Configuration Best Practices

- **Single source of truth:** All config in `config/`, never scattered in features/providers
- **Hierarchical organization:** Group by domain (audio, tts, video, etc.)
- **Separation of concerns:** Values separate from utility functions
- **Human-readable:** Easy to find and adjust values
- **Provider isolation:** Provider-specific config in dedicated files
- **Environment-aware:** Use environment variables with sensible defaults

For provider-specific configuration details, see respective `config/<domain>/` modules.

## Provider & model architecture
- Providers register themselves at import time. For example, `core/providers/__init__.py` calls `register_text_provider`, `register_image_provider`, `register_video_provider`, `register_audio_provider`, `register_tts_provider`, and `register_realtime_provider` to populate the factory maps.[F:storage-backend/core/providers/__init__.py L1-L52]
- `core/providers/resolvers.py` resolves provider instances based on request settings and validated model names. It attaches `ModelConfig` data to text providers so downstream services can respect capability flags (reasoning, temperature limits, etc.).[F:storage-backend/core/providers/resolvers.py L1-L200]
- The model registry lives in `core/providers/registry`. It normalises aliases, falls back to `gpt-5-nano`, and exposes helpers to list models/providers. When you add a new model, update `MODEL_CONFIGS`/`MODEL_ALIASES` so the registry can resolve it consistently.[F:storage-backend/core/providers/registry/registry.py L1-L70]
- Realtime transports (OpenAI Realtime, Gemini Live) use the same registration pattern. Add new transports under `core/providers/realtime/` and register them through `register_realtime_provider` to expose them to the `RealtimeChatService`.[F:storage-backend/core/providers/realtime/factory.py L1-L70]

## Core runtime contracts
- API payloads: use `ApiResponse`, `ok`, and `error` to wrap payloads and metadata. The schemas accept either strings or structured messages so legacy clients remain compatible.[F:storage-backend/core/pydantic_schemas/api_envelope.py L14-L52]
- Errors: convert `ValidationError`, `ConfigurationError`, `ProviderError`, and `ServiceError` into HTTP payloads with `core.http.errors`. This keeps the frontend consistent and reduces duplicated error-handling code.[F:storage-backend/core/http/errors.py L1-L44]
- Streaming: reuse `StreamingManager` for websocket and HTTP streaming. Text/audio providers should call `manager.collect_chunk(...)` and, when auto-TTS is desired, register a queue via `manager.register_tts_queue()` so duplicated chunks reach the background synthesiser.[F:storage-backend/core/streaming/manager.py L15-L130]
- Exceptions: raise the typed errors defined in `core.exceptions`. Avoid raising generic `Exception`; routers already translate the typed errors into consistent responses.[F:storage-backend/core/exceptions.py L1-L44]

## Feature modules
Each feature follows the same pattern: request validation (Pydantic schemas) → dependency wiring → service layer → provider/repository orchestration → envelope response.

### Batch API feature
- `BatchService` (`features/batch/services/batch_service.py`) orchestrates job submission, model validation, provider resolution, and result persistence. It stores responses in the `batch_jobs.metadata` JSON column and tracks success/failure counts before marking jobs complete.[F:storage-backend/features/batch/services/batch_service.py L12-L200]
- HTTP endpoints live in `features/batch/routes.py` and expose the submit/status/results/list/cancel surface under `/api/v1/batch/*`. Dependencies require JWT auth via `require_auth_context` and database access via `get_batch_job_repository`.[F:storage-backend/features/batch/routes.py L1-L120]
- Providers implement `generate_batch()` to encapsulate provider-specific APIs (OpenAI Batches, Anthropic Message Batches, Gemini batchGenerateContent). Shared helpers live under `core/providers/batch/`. Providers with `capabilities.batch_api=False` fall back to sequential generation using the default implementation in `BaseTextProvider`.[F:storage-backend/core/providers/text/openai.py L115-L218][F:storage-backend/core/providers/batch/__init__.py L1-L12]
- The `batch_jobs` table tracks job metadata, request counts, expiry timestamps, and optional error payloads. Use `BatchJobRepository` for CRUD operations; never write SQL inline. Jobs expire after 29 days (configurable via `config.batch.defaults`).[F:storage-backend/features/batch/db_models.py L1-L70][F:storage-backend/features/batch/repositories/batch_job_repository.py L1-L115]
- For usage guidance and best practices see `DocumentationApp/batch-api-handbook.md`.

### Text Generation Endpoints (Quick Reference)

All text generation endpoints consolidated for quick lookup:

| Endpoint | Method | Type | Description | File |
|----------|--------|------|-------------|------|
| `/chat/ws` | WebSocket | Streaming | Main entry point - bidirectional streaming with agentic workflows, cancellation support | `features/chat/routes.py` |
| `/chat` | POST | Non-streaming | HTTP endpoint for single request/response | `features/chat/websocket_routes.py` |
| `/chat/stream` | POST | SSE | Server-Sent Events streaming over HTTP | `features/chat/websocket_routes.py` |
| `/chat/session-name` | POST | Non-streaming | Auto-generate session titles using LLM | `features/chat/websocket_routes.py` |
| `/api/v1/batch` | POST | Async | Submit batch text generation job (50% cost savings) | `features/batch/routes.py` |
| `/api/v1/batch/{job_id}` | GET | Non-streaming | Get batch job status | `features/batch/routes.py` |
| `/api/v1/batch/{job_id}/results` | GET | Non-streaming | Retrieve completed batch results | `features/batch/routes.py` |
| `/api/v1/batch` | GET | Non-streaming | List all batch jobs | `features/batch/routes.py` |
| `/api/v1/batch/{job_id}/cancel` | POST | Non-streaming | Cancel a batch job | `features/batch/routes.py` |

**Legacy compatibility endpoints** (for old mobile clients):

| Endpoint | Method | Description | File |
|----------|--------|-------------|------|
| `/api/db` | POST | Action-based routing (`db_new_message`, `db_search_messages`, etc.) | `features/legacy_compat/routes.py` |
| `/api/aws` | POST | Legacy file upload | `features/legacy_compat/routes.py` |

**Notes:**
- Realtime voice chat uses `/chat/ws` with automatic mode detection (query params, model hints, or request type)
- The WebSocket endpoint acts as a **switchboard** routing to standard chat or realtime handlers
- All endpoints require JWT authentication via `Authorization: Bearer <token>` header (WebSocket uses `?token=` query param)

### Chat & Websocket workflows
- HTTP endpoints for text generation live in `features/chat/websocket_routes.py` (`/chat`, `/chat/stream`, `/chat/session-name`). History endpoints live in `features/chat/routes.py`. They wrap `ChatHistoryService`, convert service exceptions into API envelopes, and mount websocket/realtime routers under `/api/v1/chat` and `/chat` respectively.[F:storage-backend/features/chat/routes.py L1-L96][F:storage-backend/features/chat/routes.py L99-L166][F:storage-backend/features/chat/websocket_routes.py L1-L297]
- `ChatHistoryService` (in `service_impl.py`) orchestrates session CRUD, message persistence, prompts, and legacy compatibility. Keep database mutations inside repository methods so transactions stay consistent.[F:storage-backend/features/chat/service_impl.py L1-L82]
- **Websocket endpoint architecture** (`features/chat/websocket.py`, 274 lines) uses concurrent task-based processing with `asyncio.create_task()` and `asyncio.wait()` to handle messages and workflows in parallel. This enables immediate cancellation and responsive user interactions. It authenticates connections, routes messages to appropriate handlers (standard text, audio, realtime), streams events through `StreamingManager`, and delegates special workflows to `features/chat/utils`. Key design principle: Custom workflows must emit all custom events BEFORE calling `manager.signal_completion()` to ensure the frontend receives complete event sequences.[F:storage-backend/features/chat/websocket.py L1-L276][F:storage-backend/features/chat/utils/clarification_workflow.py L1-L120]
- Place new workflow helpers beside existing ones in `features/chat/utils/`. If you need to expose functionality to other modules, re-export it through `features/chat/service/__init__.py` rather than importing implementation modules directly.[F:storage-backend/features/chat/utils/__init__.py L1-L7][F:storage-backend/features/chat/service/__init__.py L1-L12]
- **Message reception** (`features/chat/utils/websocket_message_receiver.py`) handles the complex coordination of receiving new messages while workflows are running. Uses `asyncio.wait()` with timeout to detect both new messages and workflow completion, allowing immediate processing of cancel/control messages.[F:storage-backend/features/chat/utils/websocket_message_receiver.py L1-L200]

#### WebSocket Cancellation & Concurrent Task Processing

**Architectural Shift:** The WebSocket endpoint moved from sequential message processing to **concurrent task-based processing** using `asyncio.create_task()` and `asyncio.wait()` with `FIRST_COMPLETED`. This enables immediate cancellation without queueing delays.

**Concurrent Processing Pattern** (in `features/chat/websocket.py`):
```python
# Main loop processes messages and workflows concurrently
while True:
    receive_task = asyncio.create_task(receive_next_message(...))
    workflow_task = asyncio.create_task(dispatch_workflow(...))  # or None if idle

    done, pending = await asyncio.wait(
        [receive_task, workflow_task],
        return_when=asyncio.FIRST_COMPLETED
    )

    # Process whichever completes first
    if receive_task in done:
        # New message arrived - can interrupt active workflow
    if workflow_task in done:
        # Workflow finished - ready for next request
```

**Why Concurrent Processing?**
1. **Immediate cancellation** - Cancel messages interrupt workflows without waiting for message queue
2. **Responsive UI** - Frontend receives cancel acknowledgment immediately, not after current message processing
3. **Better throughput** - Workflow execution and message reception happen in parallel

**Cancellation Mechanics:**
- WebSocket workflows support user-initiated cancellation via `{"type": "cancel"}` messages sent on the same WebSocket.[F:storage-backend/features/chat/websocket.py L195-L207]
- `WorkflowRuntime` (`features/chat/utils/websocket_runtime.py`) tracks cancellation state via `asyncio.Event` and exposes `cancel()`, `is_cancelled()` methods. Workflows check cancellation status and raise `CancelledError` for graceful cleanup.[F:storage-backend/features/chat/utils/websocket_runtime.py L18-L52]
- Cancelled workflows emit `cancelled` event followed by completion sentinels (`text_not_requested`, `tts_not_requested`). The dispatcher catches `CancelledError`, sends cancellation events, and ensures proper cleanup. Clients use dual-flag completion model (text + TTS flags) to detect full completion.[F:storage-backend/features/chat/utils/websocket_dispatcher.py L223-L242]
- No active workflow? Cancel messages are safely ignored. Rapid cancel/start cycles are supported without resource leaks.

**Critical Streaming Semantics:**
- All WebSocket events use **snake_case** naming (e.g., `text_chunk`, `tts_completed`). See `DocumentationApp/websocket-events-handbook.md` for canonical event reference.
- Always emit custom events (text, audio, tool calls, etc.) BEFORE calling `manager.signal_completion()` to ensure frontend receives all event types.
- `StreamingManager` now handles TTS queue coordination: text chunks are duplicated to a registered TTS queue while simultaneously being sent to WebSocket consumers.[F:storage-backend/core/streaming/manager.py L157-L161]
- `StreamingManager` enforces token-based completion ownership: only the task holding the completion token can call `signal_completion()`, preventing duplicate completion signals and race conditions.[F:storage-backend/core/streaming/manager.py L176-L207]

**Runtime Cleanup:**
- New helper module `features/chat/utils/websocket_runtime_helpers.py` extracted for maintainability contains:
  - `cleanup_runtime()` - Safely closes audio queues and awaits pending runtime tasks
  - `route_audio_frame_if_needed()` - Routes incoming audio frames to active audio workflows
  - `is_audio_stream_frame()` - Detects audio chunks vs control messages
- Called at multiple lifecycle points: after workflow completion, on cancel, and during final cleanup to ensure no resource leaks.[F:storage-backend/features/chat/utils/websocket_runtime_helpers.py L18-L92]

**File Size & Modularity:**
The concurrent processing model required careful decomposition to maintain file size discipline (200-250 lines):
- `core/streaming/manager.py` (253 lines) extracted TTS logic into `core/streaming/tts_queue_manager.py` (98 lines)
- `features/chat/websocket.py` (274 lines) extracted runtime helpers into `features/chat/utils/websocket_runtime_helpers.py` (92 lines)
This ensures each file has a single, clear responsibility and remains maintainable as the codebase evolves.

**Testing Impact & Workarounds:**
The concurrent task-based model introduced a subtle incompatibility with Starlette's TestClient WebSocket. TestClient's blocking `receive_json()` call doesn't properly integrate with `asyncio.wait()` scheduling, causing tests to hang indefinitely waiting for events.

**Solution:** Use real `websockets` library connections instead of TestClient for testing concurrent flows:
- Mark tests with `@pytest.mark.live_api`, `@pytest.mark.requires_docker`
- Gate with `RUN_MANUAL_TESTS=1` environment variable
- Use real websocket connections: `async with websockets.connect(url) as ws`
- Set reasonable timeouts: 30-60 seconds for real API calls

See `DocumentationApp/testing-guide-handbook.md` Section 6 ("Critical Lesson: WebSocket Testing with Concurrent Task Processing") for comprehensive patterns, common pitfalls, and migration checklist.[F:storage-backend/DocumentationApp/testing-guide-handbook.md L557-L847]

#### xAI tool-call workflow
- Pass tool definitions via `settings.text.tools` so both HTTP and websocket flows forward the payload to the xAI provider. The service copies your dict into the provider call, alongside the formatted message history and prompt metadata.[F:storage-backend/features/chat/services/streaming/non_streaming.py L73-L115][F:storage-backend/features/chat/services/streaming/standard_provider.py L55-L104]
- Attach images and files by sending `prompt` as a list of `image_url` / `file_url` items. `format_messages_for_xai` uploads local paths, de-duplicates remote URLs, and returns the generated file ids so metadata can include them later.[F:storage-backend/core/providers/text/xai_format.py L55-L156][F:storage-backend/core/providers/text/xai.py L99-L152]
- Provider responses expose `metadata.tool_calls`, `metadata.uploaded_file_ids`, and set `requires_tool_action` when a tool call pauses the turn. The HTTP `/chat` endpoint mirrors these fields back to the frontend so the UI can trigger a tool executor immediately.[F:storage-backend/core/providers/text/xai.py L152-L205][F:storage-backend/features/chat/service.py L54-L82]
- Streaming emits a `tool_start` event on the main queue and withholds `text_completed` until the tool action finishes. The websocket bridge forwards the event in order (`custom_event` → `text_chunk` → `tool_start` → completion sentinels), so clients should pause their progress indicator until they receive either a follow-up text chunk or a completion message.[F:storage-backend/features/chat/services/streaming/standard_provider.py L86-L145][F:storage-backend/features/chat/utils/websocket_streaming.py L16-L63]

### Semantic Search
- Hybrid vector search enriches user prompts with relevant context from previous conversations. Combines **dense vectors** (OpenAI embeddings for semantic similarity) + **sparse vectors** (BM25 for exact keyword matches) fused via **Reciprocal Rank Fusion (RRF)**.
- Provider layer: `core/providers/semantic/qdrant.py` implements hybrid search using Qdrant Cloud, `embeddings.py` generates OpenAI dense vectors, `bm25.py` generates sparse vectors, `qdrant_indexing.py` handles message indexing.
- Feature layer: `features/semantic_search/prompt_enhancement.py` is the main entry point (`enhance_prompt_with_semantic_context()`), `service/` (mixin pattern) orchestrates search and indexing, `utils/context_formatter.py` formats results for LLM with token budget management.
- Integration: `features/chat/utils/websocket_dispatcher.py` calls prompt enhancement before workflow execution and sends `semanticContextAdded` WebSocket event; `features/chat/services/history/semantic_indexing.py` queues non-blocking indexing after message persistence.
- Configuration: `SEMANTIC_SEARCH_ENABLED` and `SEMANTIC_INDEXING_ENABLED` master switches, `QDRANT_URL`/`QDRANT_API_KEY` credentials, `SEMANTIC_EMBEDDING_MODEL` (text-embedding-3-small or -large), `SEMANTIC_SEARCH_DEFAULT_LIMIT`/`SEMANTIC_SEARCH_CONTEXT_MAX_TOKENS` for search behavior.
- User-level control via `userSettings.general.semantic_enabled` in WebSocket payload; supports filters (message type, tags, date range, session IDs) for fine-grained search.
- Non-blocking architecture: indexing uses `asyncio.create_task()` and doesn't block message creation; rate limiter prevents abuse (default: 60 req/min per customer); circuit breaker handles Qdrant/OpenAI failures gracefully.
- Search modes: `semantic_search_mode` inside `userSettings.semantic` selects `semantic` (dense-only), `hybrid` (dense + sparse, default), or `keyword` (sparse-only). Backend maps modes to collections via `core.config.get_collection_for_mode()` so the frontend never deals with raw collection names.
- Dual indexing: `MultiCollectionSemanticProvider` wraps the Qdrant provider and writes every message to both `chat_messages_prod` (semantic) and `chat_messages_prod_hybrid` (hybrid) collections while reusing the same embedding. Deduplication happens before indexing to avoid duplicate payloads.
- For comprehensive details, see `DocumentationApp/semantic-search-handbook.md`.

```python
from features.semantic_search.service import get_semantic_search_service

service = get_semantic_search_service()
await service.initialize()

# Conceptual search (dense-only)
semantic_results = await service.search(
    query="brainstormed startup ideas",
    customer_id=42,
    search_mode="semantic",
    score_threshold=0.7,
)

# Hybrid search (default, balanced)
hybrid_results = await service.search(
    query="authentication implementation",
    customer_id=42,
    search_mode="hybrid",
    score_threshold=0.3,
)

# Keyword search (BM25 only)
keyword_results = await service.search(
    query="WebSocket event contract",
    customer_id=42,
    search_mode="keyword",
    limit=20,
)
```

### Realtime chat
- `RealtimeChatService` coordinates OpenAI/Gemini realtime sessions, manages per-turn context, and streams provider events to the frontend while persisting transcripts via `ChatHistoryService` when required.[F:storage-backend/features/realtime/service.py L1-L108]
- Session defaults and turn status tracking live in `features/realtime/state.py`. The HTTP router lives under `/realtime/*`, but WebSocket upgrades share the primary `/chat/ws` endpoint via `features/realtime/routes.websocket_router` so clients only need a single URL. Add new realtime providers through `core.providers.realtime` and pass their identifiers via `RealtimeSessionSettings`.[F:storage-backend/features/realtime/state.py L1-L82][F:storage-backend/features/realtime/routes.py L18-L78][F:storage-backend/core/pydantic_schemas/__init__.py L7-L22]

### Audio (Speech-to-text)
- `STTService` normalises Deepgram options, resamples audio when required, and streams transcripts through `StreamingManager`. Use `configure` to apply per-session settings before calling `transcribe_file` or `transcribe_stream`.[F:storage-backend/features/audio/service.py L1-L118][F:storage-backend/features/audio/service.py L120-L198]
- REST endpoints (`/api/v1/audio/...`) live in `features/audio/routes.py`. Websocket streaming is handled by `features/audio/websocket.py`, which shares the same manager plumbing used by chat workflows.[F:storage-backend/features/audio/routes.py L1-L52][F:storage-backend/features/audio/websocket.py L1-L84]
- Keep new audio helpers inside `features/audio/utils.py` so other services can reuse them without cross-feature imports.[F:storage-backend/features/audio/utils.py L1-L78]

### Image generation
- `ImageService` selects providers via `get_image_provider`, validates prompt/dimensions, and optionally uploads the generated bytes to S3. Returning `save_to_db=false` skips S3 and produces an inline `data:` URI.[F:storage-backend/features/image/service.py L1-L64][F:storage-backend/features/image/service.py L66-L110]
- `/image/generate` validates requests, translates provider/storage errors into HTTP exceptions, and wraps responses with `ImageGenerationResponse`. Use `format_validation_error`/`format_provider_error` helpers for all new endpoints in this module.[F:storage-backend/features/image/routes.py L1-L56][F:storage-backend/features/image/routes.py L58-L104]
- **Providers & Models (December 2025)**:
  - **OpenAI**: `gpt-image-1.5` (default), `gpt-image-1`, `gpt-image-1-mini`, `dall-e-3` (legacy). Aliases: `openai-1.5`, `openai-1`.
  - **Flux (Black Forest Labs)**: FLUX.2 generation - `flux-2-pro` (default), `flux-2-max` (highest quality), `flux-2-flex`. Legacy: `flux-dev`, `flux-pro-1.1`, `flux-kontext-pro`. Aliases: `flux-pro`, `flux-max`, `flux-flex`, `flux-1`.
  - **Stability AI**: `core` (default), `sd3.5`, `sd3`, `sdxl` (legacy).
  - **Gemini**: Nano Banana - `gemini-3-pro-image-preview` (Pro, up to 4K), `gemini-2.5-flash-image` (default). Legacy: `imagen-4.0-generate-001`. Aliases: `gemini-pro`, `nano-banana`, `nano-banana-pro`.
  - **xAI**: `grok-2-image`.
- **Image-to-image generation**: Flux supports transforming existing images via the `image_url` request parameter. The service passes `input_image` to the provider for style transfer, modification, or enhancement workflows.
- **Agentic tool integration**: `generate_image` tool (profiles: `general`, `media`) allows LLMs to generate images during agentic workflows. Model options: `flux`, `flux-max`, `openai`, `gemini`, `gemini-pro`.
- Configuration lives in `config/image/` - model aliases in `aliases.py`, provider defaults in `providers/`, global defaults in `defaults.py`.

### Video generation
- `VideoService` mirrors the image flow but with additional provider-specific options (duration, aspect ratio, reference images). It handles both text-to-video and image-to-video flows and persists outputs via `StorageService`.[F:storage-backend/features/video/service.py L1-L118][F:storage-backend/features/video/service.py L119-L207]
- `/video/generate` returns base64 video data when `save_to_db=false` and translates configuration/provider/storage failures into 4xx/5xx responses using the shared HTTP error formatters.[F:storage-backend/features/video/routes.py L1-L74]
- **Providers & Models (December 2025)**:
  - **Google Gemini (Veo)**: `veo-3.1-fast` (default), `veo-3.1-quality`. Resolutions: 720p, 1080p. Features: text-to-video, image-to-video, camera controls.
  - **OpenAI (Sora)**: `sora-2`. Durations: 4, 8, 12 seconds. Features: text-to-video, image-to-video.
  - **KlingAI** (Most Feature-Rich):
    - V1 Family: `kling-v1`, `kling-v1-5`, `kling-v1-6` (multi-image support)
    - V2 Family: `kling-v2-master`, `kling-v2-1`, `kling-v2-5`, `kling-v2-5-turbo`
    - V2.6 Family: `kling-v2-6`, `kling-v2-6-pro` (native audio generation, pro mode only)
    - O1 Family: `kling-o1`, `kling-o1-pro` (unified generation + editing, pro mode only)
- **KlingAI unique features**: Video extension (up to 180s total via `/video/extend`), avatar/lip-sync generation, motion brush with trajectory control (up to 77 points), camera control presets, native audio generation (V2.6/O1).
- **KlingAI implementation architecture**: The provider (`core/providers/video/klingai.py`) delegates to specialized utilities in `core/providers/video/utils/klingai/`:
  - `auth.py` - JWT token generation with 30-minute expiry and caching
  - `models.py` - Pydantic models for camera control, motion brush, task responses
  - `requests.py` - Async HTTP client with polling and cancellation support
  - `validators_basic.py`, `validators_image.py` - Parameter validation per model family
  - `generators_text.py`, `generators_image.py`, `generators_multi.py` - Generation modes
  - `generators_extend.py` - Video extension logic
  - `generators_avatar.py` - Avatar and lip-sync generation
- Configuration lives in `config/video/providers/klingai.py` with environment variables: `KLINGAI_ACCESS_KEY`, `KLINGAI_SECRET_KEY`, `KLINGAI_API_BASE_URL`, `KLINGAI_DEFAULT_MODEL`, etc.

### Storage (S3 attachments)
- `/api/v1/storage/upload` accepts multipart form uploads, validates the extension against the `ALLOWED_FILE_EXTENSIONS` set, and streams the bytes to S3 via `StorageService`. Legacy `{code, success, message, data}` envelopes are returned so chat clients can keep parsing the old schema.[F:storage-backend/features/storage/routes.py L1-L120]
- JSON-encoded fields such as `userInput`/`userSettings` are parsed via `_parse_json_field`; invalid JSON triggers a 400 error with the offending field. Force filenames by setting `userInput.force_filename=true`.[F:storage-backend/features/storage/routes.py L41-L118]
- Dependencies live in `features/storage/dependencies.py` and surface a singleton `StorageService` configured with the AWS credentials found in `core.config`. Errors raised by the service are translated into `api_error` payloads for consistent debugging.[F:storage-backend/features/storage/dependencies.py L1-L52]

### Text-to-speech (TTS)
- `TTSService` now exposes both buffered (`stream_text_audio`) and queue-driven (`stream_from_text_queue`) streaming paths so chat flows can synthesise audio before text completion.[F:storage-backend/features/tts/service.py L18-L66]
- `service_stream_queue.py` spins up the provider stream, emits lifecycle events (`tts_started`/`tts_generation_completed`), and persists merged audio to S3 before returning metadata to the caller.[F:storage-backend/features/tts/service_stream_queue.py L32-L105]
- `service_stream_queue_helpers.py` coordinates ElevenLabs WebSocket ingestion, counts duplicated chunks, and falls back to buffered mode automatically when `supports_input_stream` is `False` (OpenAI).[F:storage-backend/features/tts/service_stream_queue_helpers.py L20-L137]
- Chat streaming uses `TTSOrchestrator` to register the queue with `StreamingManager`, await completion, and hand metadata to the payload builder without blocking text emission.[F:storage-backend/features/chat/services/streaming/tts_orchestrator.py L18-L176]
- HTTP endpoints live in `features/tts/routes.py` and keep returning the legacy `{code, success, message, data}` envelope via `api_ok`/`api_error`. Dependency wiring caches a singleton `TTSService` for reuse across requests.[F:storage-backend/features/tts/routes.py L1-L88][F:storage-backend/features/tts/dependencies.py L1-L36]
- Tests cover the queue duplication contract (`tests/unit/core/streaming/test_manager.py`) and queue streaming service behaviour (`tests/features/tts/test_service_stream_queue.py`). Extend these when adding providers or new telemetry fields.[F:storage-backend/tests/unit/core/streaming/test_manager.py L40-L200][F:storage-backend/tests/features/tts/test_service_stream_queue.py L90-L250]

#### ElevenLabs WebSocket streaming
- `ElevenLabsTTSProvider.stream_from_text_queue` wraps the official streaming endpoint and delegates queue handling to reusable websocket helpers.[F:storage-backend/core/providers/tts/elevenlabs.py L74-L128]
- `core/providers/tts/elevenlabs_websocket.py` resolves chunk schedules, voice settings, and exposes `stream_from_text_queue` that yields base64 audio frames for downstream services.[F:storage-backend/core/providers/tts/elevenlabs_websocket.py L58-L117]
- `core/providers/tts/utils/queue_websocket_streaming.py` handles the bidirectional WebSocket lifecycle: sending queued text chunks, receiving audio frames, and surfacing provider errors with helpful context.[F:storage-backend/core/providers/tts/utils/queue_websocket_streaming.py L1-L129]
- Set `settings.tts.chunk_schedule` in the client payload to tune the ElevenLabs pacing. Omit the field to rely on provider defaults (the helper validates shape and value ranges via the schema validators).[F:storage-backend/features/tts/schemas/requests.py L34-L83]

### Browser Automation
- `BrowserAutomationTool` is registered as an internal tool in the agentic workflow (`core/tools/internal/browser_automation.py`). When LLM requests the tool via function calling, it delegates to `BrowserAutomationService`.
- `BrowserAutomationService` (`features/browser/service.py`) builds a request with user settings, communicates with the isolated browser-automation container via HTTP POST `/execute`, and sends WebSocket events (`browserAutomationStarted`, `browserAutomationCompleted`, `browserAutomationError`) to the frontend.
- The browser-automation container runs independently (image: `betterai/browser-automation:latest`) with browser-use Agent, configurable LLM providers, and VNC monitoring at port 5900. Configuration via environment variables: `BROWSER_AUTOMATION_URL`, `BROWSER_DEFAULT_LLM_PROVIDER`, `BROWSER_DEFAULT_MAX_STEPS`, `BROWSER_TASK_TIMEOUT`.
- User settings control behavior: `settings.browser_automation` includes `enabled`, `llm_provider`, `max_steps`, `timeout`, `use_vision`, `window_width`, `window_height`, `headless`.
- Results from the container include final URL, URLs visited, steps taken, execution time, and optional GIF path. Service wraps these in `ToolExecutionResult` for the agentic workflow to append to conversation history.
- For comprehensive details, see `DocumentationApp/browser-automation-handbook.md`.

### Proactive Agent (Sherlock & Bugsy)
- **Multi-character AI framework** powered by Claude Code CLI running on the development server. Currently supports two characters: Sherlock (proactive detective persona with heartbeats) and Bugsy (codebase Q&A assistant).
- **Architecture**: Frontend apps send messages via REST API → Backend queues to SQS → Poller scripts on dev server consume messages and invoke Claude Code CLI → Responses posted back to backend → Push notifications via WebSocket to user devices.
- **Feature location**: `features/proactive_agent/` contains routes, service, schemas, repositories, WebSocket handler, and connection registry.
- **Key endpoints**:
  - `GET /api/v1/proactive-agent/health` — Health check with active WebSocket connection count
  - `GET /api/v1/proactive-agent/session` — Get or create session for user
  - `POST /api/v1/proactive-agent/messages` — Queue user message to SQS (returns `{queued: true, sessionId}`)
  - `GET /api/v1/proactive-agent/messages/{session_id}/poll` — Poll for agent responses
  - `POST /api/v1/proactive-agent/notifications` — Receive heartbeat/response from poller (server-to-server)
  - `POST /api/v1/proactive-agent/stream` — Receive streaming chunks from Claude Code
  - `WS /api/v1/proactive-agent/ws/notifications` — Real-time push notifications to connected clients
- **WebSocket push notifications**: `connection_registry.py` tracks active WebSocket connections per user. When agent responses arrive, they're pushed instantly if user is connected; otherwise saved to DB for later polling.
- **Database integration**: Reuses existing `ChatSessionsNG`/`ChatMessagesNG` tables with `ai_character_name` filter (e.g., `sherlock`, `bugsy`). Session stores `claude_session_id` for Claude Code session continuity (`--resume` flag).
- **Message limits**: User messages and agent notifications support up to 30,000 characters.
- **Streaming support**: Real-time text streaming via `stream_start`, `text_chunk`, `thinking_chunk`, `stream_end` events pushed over WebSocket.
- For comprehensive details, see `DocumentationApp/sherlock-technical-handbook.md`.

### Legacy Compatibility
- The `features/legacy_compat/` module provides backward-compatible endpoints for older mobile clients (Kotlin Android app) that cannot be updated to use the new API surface.
- **`/api/db` (POST)**: Action-based routing endpoint handling multiple operations via `action` parameter:
  - `db_new_message` — Create a new message in a session (may trigger text generation)
  - `db_search_messages` — List sessions for a user
  - `db_get_user_session` — Get session with messages
  - `db_all_sessions_for_user` — Get all sessions for a user
- **`/api/aws` (POST)**: Legacy file upload endpoint using multipart form data, delegates to `StorageService`.
- Both endpoints return the legacy `{code, success, message, data}` envelope format via `api_ok`/`api_error` helpers.
- Implementation lives in `features/legacy_compat/routes.py`. The module depends on the same services as the modern endpoints but wraps responses in the old schema.[F:storage-backend/features/legacy_compat/routes.py L1-L142]
- **Note:** Do not add new functionality to these endpoints. They exist solely for backward compatibility with clients that cannot be updated.

### Blood, Garmin, and UFC databases
- Blood: `BloodService` filters and serialises test records, while `routes.py` exposes both REST and legacy MediaModel-compatible endpoints. Use `get_blood_session`/`get_blood_service` dependencies to ensure sessions are scoped correctly.[F:storage-backend/features/db/blood/service.py L1-L44][F:storage-backend/features/db/blood/routes.py L1-L84]
- Garmin: `GarminService` coordinates repository calls, date adjustments, and dataset metadata. `features/garmin/routes.py` exposes `/status`, dataset fetchers, and analysis endpoints that combine Garmin and Withings data. Dependency modules resolve both provider stubs and ingestion services so feature teams can swap implementations without touching the router.[F:storage-backend/features/db/garmin/service.py L1-L84][F:storage-backend/features/garmin/routes.py L1-L86]
- UFC: Authentication, fighter listings, and subscription management are handled through `features/db/ufc/service.py` and surfaced in `routes.py`. Always return envelopes via `api_ok` and translate errors to typed payloads to keep the admin tooling stable.[F:storage-backend/features/db/ufc/service.py L1-L118][F:storage-backend/features/db/ufc/routes.py L1-L84]

## Infrastructure services
- `StorageService` uploads generated assets (images, videos, audio) to S3 with deterministic key patterns (`{customer}/{folder}/{timestamp}_{uuid}.ext`). It fails fast when credentials or bucket names are missing.[F:storage-backend/infrastructure/aws/storage.py L1-L82]
- `SqsQueueService` handles delayed/deduplicated messages and automatically stamps payloads with `created_at` when using `enqueue_timestamped_payload`. Use this service when features must trigger downstream workers via AWS queues.[F:storage-backend/infrastructure/aws/queue.py L1-L78]
- MySQL helpers in `infrastructure/db/mysql.py` expose async engines and session factories for main, Garmin, blood, and UFC databases. Always acquire sessions through FastAPI dependencies rather than instantiating engines inside route handlers.[F:storage-backend/infrastructure/db/mysql.py L1-L121][F:storage-backend/infrastructure/db/mysql.py L123-L168]

## Temporary storage utilities
- `persist_upload_file` writes `UploadFile` objects to a predictable temp directory grouped by customer and category (`/tmp/.../storage-backend-ng/<customer>/<category>`). The returned `StoredUpload` exposes the final path, filename, and content type for downstream processing.[F:storage-backend/services/temporary_storage.py L1-L56]

## Testing strategy
- Pytest defaults include asyncio support and opt-in docker-based integration suites (`requires_docker`). Use `pytest -m "not requires_docker"` for a fast unit run and `pytest -m requires_docker` when you need MySQL containers.[F:storage-backend/pytest.ini L1-L8]
- API contract tests live under `tests/api/`, e.g. UFC auth regression tests assert envelope structure and dependency overrides.[F:storage-backend/tests/api/ufc/test_auth_routes.py L1-L118]
- Integration tests under `tests/integration/` spin up disposable databases and exercise repository/service flows end-to-end. Keep fixtures lightweight and reuse the existing factories rather than mocking infrastructure.
- Unit tests in `tests/unit/` cover provider factories, model registry behaviour, and service logic. Extend these suites when you add new providers or change configuration defaults.

## Development guidelines & extension playbooks
1. **Follow the feature layout.** New endpoints belong under `features/<domain>/routes.py` with matching `schemas/` and `service.py`. Keep feature-specific helpers in `features/<domain>/utils/`.
2. **Reuse dependencies.** Expose new services through `dependencies.py` so routers stay declarative. Avoid instantiating repositories directly in route handlers.
3. **Extend internal tools.** To add a new tool to the agentic workflow (like browser automation):
   - Implement the tool class in `core/tools/internal/<tool_name>.py` inheriting from `BaseTool`.
   - Register it in `core/tools/internal/__init__.py`.
   - Add to the tool loop in `features/chat/services/streaming/agentic.py`.
   - Add unit tests under `tests/unit/core/tools/` to verify tool detection and execution.
4. **Extend providers safely.** To add a new AI model or provider:
   - Implement the provider class in the relevant `core/providers/<category>/` package.
   - Register it in `core/providers/__init__.py`.
   - Update `MODEL_CONFIGS`/`MODEL_ALIASES` if the model name should be discoverable through the registry.[F:storage-backend/core/providers/__init__.py L1-L52][F:storage-backend/core/providers/registry/registry.py L1-L70]
   - Add unit tests under `tests/unit/core/providers/` to confirm routing works as expected.
5. **Persist through services.** Database mutations should flow through repository classes so transactions and audit logging remain centralised. Do not perform raw SQL in routers.
6. **Document your changes.** Update this handbook or add companion docs in `DocumentationApp/` whenever you introduce new domains or workflows. The goal is zero tribal knowledge.
7. **Respect streaming semantics.** When creating new websocket workflows, emit custom events before calling `manager.signal_completion()` to prevent dropped messages.[F:storage-backend/features/chat/websocket.py L64-L118]
8. **Keep auth centralised.** Reuse existing helpers such as `authenticate_websocket` and `get_current_user` rather than re-implementing token parsing inside new modules.[F:storage-backend/features/chat/websocket.py L24-L62][F:storage-backend/features/tts/dependencies.py L18-L24]

## Troubleshooting & common pitfalls
- **Missing environment variables:** A `ConfigurationError` indicates the corresponding env var is missing. The error payload includes the `key`—populate it in `.env.local` and restart the container.[F:storage-backend/core/config.py L1-L214][F:storage-backend/core/http/errors.py L14-L44]
- **Streaming hangs:** Ensure every consumer queue receives a `None` sentinel by calling `manager.signal_completion()`, and avoid sending messages after completion (the manager logs a warning and drops the payload). Verify that workflows emit all custom events (text, audio, tool calls) BEFORE calling `signal_completion()`.[F:storage-backend/core/streaming/manager.py L176-L207]
- **Completion token errors:** `CompletionOwnershipError` indicates a workflow is trying to complete without holding the token. Ensure only the top-level dispatcher creates the token and passes it through the workflow call stack. Services and providers should NOT call `signal_completion()`.[F:storage-backend/core/streaming/manager.py L176-L197][F:storage-backend/core/exceptions.py L1-L44]
- **WebSocket tests hang indefinitely:** TestClient-based WebSocket tests with concurrent task processing hang because TestClient's `receive_json()` doesn't integrate with `asyncio.wait()` scheduling. Use real `websockets` library connections instead: mark with `@pytest.mark.live_api`, gate with `RUN_MANUAL_TESTS=1`, and use `async with websockets.connect(url) as ws`. See `DocumentationApp/testing-guide-handbook.md` Section 6 for patterns.[F:storage-backend/DocumentationApp/testing-guide-handbook.md L557-L847]
- **JSON serialization errors:** `RecursionError: maximum recursion depth exceeded` with mock objects indicates circular references. The sanitizer now includes circular reference detection and depth limiting (max 20 levels). If you hit this, check for self-referencing mock attributes or very deep object graphs.[F:storage-backend/core/utils/json_serialization.py L31-L102]
- **Provider selection errors:** When `get_*_provider` raises a `ConfigurationError`, verify the model prefix or register the provider. The error lists available providers to guide debugging.[F:storage-backend/core/providers/resolvers.py L1-L200]
- **Legacy compatibility:** Older clients expect the `{code, success, message, data}` envelope. Use `api_ok`/`api_error` helpers so existing automation continues to function.[F:storage-backend/core/pydantic_schemas/api_envelope.py L29-L52]
- **Temporary files:** Uploaded files are stored under `/tmp/.../storage-backend-ng`. Clean up large artifacts after use to avoid filling the docker volume, especially when running speech workflows repeatedly.[F:storage-backend/services/temporary_storage.py L1-L56]

Keep this document current. When the backend evolves (new providers, workflows, or data stores), update the relevant sections so the next agent can land safely.
