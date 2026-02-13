# Core Infrastructure Layer

**Tags:** `#backend` `#core` `#infrastructure` `#cross-cutting` `#providers` `#streaming` `#authentication` `#logging` `#exceptions` `#configuration` `#ai-clients` `#observability` `#pydantic` `#fastapi`

## System Context

This `core/` directory is part of the **storage-backend** FastAPI service - the AI-powered backend for the BetterAI platform. The core layer provides **cross-cutting infrastructure** that all feature modules depend on.

**Architecture position:** `config/` → **`core/`** → `features/` → `infrastructure/`

The core layer is **not feature-specific** - it provides foundational services (authentication, streaming, provider registry, logging) consumed by all domain features (chat, image, video, TTS, etc.).

## Purpose

Cross-cutting infrastructure providing:
- **Provider Registry** - Multi-provider AI integration (text, image, video, audio, TTS, realtime, semantic)
- **Streaming Orchestration** - WebSocket/SSE event fan-out with token-based completion ownership
- **Authentication** - JWT validation and context extraction
- **Configuration** - Environment-based settings management
- **Logging** - Centralized structured logging with noise filters
- **Exception Hierarchy** - Typed exceptions with context metadata
- **API Schemas** - Pydantic models for requests/responses

## Directory Structure

```
core/
├── config.py             # Environment configuration & Settings dataclass
├── exceptions.py         # Typed exception hierarchy (ProviderError, ValidationError, etc.)
├── logging.py            # Centralized logging with custom filters
├── api/                  # API response helpers (re-exports)
├── auth/                 # JWT authentication (jwt.py)
├── clients/              # External service clients
│   ├── ai.py             # Global AI SDK initialization (OpenAI, Anthropic, Gemini, etc.)
│   └── ...
├── http/                 # HTTP error formatting
├── models/               # Deprecated (→ pydantic_schemas, registry)
├── observability/        # Metrics collection & request logging
├── pydantic_schemas/     # FastAPI request/response models & API envelope
├── providers/            # AI provider registry & implementations (see providers/CLAUDE.md)
├── streaming/            # StreamingManager with token-based completion
└── utils/                # Environment helpers, config builders
```

## Key Components

### `config.py` - Environment Configuration
Centralized environment variable loading with `Settings` dataclass:
- API keys (OpenAI, Anthropic, Google, AWS, ElevenLabs, etc.)
- Database URLs (main, Garmin, blood, UFC)
- Semantic search configuration
- Environment detection (production/sherlock/local)

### `exceptions.py` - Exception Hierarchy
Typed exceptions with context metadata for debugging:
- `ServiceError` (base)
- `ValidationError(field, message)`
- `ProviderError(provider, original_error)`
- `ConfigurationError(key)`
- `StreamingError(stage)`
- `CompletionOwnershipError` - Token violation
- `DatabaseError(operation)`
- `AuthenticationError`
- `RateLimitError(retry_after)`

### `logging.py` - Structured Logging
Custom filters reduce noise from external libraries:
- `_NoBinaryFilter` - Removes Deepgram binary noise
- `_WebsocketConnectionFilter` - Removes connection closed spam
- Suppresses PIL, httpx, boto3, sqlalchemy DEBUG
- Environment-aware (file rotation in Docker)

### `auth/jwt.py` - Authentication
JWT validation for protected endpoints:
```python
# FastAPI dependency
auth_context: AuthContext = Depends(require_auth_context)
# Returns: {customer_id, email, token, payload}
```

### `clients/ai.py` - AI Client Initialization
Global clients initialized at import time:
- `ai_clients["openai_async"]` - AsyncOpenAI
- `ai_clients["anthropic_async"]` - AsyncAnthropic
- `ai_clients["gemini"]` - Google GenAI
- `ai_clients["groq"]`, `ai_clients["perplexity"]`, etc.

Pattern: Fail-fast if API key missing; atexit cleanup handlers.

### `pydantic_schemas/` - API Models
- `ApiResponse[T]` - Generic response envelope (code, success, message, data, meta)
- `api_ok()` / `api_error()` - Response constructors
- `ChatRequest`, `ImageGenerationRequest`, `VideoGenerationRequest`
- `ProviderResponse` - Standardized provider output

### `observability/` - Metrics & Logging
- `metrics.py` - Transcription metrics and ad-hoc metric tracking
- `request_logging.py` - HTTP/WebSocket request logging middleware

## Streaming Architecture

**StreamingManager** (`streaming/manager.py`) enforces **token-based completion ownership**:

```python
# 1. Dispatcher creates token
token = manager.create_completion_token()

# 2. Services stream events (no completion power)
await manager.send_to_queues({"type": "text", "content": chunk})

# 3. Only token holder can complete
await manager.signal_completion(token=token)
```

**Benefits:** Prevents race conditions in multi-consumer streaming (WebSocket + TTS).

## Subdirectory Documentation

| Directory | Purpose | Detailed Docs |
|-----------|---------|---------------|
| `providers/` | AI provider registry & 40+ implementations | `providers/CLAUDE.md` |

## Configuration Integration

The core layer consumes configuration from `config/` directory:

| Config Module | Used By | Details |
|---------------|---------|---------|
| `config/providers/` | `core/providers/registry/` | Model capabilities and provider configurations |
| `config/defaults.py` | Multiple layers | Global temperature, token, and system prompt defaults |

## Key Design Patterns

1. **Import-Time Registration** - Providers registered when module loads
2. **Factory Pattern** - `get_text_provider(settings)` resolves by model name
3. **Token-Based Ownership** - Streaming completion control
4. **Dependency Injection** - Settings dataclass for FastAPI depends()
5. **Typed Exceptions** - Context metadata for debugging

## Integration Points

**Consumed by `features/`:**
- `features/chat/` uses `get_text_provider()`, `StreamingManager`, `AuthContext`
- `features/image/` uses `get_image_provider()`
- `features/tts/` uses `get_tts_provider()`
- All features use `api_ok()`, `api_error()`, exceptions

**Depends on `config/`:**
- `core/providers/registry/` imports `MODEL_CONFIGS` from `config/providers/`
- `core/config.py` reads environment variables

## Related Documentation

- `config/CLAUDE.md` - Model registry and provider configurations
- `providers/CLAUDE.md` - Provider registry deep-dive
- Root `CLAUDE.md` - Full backend architecture
