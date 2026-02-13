# Storage Backend Testing Guide

**Last Updated:** 2026-01-12
**Scope:** Pytest test suite organization, manual testing, and WebSocket testing patterns

This handbook explains how to exercise the FastAPI storage backend both automatically (via `pytest`) and manually (via targeted scripts). It reflects the current layout under `docker/storage-backend/`.

**Related:** For WebSocket event names and completion model, see `websocket-events-handbook.md`.

## Quick Reference

**Test Suite Size**: 228 test files | 597 test items | 65 directories | 8 conftest files

**Key Statistics**:
- 557 tests passed in baseline run (122 seconds)
- 40 tests skipped (environment-dependent)
- 47% unit tests, 16% integration tests, 6% feature tests
- 13 pytest markers for fine-grained test selection
- Multiple test execution modes (fast/Docker/live API/manual)

**Fast Commands**:
```bash
# Fast feedback (no Docker) - recommended for development
pytest -m "not requires_docker"

# Full suite (all tests)
pytest

# Docker-backed integration tests
pytest -m requires_docker

# Live provider tests (requires API keys)
pytest -m live_api -s
```

**Directory Structure**:
- `tests/unit/` (108 files) - Pure unit tests, no external dependencies
- `tests/integration/` (36 files) - Multi-service integration, some require Docker
- `tests/features/` (14 files) - Business flow validation
- `tests/manual/` (15 files) - Interactive validation against running backend
- `tests/api/` (5 files) - Route handler tests
- `tests/e2e/` (1 file) - Complete user journeys
- `tests/load/` (1 file) - Concurrent streaming stress tests
- `tests/performance/` (1 file) - Performance benchmarks

## 1. Prerequisites

1. **Python 3.10+ environment.** Create and activate a virtual environment on your development host when running tests outside Docker.
2. **Install backend dependencies.** From the repository root:
   ```bash
   cd docker/storage-backend
   pip install -r requirements.txt
   ```
   The requirements file already ships `pytest`, `pytest-asyncio`, `testcontainers`, `httpx`, `websockets`, and other libraries used across the suite.
3. **Optional provider credentials.** Some tests hit real APIs or require Docker. Export any secrets before running those subsets:
   ```bash
   export OPENAI_API_KEY=...
   export ANTHROPIC_API_KEY=...
   export GOOGLE_API_KEY=...
   export RUN_MANUAL_TESTS=1  # only for Gemini manual checks
   ```
4. **Docker daemon (integration-only).** Tests marked `requires_docker` spin up ephemeral MySQL containers through Testcontainers. Run them from a host that can talk to Docker (not from the backend container).

## 2. Automated Test Suite (pytest)

The full test tree lives at `docker/storage-backend/tests/` and contains **228 test files** organized across 65 directories. Test files are grouped by layer and business domain:

| Directory | Files | Purpose |
| --- | --- | --- |
| `tests/api/` | 5 | FastAPI route coverage using `httpx.AsyncClient` and dependency overrides for audio, blood, storage, and UFC endpoints. |
| `tests/features/` | 14 | Service-level tests that exercise chat, audio, image, video, TTS, and other business flows with lightweight provider fakes. |
| `tests/unit/` | 108 | Pure unit tests for core helpers, provider factories, and infrastructure utilities. Largest test category covering core, features, and infrastructure layers. |
| `tests/integration/` | 36 | End-to-end flows and repository checks. Subdirectories include `chat/`, `audio/`, `realtime/`, `tools/`, `tts/`, `garmin/`, `blood/`, and `ufc/`, each with their own `conftest.py` for database or service setup. |
| `tests/e2e/` | 1 | End-to-end agentic workflow tests exercising complete user journeys. |
| `tests/regression/` | 1 | Legacy parity harnesses that protect API envelopes and payload formats (chat history envelope). |
| `tests/manual/` | 15 + 1 .sh + 1 .md | Opt-in scripts that target a running backend. They can be invoked via `pytest` or executed directly with Python/shell. Includes comprehensive testing checklist. |
| `tests/load/` | 1 | Load tests for concurrent streaming and system stress testing. |
| `tests/performance/` | 1 | Performance benchmarks for agentic workflows and other performance-critical paths. |
| `tests/utils/` | 2 | Shared helpers: `live_providers.py` (skips live API tests when credentials are unavailable) and `streaming_tts_test_helpers.py` (deterministic TTS test stubs). |
| `tests/helpers/` | 1 | Environment and service validation utilities (`is_semantic_search_available()`, `is_garmin_db_available()`, etc.). |
| `scripts/` | 5 test scripts | Manual verification and benchmark scripts for milestone features (M2 semantic search components, M6 filtering, batch API, semantic E2E). These are collected by pytest but skip by default to avoid live service dependencies. |

**Test Distribution by Type:**
- **Unit tests**: 47% (108 files) - Fast, no external dependencies
- **Integration tests**: 16% (36 files) - Multi-service integration
- **Feature tests**: 6% (14 files) - Business flow validation
- **Manual tests**: 7% (15 files) - Interactive validation
- **API/E2E/Load/Performance/Regression**: 24% (55 files) - Specialized testing

### 2.1 Global configuration

* `pytest.ini` defines **13 test markers** for fine-grained test selection:
  * `asyncio` – async tests that need an event loop.
  * `anyio` – tests requiring AnyIO-powered async support.
  * `requires_docker` – suites that depend on the local Docker daemon and Testcontainers (UFC, Garmin, Blood repositories).
  * `live_api` – tests that reach real third-party APIs (OpenAI, Anthropic, Gemini). These modules usually check environment variables via `tests/utils/live_providers.py` and skip automatically when credentials are missing.
  * `integration` – integration tests that interact with multiple services or subsystems (marker defined but currently not widely used in favor of directory-based organization).
  * `requires_semantic_search` – tests requiring semantic search configuration (OPENAI_API_KEY + Qdrant URL + semantic_search_enabled setting).
  * `requires_garmin_db` – tests requiring Garmin database configuration (GARMIN_DB_URL environment variable).
  * `requires_ufc_db` – tests requiring UFC database configuration (UFC_DB_URL environment variable).
  * `requires_sqs` – tests requiring AWS SQS queue service (AWS credentials).
  * `requires_openai` – tests requiring OpenAI API key.
  * `requires_google` – tests requiring Google/Gemini API key.
  * `requires_anthropic` – tests requiring Anthropic API key.
* `pytest.ini` also configures **warning filters** to suppress known deprecation warnings from third-party libraries (Pydantic, FastAPI, Google GenAI, WebSockets).
* `tests/conftest.py` injects the repository root into `sys.path` and pins AnyIO to the `asyncio` backend by default so `import core...` works regardless of the working directory. It also provides:
  * **Session-scoped fixtures** for JWT auth token generation (`auth_token`, `auth_token_factory`, `auth_token_secret`).
  * **Service availability fixtures** (`require_semantic_search`, `require_garmin_db`, `require_ufc_db`, `require_sqs`) that skip tests when required services are not configured.
  * **Cleanup fixtures** that ensure proper shutdown of httpx transports used by AI SDK clients.
  * **Helper namespace** (`pytest.helpers`) exposing service availability check functions for use in custom skip conditions.

### 2.2 Common commands

| Scenario | Command | Notes |
| --- | --- | --- |
| Fast feedback inside the backend container | `pytest -m "not requires_docker"` | Runs unit, feature, API, and most integration tests without touching Docker. |
| Full regression from a host with Docker | `pytest -m requires_docker` | Launches suites that provision temporary MySQL containers (Blood, Garmin, UFC). |
| All tests | `pytest` | Executes every module. `requires_docker` and `live_api` suites still skip automatically if prerequisites are missing. |
| Only live-provider checks | `pytest -m live_api -s` | Requires real credentials; see environment variables above. |

### 2.3 Execution environment matrix

| Test slice | Marker(s) | Where to run | Notes |
| --- | --- | --- | --- |
| **Unit, feature, API, realtime, and most chat integrations** | default | Inside the backend container | Works with the dev container's Python toolchain. Includes the new audio-direct workflow, Responses API routing, realtime chat flows, and Claude sidecar mocks. 【F:docker/storage-backend/tests/features/chat/test_audio_direct_workflow.py†L1-L200】【F:docker/storage-backend/tests/features/test_responses_api_workflow.py†L1-L115】【F:docker/storage-backend/tests/integration/realtime/test_openai_flow.py†L1-L160】 |
| **Database-backed integrations** | `requires_docker` | Host shell with Docker daemon access | Blood, Garmin, and UFC repository tests spin up MySQL via Testcontainers and therefore skip in the dev container. 【F:docker/storage-backend/tests/integration/blood/test_repositories.py†L1-L40】【F:docker/storage-backend/tests/integration/garmin/test_repositories.py†L1-L45】【F:docker/storage-backend/tests/integration/ufc/test_auth_repositories.py†L1-L35】 |
| **Garmin router smoke tests** | `requires_docker` + production config | Host shell with production `.env` | Routes only load when `ENVIRONMENT=production`; skip in local dev runs unless you mirror that configuration. 【F:docker/storage-backend/tests/integration/features/garmin/test_garmin_routes.py†L1-L45】 |
| **Live provider verification** | `live_api` | Anywhere with valid API keys | Requires provider credentials. Skips gracefully when `tests/utils/live_providers.require_live_client` cannot build the client. 【F:docker/storage-backend/tests/unit/core/providers/text/test_chat_history_handling.py†L1-L118】【F:docker/storage-backend/tests/utils/live_providers.py†L19-L59】 |
| **Manual opt-in suites** | Custom skip guards | Backend container (with running API) | Gated by `RUN_MANUAL_TESTS=1` (plus provider keys / DB URLs as needed). 【F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py†L1-L113】【F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py†L1-L48】【F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py†L1-L56】 |

### 2.4 Test fixtures and conftest files

The test suite uses **8 conftest.py files** organized hierarchically to provide fixtures at different scopes:

#### Root Level (`tests/conftest.py`)
* **JWT authentication**: `auth_token`, `auth_token_factory`, `auth_token_secret` fixtures for authenticated requests
* **Service availability**: `require_semantic_search`, `require_garmin_db`, `require_ufc_db`, `require_sqs` fixtures that skip tests when services are not configured
* **Cleanup**: `close_ai_clients` ensures proper shutdown of httpx transports used by AI SDK clients
* **Helper namespace**: `pytest.helpers` exposes service check functions (`is_semantic_search_available()`, `is_garmin_db_available()`, etc.)
* **AnyIO backend**: Pins to `asyncio` backend for consistent async behavior

#### Integration Tests (`tests/integration/conftest.py`)
* **WebSocket URL factory**: `websocket_url_factory` builds authenticated WebSocket URLs with JWT tokens
* **Chat test client**: `chat_test_client` provides FastAPI TestClient with WebSocket support

#### Chat Integration (`tests/integration/chat/conftest.py`)
* **In-memory SQLite**: Session-scoped `engine` fixture with `aiosqlite` for fast database tests
* **Transaction isolation**: `session` fixture with automatic rollback after each test
* **No Docker required**: Uses SQLite instead of MySQL for faster test execution
* **WebSocket support**: `chat_test_client` with `/chat/ws` endpoint wired to production handlers

#### Database-Backed Integrations (UFC, Garmin, Blood)
All three share the same pattern via Testcontainers:
* **`tests/integration/ufc/conftest.py`** – MySQL 8.0 container with UFC schema
* **`tests/integration/garmin/conftest.py`** – MySQL 8.0 container with Garmin schema
* **`tests/integration/blood/conftest.py`** – MySQL 8.0 container with Blood schema

Each provides:
* **`mysql_container`**: Session-scoped MySQL Testcontainer
* **`engine`**: AsyncEngine connected to the container
* **`apply_schema`**: Schema creation using `infrastructure.db.prepare_database`
* **`session`**: Transaction-scoped AsyncSession with automatic rollback
* **Requires Docker**: Tests skip when Docker daemon is not accessible

#### Manual Tests (`tests/manual/conftest.py`)
* **Environment guards**: Skips tests when `RUN_MANUAL_TESTS` not set
* **Backend authentication**: `token` fixture authenticates against running backend using `GEMINI_MANUAL_EMAIL`/`GEMINI_MANUAL_PASSWORD`
* **Audio fixtures**: `audio_path` resolves WAV file from `GEMINI_MANUAL_AUDIO_PATH`
* **Graceful skipping**: Tests skip cleanly when prerequisites are missing

#### Unit Tests - Text Providers (`tests/unit/core/providers/text/conftest.py`)
* **Gemini background loop**: `gemini_background_loop` runs on separate thread for Gemini SDK compatibility
* **Live provider**: `gemini_text_provider` fixture proxies SDK calls to background loop
* **Safe teardown**: Properly closes background event loop after test session

**Understanding this fixture hierarchy helps when adding new tests: reuse existing factories instead of rebuilding engines or clients from scratch.**

### 2.5 Test utilities and helpers

The test suite provides shared utilities in two locations:

#### Environment and Service Validation (`tests/helpers/__init__.py`)
**Purpose**: Centralized service availability checks and prerequisite validation.

**Service Availability Functions**:
* `is_semantic_search_available()` – Checks OPENAI_API_KEY and semantic_search_enabled setting
* `is_garmin_db_available()` – Checks GARMIN_DB_URL and garmin_enabled setting
* `is_ufc_db_available()` – Checks UFC_DB_URL
* `is_sqs_available()` – Checks AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
* `is_openai_available()` – Checks OPENAI_API_KEY
* `is_google_available()` – Checks GOOGLE_API_KEY
* `is_anthropic_available()` – Checks ANTHROPIC_API_KEY
* `get_missing_prerequisites(service)` – Returns list of missing environment variables/config for a service

**Usage**: These functions are used by conftest fixtures and `@pytest.mark.skipif` decorators. They're also exposed via `pytest.helpers` namespace for custom skip conditions.

#### Streaming and Provider Test Utilities (`tests/utils/`)

**`streaming_tts_test_helpers.py`** – Deterministic TTS streaming stubs:
* **`StubTTSService`** – Emulates TTS service without real API calls
  * Supports parallel streaming (`stream_from_text_queue`)
  * Supports sequential fallback (`stream_text`)
  * Configurable delays for timing tests
* **`install_streaming_stubs()`** – Monkeypatch function to replace production streaming pipeline with stubs
* **`make_settings()`** – Factory for canonical chat settings payloads
* **Usage**: Integration, performance, and load tests use these stubs for predictable, fast execution

**`live_providers.py`** – Live provider integration utilities:
* **`require_live_client(client_key, env_var)`** – Skip test if SDK client unavailable (checks `core.clients.ai.ai_clients` registry)
* **`skip_if_transient_provider_error(exc, provider_name)`** – Convert transient failures to skips instead of hard failures
* **Detects**: Rate limits, auth issues, API key problems, capacity issues, quota exceeded
* **Usage**: Prevents flaky test failures when testing against real provider APIs

#### Semantic Search Test Utilities

The semantic search test infrastructure provides deterministic testing through stub implementations that avoid dependencies on live Qdrant or tiktoken libraries:

**Stub Modules** (`tests/unit/features/chat/utils/test_websocket_dispatcher_semantic.py`):
* **Qdrant stubs** – When `qdrant_client` is not installed, the test creates stub classes for `AsyncQdrantClient`, `Distance`, `Filter`, `MatchValue`, `PointStruct`, `VectorParams`, and other Qdrant models. This allows semantic search tests to run without a live vector database connection.
* **Tiktoken stubs** – Provides a `_StubEncoding` class that simulates token encoding/decoding using character ordinals, eliminating the dependency on the actual tiktoken library during unit tests.

**Test Helpers**:
* **`DummySemanticService`** – Returns pre-configured context strings and tracks search parameters (limit, score_threshold, tags, date_range, message_type, session_ids) for verification.
* **`DummyManager`** – Collects emitted events for assertion, avoiding actual WebSocket communication.
* **`DummyTokenCounter`** – Simple word-count-based token counter for predictable test results.
* **`DummyRateLimiter`** – Configurable allow/deny rate limiter that records customer_id calls.
* **`enable_semantic_search` fixture** – Auto-use fixture that patches `app_settings` to enable semantic search and installs the dummy rate limiter for all tests in the module.

**Coverage**:
* Settings parsing with global flag precedence and user configuration override
* Prompt enhancement with semantic context injection and metadata tracking
* Filter validation and application (tags, date ranges, message types, session IDs)
* Event emission for semantic context added (`customEvent` with `semanticContextAdded` type)
* Rate limiting behavior and customer ID tracking
* Graceful degradation when semantic search is disabled or rate limited

### 2.6 Live-provider coverage

Gemini still requires a long-lived event loop. `tests/unit/core/providers/text/conftest.py` provides a `gemini_text_provider` fixture that proxies SDK calls to a background loop and tears it down safely after the session. Modules under `tests/unit/core/providers/text/` mark themselves with `pytest.mark.live_api`; they will skip unless `GOOGLE_API_KEY` is configured and the Gemini client initialises successfully.

Other live tests (e.g., `tests/manual/test_chat_history_manual.py`) use `tests/utils/live_providers.py` helpers to skip cleanly on missing credentials or transient rate limits.

### 2.7 Test coverage by domain

The test suite provides comprehensive coverage across all major backend domains:

#### Text Provider Coverage (19 test files)
**Core providers** (`tests/unit/core/providers/text/`): 15 files
* **Anthropic**: Event handling, tools/requires_action patterns
* **OpenAI**: Tool events, streaming, Responses API format, Responses tools
* **Gemini**: Config, events, format, Gemini-specific requires_action, audio streaming
* **xAI**: Format and provider implementation
* **Claude Code**: Sidecar integration
* **Cross-provider**: Chat history handling, message alternation, model alias parameters, system prompt placement

**Integration tests**: 4 files covering Claude sidecar streaming, Claude Code WebSocket flow, edit message flow, and chat history workflow

**Coverage**: All major text providers (OpenAI, Anthropic, Gemini, xAI, Groq, DeepSeek) with event format validation, tool integration, streaming behavior, and error handling.

#### Chat Feature Coverage (23 test files)
**Unit tests** (`tests/unit/features/chat/`): 16 files
* Agent settings extraction, agentic outcome, chat history, reasoning parameters
* Repository transactions, semantic indexing, system prompt, tool injection
* Content processor, WebSocket dispatcher with semantic enhancement
* Streaming services: deep research, persistence, standard provider, tool events
* History session management

**Feature tests** (`tests/features/chat/`): 6 files
* Audio direct (Gemini workflow, general workflow), audio workflow, image workflow
* xAI endpoints, chat service, realtime history formatter

**Integration tests** (`tests/integration/chat/`): 7 files + 2 READMEs
* Agentic workflow, Claude sidecar (integration + streaming), edit message flow
* History routes, repositories, Claude Code WebSocket flow

**Coverage**: Complete chat feature stack from core business logic through streaming services to API integration.

#### Audio and Realtime Coverage (17 test files)
**Audio tests**: 8 files
* **Unit**: Deepgram timeout, settings, provider selection, transcription rewrite (4 files)
* **Feature**: Providers, service, streaming workflow (3 files)
* **Integration**: Transcribe endpoint (1 file)

**Realtime tests**: 9 files
* **Unit**: Context, error classification, errors/validation, event payloads, finalization, schemas, state, turn state updates (8 files in `tests/unit/features/realtime/`)
* **Integration**: OpenAI Realtime flow (1 file)

**Coverage**: Audio transcription (streaming + static), realtime state management, error handling, event payloads, and provider integration.

#### Tool System Coverage (12 test files)
**Unit tests** (`tests/unit/core/tools/`): 9 files
* Base classes, error handling, executor, factory, profiles, registry
* Image generation, text generation, video generation tools

**Integration tests** (`tests/integration/tools/`): 3 files
* Image generation tool, text generation tool, video generation tool integration

**Coverage**: Complete tool lifecycle from registration and factory creation through execution and error handling.

#### Streaming Architecture Coverage (9 test files)
**Core streaming** (`tests/unit/core/streaming/`): 3 files
* Streaming manager, token management, streaming types

**Chat streaming services** (`tests/unit/features/chat/services/streaming/`): 6 files
* Deep research, deep research persistence, standard provider, requires_action, tool events, tools

**Coverage**: Streaming manager, queue fan-out, completion token lifecycles, tool-call formatting, and deep research workflows.

#### Domain-Specific Features
**Garmin**: 8 files (7 unit, 1 integration) – Activity/sleep schemas, dependencies, service, provider, tasks, translators, repositories
**UFC**: 6 files (3 unit, 3 integration) – Service, auth service, mutations, repositories (auth, mutation, general)
**Blood**: 2 files (1 unit, 1 integration) – Service, repositories
**TTS**: 5 files (2 unit, 3 integration) – Service, utils, ElevenLabs WebSocket, service WebSocket routing
**Semantic Search**: 2 unit files + 5 scripts – Settings parser, semantic service, dependencies

#### Infrastructure Coverage (6 test files)
* **AWS**: Clients, SQS queue (2 files)
* **Database**: MySQL factory, session scope (2 files)
* **Config**: OpenAI models (1 file)
* **Infrastructure milestone**: General infrastructure tests (1 file)

### 2.8 Coverage highlights added in the latest backend refresh

* **Audio-direct and multimodal chat workflows.** New suites under `tests/features/chat/` cover the audio-direct Gemini pipeline end to end (placeholder messages, websocket ingestion, and request-type switching) so regressions surface immediately. 【F:docker/storage-backend/tests/features/chat/test_audio_direct_gemini.py†L1-L120】【F:docker/storage-backend/tests/features/chat/test_audio_direct_workflow.py†L1-L200】
* **Realtime service orchestration.** Integration checks in `tests/integration/realtime/` exercise OpenAI realtime services, verifying websocket session wiring, audio fan-out, and persistence hooks. 【F:docker/storage-backend/tests/integration/realtime/test_openai_flow.py†L1-L160】
* **Responses API routing.** `tests/features/test_responses_api_workflow.py` ensures model metadata picks the correct API (Responses vs. Chat Completions) and validates reasoning payloads for GPT-5 Nano. 【F:docker/storage-backend/tests/features/test_responses_api_workflow.py†L1-L115】
* **Claude sidecar + edit flows.** Integration layers now cover Claude code sidecar streaming, the edit-message workflow, and websocket framing so Claude regressions are caught without manual runs. 【F:docker/storage-backend/tests/integration/chat/test_claude_sidecar_integration.py†L1-L220】【F:docker/storage-backend/tests/integration/chat/test_edit_message_flow.py†L1-L200】
* **Realtime tool and streaming managers.** Unit suites under `tests/unit/features/chat/services/streaming/` and `tests/unit/core/streaming/` pin down tool-call formatting, queue fan-out, and completion token lifecycles. 【F:docker/storage-backend/tests/unit/features/chat/services/streaming/test_tool_events.py†L1-L160】【F:docker/storage-backend/tests/unit/core/streaming/test_manager.py†L1-L140】
* **Semantic search infrastructure.** Comprehensive test coverage for the new semantic search feature includes settings parsing, prompt enhancement with context, filtering (tags, message types, date ranges, session IDs), WebSocket dispatcher integration, and rate limiting. Tests verify that semantic context is properly added to prompts and that filters are correctly applied.
  * `tests/unit/features/test_semantic_search_settings_parser.py` - Settings parser respecting global flags and user configuration
  * `tests/unit/features/chat/utils/test_websocket_dispatcher_semantic.py` - WebSocket dispatcher semantic enhancement with filtering and event emission
  * `tests/manual/test_semantic_provider.py` - Manual verification against live semantic search service
  * `scripts/test_m2_feature_module.py` - M2 milestone tests for TokenCounter, MetadataBuilder, ContextFormatter, and service initialization
  * `scripts/test_m6_filtering.py` - M6 milestone tests for tag-based and message-type filtering against live MySQL and Qdrant instances
* **Agentic workflow testing pyramid.** Complete test coverage from unit through E2E: `test_agentic_outcome.py` (unit), `test_agentic_tool_validation.py` (feature), `test_agentic_workflow.py` (integration), `test_agentic_workflow_e2e.py` (E2E), `test_websocket_agentic.py` (manual), `test_agentic_performance.py` (performance).

## 3. Manual and Exploratory Testing

Manual scripts live alongside the automated suite so they can take advantage of shared utilities and dependency management. Run them against a locally running backend (`uvicorn main:app --reload`) or a remote deployment by updating the base URL/token values inside each script.

| Location | Purpose | How to run | Requirements |
| --- | --- | --- | --- |
| `tests/manual/test_websocket.py` | Streams a chat response over `/chat/ws`, printing every event. | `pytest tests/manual/test_websocket.py -s` or `python tests/manual/test_websocket.py` | Backend listening on `ws://localhost:8000/chat/ws`; `websockets` package (installed via requirements). |
| `tests/manual/test_chat_history_manual.py` | Validates Anthropic and OpenAI reasoning support using the real providers. | `pytest -m live_api tests/manual/test_chat_history_manual.py -s` | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Skips automatically if credentials or clients are missing. |
| `tests/manual/test_gemini_audio_complete.py` | End-to-end Gemini audio verification (streaming STT, Audio Direct, DB persistence). | `RUN_MANUAL_TESTS=1 pytest tests/manual/test_gemini_audio_complete.py -s` | Running backend, valid login credentials for `/api/v1/auth/login`, `GOOGLE_API_KEY`, audio fixture at `tests/fixtures/test_audio.wav`. |
| `tests/manual/test_gemini_streaming_manual.py` | Sends a local WAV file through the streaming transcription path. | `RUN_MANUAL_TESTS=1 python tests/manual/test_gemini_streaming_manual.py /path/to/audio.wav` | Same as above plus an audio sample on disk. |
| `tests/manual/test_openai_streaming_basic.py` | Connectivity smoke test for the OpenAI streaming speech provider using mock audio chunks. | `RUN_MANUAL_TESTS=1 pytest tests/manual/test_openai_streaming_basic.py -s` | `RUN_MANUAL_TESTS=1`, `OPENAI_API_KEY`, backend dependencies installed. 【F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py†L1-L49】 |
| `tests/manual/test_openai_streaming_complete.py` | Drives `get_audio_provider` with a real WAV file and prints timing/event diagnostics. | `python tests/manual/test_openai_streaming_complete.py /path/to/audio.wav [--model both]` | Local audio sample, `OPENAI_API_KEY`, same dependencies as the backend streaming stack. 【F:docker/storage-backend/tests/manual/test_openai_streaming_complete.py†L1-L117】 |
| `tests/manual/benchmark_gemini_audio.py` | Benchmarks Gemini streaming vs. audio-direct throughput. | `python tests/manual/benchmark_gemini_audio.py` | Shares helpers with the manual Gemini suite; requires backend + credentials. |
| `tests/manual/test_token_redaction.py` | Verifies observability helpers redact bearer tokens in logs. | `pytest tests/manual/test_token_redaction.py -s` or `python tests/manual/test_token_redaction.py` | None beyond backend dependencies; prints the masked payload preview. 【F:docker/storage-backend/tests/manual/test_token_redaction.py†L1-L61】 |
| `tests/manual/test_ufc_fighters_query.py` | Exercises the UFC fighters query against a live database and logs timings. | `RUN_MANUAL_TESTS=1 pytest tests/manual/test_ufc_fighters_query.py -s` | `RUN_MANUAL_TESTS=1`, connectivity to the UFC MySQL instance, repository credentials configured. 【F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py†L1-L61】 |
| `tests/manual/test_semantic_provider.py` | Validates semantic search provider integration and context retrieval. | `RUN_SEMANTIC_MANUAL_TESTS=1 pytest tests/manual/test_semantic_provider.py -s` | `RUN_SEMANTIC_MANUAL_TESTS=1`, semantic search enabled in settings, Qdrant connection configured. |
| `tests/manual/test_http.sh` | Curl-based smoke test for `/chat`, `/chat/stream`, and `/chat/session-name`. | `bash tests/manual/test_http.sh` | `curl` and `jq` installed locally; override `BASE_URL` as needed. |
| `scripts/test_m2_feature_module.py` | M2 milestone verification for semantic search components (TokenCounter, MetadataBuilder, ContextFormatter, service initialization). | `pytest scripts/test_m2_feature_module.py -s` or `python scripts/test_m2_feature_module.py` | Semantic search enabled, Qdrant connection for service health check. Tests token counting, metadata building, context formatting, and service initialization. |
| `scripts/test_m6_filtering.py` | M6 milestone verification for semantic search filtering (tags, message types). | `pytest scripts/test_m6_filtering.py -s` (skipped by default) | Requires live MySQL and Qdrant instances with seeded data. Tests tag-based filtering and message-type filtering. Always skipped during regular pytest runs to avoid touching live services. |
| `scripts/test_batch_api.py` | Batch API operations testing. | `python scripts/test_batch_api.py` | Standalone test script for batch API functionality. |
| `scripts/test_semantic_e2e.py` | End-to-end semantic search validation. | `python scripts/test_semantic_e2e.py` | Requires semantic search configuration and live services. |
| `scripts/benchmark_semantic_operations.py` | Semantic search performance benchmarking. | `python scripts/benchmark_semantic_operations.py` | Benchmarks semantic search operations for performance analysis. |

**Additional semantic search management scripts** (not test scripts, but related utilities):
* `scripts/verify_semantic_config.py` - Verify semantic search configuration
* `scripts/backfill_semantic_search.py` - Backfill semantic search data
* `scripts/semantic_search_explorer.py` - Interactive semantic index exploration
* `scripts/semantic_manage_messages.py` - Manage indexed messages
* `scripts/semantic_inspect_index.py` - Inspect Qdrant index contents

These scripts intentionally skip when preconditions are not met so they never break CI.

## 4. Additional End-to-End Utilities

Some legacy helper scripts still live under `python/` for ad-hoc validation outside pytest. The `python/e2e_tests/` directory in particular houses end-to-end checks that call real model providers; to avoid unnecessary spend, they are run manually by QA or developers rather than through CI. Install their lightweight dependencies first (listed in `python/e2e_tests/requirements.txt`). 【F:python/e2e_tests/requirements.txt†L1-L2】

```bash
pip install -r python/e2e_tests/requirements.txt
```

Key entry points include:

| Script | Purpose | How to run | Notes |
| --- | --- | --- | --- |
| `python/e2e_tests/http_chat_test.py` | Smoke-tests the synchronous `/chat` and optional `/chat/session-name` endpoints. | `python python/e2e_tests/http_chat_test.py --base-url https://backend.example.com` | Reads `BACKEND_BASE_URL`/`BACKEND_CUSTOMER_ID` when flags are omitted and prints the model/provider chosen by the backend. 【F:python/e2e_tests/http_chat_test.py†L1-L74】 |
| `python/e2e_tests/websocket_chat_test.py` | Streams events from `/chat/ws` to verify chunk ordering and termination signals. | `python python/e2e_tests/websocket_chat_test.py --prompt "Hello"` | Uses `BACKEND_BASE_URL` to derive the WebSocket URL and logs each message until `complete`/`error`. 【F:python/e2e_tests/websocket_chat_test.py†L1-L63】 |
| `python/e2e_tests/stream_chat_test.py` | Checks the Server-Sent Events `/chat/stream` endpoint and parses SSE frames. | `python python/e2e_tests/stream_chat_test.py --prompt "Status update"` | Requires `requests`; honours `BACKEND_BASE_URL`/`BACKEND_CUSTOMER_ID` for defaults. 【F:python/e2e_tests/stream_chat_test.py†L1-L72】 |
| `python/e2e_tests/image_generation_test.py` | Calls `/image/generate` across multiple providers and optionally saves outputs. | `python python/e2e_tests/image_generation_test.py --providers openai stability` | Accepts JSON overrides, can persist assets to `IMAGE_GENERATION_OUTPUT_DIR`. 【F:python/e2e_tests/image_generation_test.py†L1-L200】 |
| `python/e2e_tests/audio_static_transcription_manual.py` | Submits recordings to `/api/v1/audio/transcribe` and prints a QA summary. | `python python/e2e_tests/audio_static_transcription_manual.py --file sample.wav --action transcribe` | Requires bearer token when auth is enforced; honours model/provider overrides via CLI flags. 【F:python/e2e_tests/audio_static_transcription_manual.py†L1-L200】 |
| `python/e2e_tests/video_text_to_video_manual.py` | Exercises the Veo 3.1 Fast pathway end-to-end and stores the returned clip locally. | `python python/e2e_tests/video_text_to_video_manual.py --output-dir ./runs` | Requires real video-generation credentials; saves bytes to `IMAGE_GENERATION_OUTPUT_DIR` (or the `--output-dir` flag) and honours `BACKEND_BASE_URL`. 【F:python/e2e_tests/video_text_to_video_manual.py†L1-L123】 |
| `python/e2e_tests/video_text_to_video_sora_manual.py` | Minimal text-to-video workflow targeting OpenAI Sora. | `python python/e2e_tests/video_text_to_video_sora_manual.py --prompt "Cloud timelapse"` | Accepts duration/aspect/quality flags and stores the resulting clip locally. 【F:python/e2e_tests/video_text_to_video_sora_manual.py†L1-L144】 |
| `python/e2e_tests/video_image_to_video_manual.py` | Generates a Gemini image and feeds it to Veo 3.1 Fast for image-to-video validation. | `python python/e2e_tests/video_image_to_video_manual.py --image-prompt "..." --video-prompt "..."` | Downloads intermediate assets and persists both the seed image and generated video. 【F:python/e2e_tests/video_image_to_video_manual.py†L1-L200】 |
| `python/e2e_tests/video_image_to_video_sora_manual.py` | Chains Gemini image generation into OpenAI Sora image-to-video calls. | `python python/e2e_tests/video_image_to_video_sora_manual.py --image-prompt "..." --video-prompt "..."` | Masks inline data URLs for logging and saves the resulting video locally. 【F:python/e2e_tests/video_image_to_video_sora_manual.py†L1-L200】 |

Miscellaneous root-level scripts such as `python/test-stream.py`, `python/test-text-audio-stream.py`, and Garmin utilities exercise specific APIs with custom payloads. Review each file before running so you can supply the expected bearer token or environment variables. 【F:python/test-stream.py†L1-L32】

Because these helpers bypass pytest they are not wired into CI—use them for exploratory testing when you need fine-grained control over prompts or streaming behaviour, and coordinate with the QA team before invoking costly providers.

## 5. Test Organization Patterns and Best Practices

Understanding the test suite's organization patterns helps when adding new tests or debugging failures.

### 5.1 Layered Testing Strategy

Tests mirror the codebase architecture with clear separation of concerns:

**Unit Tests** (`tests/unit/`) → `core/`, `features/`, `infrastructure/`
* Pure functions and classes with no external dependencies
* Mocked dependencies using pytest fixtures and monkeypatching
* Fast execution (milliseconds per test)
* Example: `tests/unit/core/providers/text/test_anthropic_events.py`

**Feature Tests** (`tests/features/`) → `features/` services
* Business flow validation with lightweight provider fakes
* Service-level integration within a single domain
* Uses stub services (`StubTTSService`, `DummySemanticService`)
* Example: `tests/features/chat/test_audio_direct_workflow.py`

**Integration Tests** (`tests/integration/`) → Cross-layer integration
* Multi-service integration (database + service + API)
* Uses real database connections (SQLite in-memory or MySQL via Testcontainers)
* WebSocket and streaming integration
* Example: `tests/integration/chat/test_agentic_workflow.py`

**API Tests** (`tests/api/`) → Route handlers
* FastAPI route coverage using `httpx.AsyncClient`
* Dependency overrides to inject test fixtures
* Request/response validation
* Example: `tests/api/audio/test_routes.py`

### 5.2 Provider Testing Pattern

All text providers follow a consistent testing pattern:

1. **Event format tests** - Validate provider-specific event structures
2. **Tool integration tests** - Verify tool calls and requires_action handling
3. **Streaming behavior tests** - Check chunk ordering and completion signals
4. **Error handling tests** - Ensure graceful degradation

**Provider test locations**:
- Core provider logic: `tests/unit/core/providers/text/test_{provider}_*.py`
- Integration: `tests/integration/chat/test_{provider}_*.py`
- Live API validation: Use `pytest.mark.live_api` + `require_live_client()`

### 5.3 Database Testing Strategy

Two approaches based on requirements:

**In-Memory SQLite** (Chat integration tests):
* ✅ Fast execution (no container startup)
* ✅ No Docker daemon required
* ✅ Perfect for CI/CD pipelines
* ❌ SQLite-specific behavior may differ from MySQL
* **Use when**: Testing chat features, WebSocket flows, general database operations

**Testcontainers MySQL** (UFC, Garmin, Blood):
* ✅ Production-like MySQL environment
* ✅ Tests actual MySQL-specific features
* ❌ Requires Docker daemon access
* ❌ Slower startup time (5-10 seconds per test session)
* **Use when**: Testing domain-specific features with MySQL-specific schemas

### 5.4 Fixture Reuse Pattern

Follow the fixture hierarchy to avoid duplication:

```python
# Root conftest (tests/conftest.py)
# ↓ Provides: auth_token, service availability checks

# Integration conftest (tests/integration/conftest.py)
# ↓ Provides: websocket_url_factory, chat_test_client

# Domain conftest (tests/integration/chat/conftest.py)
# ↓ Provides: database engine, session, domain-specific fixtures

# Your test file
def test_my_feature(session, auth_token):
    # Reuse existing fixtures
    pass
```

**Best practices**:
* Reuse existing fixtures instead of creating new ones
* Add domain-specific fixtures to domain conftest files
* Use session scope for expensive setup (database containers)
* Use function scope for test isolation (database sessions)

### 5.5 Test Markers Usage

Use markers to categorize tests and control execution:

```python
# Mark test requiring Docker
@pytest.mark.requires_docker
def test_ufc_repository():
    pass

# Mark test hitting live API
@pytest.mark.live_api
def test_openai_streaming():
    pass

# Conditional skip based on service availability
def test_semantic_search(require_semantic_search):
    # Automatically skipped if semantic search not configured
    pass
```

**Available markers**: `asyncio`, `anyio`, `requires_docker`, `live_api`, `integration`, `requires_semantic_search`, `requires_garmin_db`, `requires_ufc_db`, `requires_sqs`, `requires_openai`, `requires_google`, `requires_anthropic`

### 5.6 Stub and Mock Patterns

The test suite uses different stubbing strategies:

**Stub services** (preferred for deterministic behavior):
```python
from tests.utils.streaming_tts_test_helpers import StubTTSService

stub = StubTTSService()
# Predictable, fast, no external dependencies
```

**Monkeypatching** (for replacing production code):
```python
def test_with_stub(monkeypatch):
    monkeypatch.setattr("module.function", stub_function)
    # Production code calls stub_function
```

**Dependency injection** (for FastAPI routes):
```python
app.dependency_overrides[get_db] = override_get_db
# Routes receive test database instead of production
```

### 5.7 Adding New Tests Checklist

When adding new tests:

1. ✅ **Choose the right layer**: Unit, feature, integration, or API?
2. ✅ **Reuse fixtures**: Check conftest files for existing fixtures
3. ✅ **Add markers**: Does it require Docker, live API, or services?
4. ✅ **Follow naming**: `test_{feature}_{scenario}.py`
5. ✅ **Use stubs for speed**: Prefer stubs over live services in unit tests
6. ✅ **Add to coverage**: Ensure new features have test coverage at multiple layers
7. ✅ **Document special requirements**: Add comments for environment variables or setup

### 5.8 Common Patterns by Domain

**Chat tests**: Use in-memory SQLite, WebSocket test client, stub providers
**Audio tests**: Use mock audio chunks, stub transcription services
**Provider tests**: Use live API markers, `require_live_client()`, event validation
**Database tests**: Use Testcontainers for domain features, SQLite for general cases
**Streaming tests**: Use `StubTTSService`, queue inspection, event ordering checks

## 6. Troubleshooting Tips

* **Tests skipped unexpectedly?** Run `pytest -vv` to see marker reasons. Check that environment variables are exported and that Docker is reachable when running `requires_docker` suites.
* **Import errors during pytest?** Ensure you execute commands from the repository root or rely on the `tests/conftest.py` sys.path shim by running tests through `python -m pytest`.
* **Gemini live tests failing with event loop errors?** Confirm `GOOGLE_API_KEY` is set and the background loop fixture initialised (`gemini` entry appears in `core.clients.ai.ai_clients`).
* **Manual WebSocket scripts timing out?** Verify the backend is running and accessible at `ws://localhost:8000/chat/ws`, or pass an alternate URL via environment variables before executing the script.

Keeping this guide updated alongside the code ensures new contributors immediately know how to exercise both automated and manual coverage for the storage backend.

## 6. Critical Lesson: WebSocket Testing with Concurrent Task Processing

### 6.0 The Problem: TestClient WebSocket Hangs

**Historical Context:** After implementing the cancellation feature with concurrent task processing (`asyncio.create_task()` + `asyncio.wait()`), all TestClient-based WebSocket tests began hanging indefinitely.

**Symptom:** Tests would timeout after 30+ minutes waiting for events that never arrived:
```
tests/integration/test_websocket_chat.py::test_websocket_chat TIMEOUT (after 30 minutes)
tests/features/chat/test_chat_xai_endpoints.py::test_websocket_flow_emits_ordered_tool_call_events TIMEOUT
```

**Root Cause:** Starlette's `TestClient` WebSocket implementation doesn't handle the concurrent task-based message processing pattern correctly:

```python
# This pattern works fine with real WebSocket connections
# but causes TestClient to hang indefinitely:
async def websocket_endpoint(websocket):
    receive_task = asyncio.create_task(receive_next_message(...))
    workflow_task = asyncio.create_task(dispatch_workflow(...))

    done, pending = await asyncio.wait(
        [receive_task, workflow_task],
        return_when=asyncio.FIRST_COMPLETED
    )
```

**Why TestClient fails:** TestClient's receive_json() is a blocking call that doesn't properly integrate with asyncio task scheduling. When multiple concurrent tasks are running, TestClient can't correctly interleave message reception with task completion detection.

### 6.1 The Solution: Use Real WebSocket Connections for Concurrent Tests

**Best Practice:** When testing WebSocket flows that use concurrent task processing, use the `websockets` library instead of TestClient:

```python
# ❌ DON'T use TestClient for concurrent WebSocket patterns
with chat_test_client.websocket_connect("/chat/ws") as ws:
    ws.receive_json()  # Hangs if backend uses asyncio.wait()

# ✅ DO use real websockets library
import websockets
async with websockets.connect("ws://localhost:8000/chat/ws") as ws:
    event = json.loads(await ws.recv())  # Works correctly with concurrent tasks
```

**Implementation Pattern:**
1. Mark tests with `@pytest.mark.live_api` and `@pytest.mark.requires_docker`
2. Use `RUN_MANUAL_TESTS=1` environment flag to gate execution
3. Create async test methods with `@pytest.mark.asyncio`
4. Use real `websockets` library for connection
5. Set reasonable timeouts (30-60 seconds) with `asyncio.wait_for()`

**Example (from `tests/live_api/test_websocket_comprehensive.py`):**
```python
@pytest.mark.asyncio
async def test_basic_chat_flow_with_streaming(self, auth_token_factory):
    token = auth_token_factory()
    url = f"ws://localhost:8000/chat/ws?token={token}"

    async with websockets.connect(url) as ws:
        ready = json.loads(await ws.recv())
        assert ready["type"] == "websocket_ready"

        await ws.send(json.dumps(request))

        text_completed = False
        tts_completed = False
        while True:
            message = await asyncio.wait_for(ws.recv(), timeout=30.0)
            event = json.loads(message)
            event_type = event.get("type")
            if event_type == "text_completed":
                text_completed = True
            elif event_type in ("tts_completed", "tts_not_requested"):
                tts_completed = True
            if text_completed and tts_completed:
                break
```

### 6.2 Event Structure Pitfalls

**Common Mistake #1: Wrong Event Type Names**

All WebSocket events use **snake_case** names. The backend sends tool events as `tool_start` and `tool_result`:

```python
# ❌ WRONG - Using old camelCase names
if event_type == "textCompleted":  # Old name
    ...
if event_type == "toolCall":  # Never existed as top-level
    ...

# ✅ CORRECT - Use snake_case event names
if event_type == "tool_start":
    tool_calls.append(event)
elif event_type == "tool_result":
    tool_results.append(event)
elif event_type == "text_completed":
    text_done = True
```

**Note:** Custom events use wrapper `custom_event` with `eventType` subfield for extensible events (reasoning, charts, etc.).

**Common Mistake #2: Incomplete Request Payloads**

Tests that send minimal request payloads may not trigger the intended behavior. Always match the complete frontend request structure:

```python
# ❌ MINIMAL - May not trigger agentic mode
request = {
    "requestType": "text",
    "userInput": {"prompt": [{"type": "text", "text": "..."}]},
    "userSettings": {"text": {"model": "gpt-4o-mini"}}
}

# ✅ COMPLETE - Matches frontend structure for agentic workflows
request = {
    "requestType": "text",
    "userInput": {
        "prompt": [{"type": "text", "text": "..."}],
        "chat_history": [],
        "session_id": ""
    },
    "userSettings": {
        "text": {
            "model": "gpt-4o-mini",
            "temperature": 0.3,
            "streaming": True
        },
        "general": {
            "ai_agent_enabled": True,
            "ai_agent_profile": "general"
        },
        "image": {
            "model": "flux",
            "number_of_images": 1
        }
    },
    "customerId": 1
}
```

### 6.3 JSON Serialization and Circular References

**The Problem:** When sanitizing objects for JSON serialization (especially mock objects in tests), circular references cause infinite recursion and stack overflow:

```
RecursionError: maximum recursion depth exceeded
core/streaming/manager.py:148: StreamingError
```

**The Fix:** Add circular reference detection and depth limiting to `sanitize_for_json()`:

```python
def sanitize_for_json(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable representations.

    Handles circular references and limits recursion depth.
    """
    return _sanitize_with_context(obj, visited=set(), depth=0)

def _sanitize_with_context(obj: Any, visited: set[int], depth: int) -> Any:
    # Depth limit protection
    if depth > _MAX_DEPTH:
        return f"<max_depth_exceeded: {type(obj).__name__}>"

    # Circular reference detection
    obj_id = id(obj)
    if obj_id in visited:
        return f"<circular_ref: {type(obj).__name__}>"

    # Track visited objects and process
    visited.add(obj_id)
    try:
        # ... sanitization logic ...
    finally:
        visited.discard(obj_id)  # Allow same object in different branches
```

**Impact:** This fix prevents stack overflow when TestClient sends mock objects with self-referencing attributes through WebSocket event serialization.

### 6.4 File Size Discipline Learnings

**The Challenge:** After implementing the cancellation feature, core files exceeded the 200-250 line target:
- `core/streaming/manager.py`: 301 lines
- `features/chat/websocket.py`: 347 lines

**The Danger:** Oversized files become hard to navigate, test, and refactor. They violate the modular design principle.

**Solution Pattern:** Extract coherent responsibilities into separate modules:

**Example 1: TTS Queue Management**
```
Before: manager.py (301 lines)
├─ Streaming logic
├─ Queue coordination
├─ TTS queue handling (scattered across methods)
└─ Result collection

After: manager.py (253 lines) + tts_queue_manager.py (98 lines)
├─ manager.py: Pure streaming, queue delegation
└─ tts_queue_manager.py: All TTS concerns (register, deregister, send chunks)
```

**Example 2: WebSocket Runtime Helpers**
```
Before: websocket.py (347 lines)
├─ Main endpoint logic
├─ Message receive loop
├─ Audio frame routing
├─ Runtime cleanup
└─ Audio detection helpers

After: websocket.py (274 lines) + websocket_runtime_helpers.py (92 lines)
├─ websocket.py: Core endpoint and message loop
└─ websocket_runtime_helpers.py: cleanup_runtime(), route_audio_frame_if_needed(), is_audio_stream_frame()
```

**Refactoring Checklist:**
1. ✅ Identify cohesive responsibilities that can be extracted
2. ✅ Create new module with clear, focused purpose
3. ✅ Move functions without changing logic (copy → paste → verify)
4. ✅ Update imports in original file
5. ✅ Run syntax checks: `python3 -m py_compile`
6. ✅ Check backend logs for import errors
7. ✅ Verify no functionality changed (same public API)

### 6.5 Pytest Configuration Issues

**The Problem:** Declaring `pytest_plugins` at non-top-level conftest causes plugin double-registration:

```
ValueError: Plugin already registered under a different name
```

**The Fix:** Pytest autodiscovers conftest files automatically. Declaring `pytest_plugins` in non-root conftest files causes the same module to be registered twice:

```python
# tests/conftest.py (TOP-LEVEL - OK)
pytest_plugins = ("anyio", "pytest_asyncio")  ✅ Explicit opt-in

# tests/live_api/conftest.py (NON-TOP-LEVEL - BREAKS)
pytest_plugins = ("tests.integration.conftest",)  ❌ Causes double registration
# → Integration conftest already loaded via autodiscovery!

# Solution: Remove non-top-level pytest_plugins, rely on autodiscovery
```

**Rule of Thumb:** Only use `pytest_plugins` in the root `tests/conftest.py` for explicit plugin opt-in.

### 6.6 Test Replacement Pattern

**When TestClient WebSocket tests break, follow this pattern:**

1. **Identify the broken tests:**
   ```bash
   pytest -m "not requires_docker" 2>&1 | grep "TIMEOUT\|HANG"
   ```

2. **Mark them as skipped with clear reason:**
   ```python
   @pytest.mark.skip(
       reason="TestClient WebSocket hangs with concurrent task processing. "
       "See tests/live_api/test_websocket_comprehensive.py::test_replacement_name"
   )
   def test_original_flow():
       pass
   ```

3. **Create corresponding live API test:**
   ```python
   @pytest.mark.live_api
   @pytest.mark.requires_docker
   @pytest.mark.skipif(not os.getenv("RUN_MANUAL_TESTS"), reason="...")
   class TestWebSocketScenario:
       @pytest.mark.asyncio
       async def test_scenario(self, auth_token_factory):
           # Real websockets implementation
   ```

4. **Document in README:**
   - Why TestClient fails
   - How to run the real test
   - What it validates
   - Expected output

### 6.7 Migration Checklist for Future WebSocket Tests

Use this checklist when adding new WebSocket functionality:

- [ ] **Does it use concurrent task processing?** (asyncio.create_task + asyncio.wait)
  - YES → Use real websockets, mark with `@pytest.mark.live_api`
  - NO → Can use TestClient, but prefer real websockets for consistency

- [ ] **Complete request payload?** Include all userSettings sections matching frontend

- [ ] **Correct event detection?** Check backend event format, not just event type

- [ ] **Reasonable timeout?** 30-60 seconds for real API calls, not 2-3 seconds

- [ ] **Proper cleanup?** Ensure WebSocket closes and resources release

- [ ] **Environment gating?** Use `RUN_MANUAL_TESTS=1` flag

- [ ] **Documentation?** Add README explaining test, requirements, expected output

## 6. Test suite statistics and baseline

The backend test suite contains **228 test files** organized across **65 directories** with **597 total test items** collected by pytest.

**Historical baseline** (Jan 2025 refresh): **557 passed, 40 skipped** in 122.51 seconds (~2 minutes).

**Test File Distribution:**
- **Unit tests**: 108 files (47%) - Core, features, infrastructure
- **Integration tests**: 36 files (16%) - Chat, audio, realtime, tools, TTS, domain features
- **Feature tests**: 14 files (6%) - Chat, audio, image, video, TTS workflows
- **Manual tests**: 15 files (7%) - Interactive validation + 1 .sh script + 1 .md checklist
- **API tests**: 5 files (2%) - Route handlers
- **E2E tests**: 1 file (<1%) - Complete user journeys
- **Load tests**: 1 file (<1%) - Concurrent streaming
- **Performance tests**: 1 file (<1%) - Agentic performance
- **Regression tests**: 1 file (<1%) - Chat history envelope parity

**Test Item Distribution (from baseline run):**
- Unit tests: 382 items (largest category)
- Integration tests: 92 items (chat, realtime, TTS, file attachments, legacy compat)
- Feature tests: 48 items
- API tests: 16 items
- Manual tests: 12 items (6 skipped based on environment flags)
- Regression tests: 9 items
- Scripts tests: 4 items (2 skipped - semantic search milestone verification)
- Load tests: 1 item

**Execution Speed:**
- Fast unit/feature tests: ~1-2 minutes (no Docker required)
- With Docker integration tests: Additional time for container startup
- Manual/live API tests: Variable based on provider response times

### 6.1 Expected skips

| Test module(s) | Skip reason | Action |
| --- | --- | --- |
| `tests/integration/blood/test_repositories.py` | Marked `requires_docker`; waits for a host-driven MySQL container. 【F:docker/storage-backend/tests/integration/blood/test_repositories.py†L1-L40】【F:docker/storage-backend/test.results.txt†L86-L87】 | Run from the host with Docker available, or accept the skip inside the dev container. |
| `tests/integration/features/audio/test_openai_streaming_integration.py` (`test_transcribe_*`, `test_streaming_events_are_emitted`) | Skip if `OPENAI_API_KEY` is missing to avoid hitting live OpenAI streaming APIs without credentials. 【F:docker/storage-backend/tests/integration/features/audio/test_openai_streaming_integration.py†L1-L126】【F:docker/storage-backend/test.results.txt†L124-L126】 | Export `OPENAI_API_KEY` before re-running for a live verification. |
| `tests/integration/features/garmin/test_garmin_routes.py` | Requires Docker and a production configuration where Garmin routes are enabled. 【F:docker/storage-backend/tests/integration/features/garmin/test_garmin_routes.py†L1-L89】【F:docker/storage-backend/test.results.txt†L127-L130】 | Mirror the production `.env` and run from the host to exercise these routes. |
| `tests/integration/garmin/test_repositories.py` | Marked `requires_docker` to provision Garmin MySQL schemas. 【F:docker/storage-backend/tests/integration/garmin/test_repositories.py†L1-L45】【F:docker/storage-backend/test.results.txt†L131-L133】 | Re-run on a host with Docker when validating Garmin persistence. |
| `tests/integration/ufc/*.py` | All repository and mutation suites are guarded by `requires_docker` because they rely on the UFC Testcontainers stack. 【F:docker/storage-backend/tests/integration/ufc/test_auth_repositories.py†L1-L35】【F:docker/storage-backend/test.results.txt†L161-L171】 | Execute from the host with Docker when database migrations change. |
| `tests/manual/test_gemini_*`, `tests/manual/test_openai_streaming_basic.py`, `tests/manual/test_ufc_fighters_query.py`, `tests/manual/test_semantic_provider.py` | Manual flows gated by environment flags (`RUN_MANUAL_TESTS`, `RUN_MANUAL_TESTS`, `RUN_MANUAL_TESTS`, `RUN_SEMANTIC_MANUAL_TESTS`) to prevent accidental spend or live service access. 【F:docker/storage-backend/tests/manual/test_gemini_audio_complete.py†L1-L150】【F:docker/storage-backend/tests/manual/test_openai_streaming_basic.py†L1-L48】【F:docker/storage-backend/tests/manual/test_ufc_fighters_query.py†L1-L56】【F:docker/storage-backend/test.results.txt†L175-L183】 | Opt in only when running supervised manual checks with the required credentials and sample assets. |
| `scripts/test_m6_filtering.py` | Always skipped with reason "Manual semantic search verification script; requires seeded MySQL and Qdrant" to avoid touching live services during automated pytest runs. | Run explicitly when verifying semantic search filtering functionality against production-like data. |
| `tests/unit/core/providers/text/test_chat_history_handling.py`, `test_message_alternation.py`, `test_model_alias_parameters.py`, `test_system_prompt_placement.py` | Tagged with `live_api` and call `require_live_client`, so they skip when the corresponding provider client cannot be initialised. 【F:docker/storage-backend/tests/unit/core/providers/text/test_chat_history_handling.py†L1-L120】【F:docker/storage-backend/tests/unit/core/providers/text/test_message_alternation.py†L1-L120】【F:docker/storage-backend/tests/utils/live_providers.py†L19-L59】【F:docker/storage-backend/test.results.txt†L325-L359】 | Provide the relevant API keys (OpenAI, Anthropic, etc.) when running live verification. |

## 7. CRITICAL: Test Integrity Rules

**NEVER mask real errors to make tests pass.** Tests must fail when configuration is missing or services are broken.

**FORBIDDEN PATTERNS:**

1. **❌ Catching configuration errors and returning None:**
   ```python
   # WRONG - Don't do this!
   try:
       service = create_service()
       return service
   except ConfigurationError:
       logger.warning("Service unavailable")
       return None  # ❌ Tests will pass with broken service
   ```

2. **❌ Creating fake/null providers to bypass errors:**
   ```python
   # WRONG - Don't do this!
   class NullSemanticProvider:
       async def search(self): return []  # ❌ Fake success

   def get_provider():
       try:
           return RealProvider()
       except:
           return NullSemanticProvider()  # ❌ Masks errors
   ```

3. **❌ Catching API key errors and returning fake success:**
   ```python
   # WRONG - Don't do this!
   try:
       result = await call_api()
   except ValueError as exc:
       if "API_KEY" in str(exc):
           return {"success": True, "model": "offline"}  # ❌ Lying
   ```

4. **❌ Returning success when operation actually failed:**
   ```python
   # WRONG - Don't do this!
   try:
       await process()
       return {"success": True}
   except Exception:
       return {"success": True, "reason": "unavailable"}  # ❌ Not success!
   ```

**CORRECT PATTERNS:**

1. **✅ Skip tests when prerequisites missing:**
   ```python
   @pytest.mark.skipif(not os.getenv("API_KEY"), reason="API_KEY not set")
   def test_integration():
       # Test only runs with real API key
   ```

2. **✅ Raise configuration errors immediately:**
   ```python
   def get_service():
       if not API_KEY:
           raise ConfigurationError("API_KEY required")
       return create_service()
   ```

3. **✅ Return honest failure states:**
   ```python
   try:
       result = await call_api()
       return {"success": True, "result": result}
   except APIError as exc:
       return {"success": False, "error": str(exc)}  # ✅ Honest
   ```

**Why This Matters:**
- Tests that pass with broken services give false confidence
- Production deploys with missing configuration will fail silently
- Debugging becomes impossible when errors are masked
- Features appear to work but actually do nothing

**Enforcement:**
- Code reviews must check for error masking patterns
- Tests should FAIL or SKIP when configuration is missing
- Never create fallback implementations that hide real errors
- See `TEST-INTEGRITY-AUDIT.md` for detailed anti-patterns and remediation
