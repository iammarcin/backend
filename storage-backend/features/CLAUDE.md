**Tags:** `#backend` `#features` `#fastapi` `#architecture` `#domain-modules`

# Features Directory Overview

This directory contains all domain-specific feature modules for the BetterAI storage-backend. Each feature is self-contained with its own routes, services, repositories, and schemas.

## System Context

The `features/` directory is part of the **storage-backend** - a FastAPI-based service providing AI-powered chat, audio transcription, image/video generation, and health data APIs. Features follow a layered architecture pattern and integrate with:
- `core/` - Cross-cutting infrastructure (providers, streaming, auth)
- `infrastructure/` - External integrations (AWS S3, MySQL databases)

## Feature Module Pattern

Each feature follows a consistent structure:
```
features/<domain>/
├── routes.py         # FastAPI router (HTTP/WebSocket endpoints)
├── service.py        # Business logic orchestration
├── dependencies.py   # FastAPI dependency injection
├── schemas/          # Pydantic request/response models
├── db_models.py      # SQLAlchemy ORM models (if DB-backed)
├── repositories/     # Database CRUD operations
└── utils/            # Feature-specific helpers
```

## Available Features

| Feature | Purpose | Key Capabilities |
|---------|---------|------------------|
| **chat** | Core chat engine | WebSocket streaming, deep research, history persistence |
| **realtime** | Real-time voice | OpenAI Realtime API, Gemini Live, duplex audio streaming |
| **audio** | Speech-to-text | Deepgram, OpenAI, Gemini transcription (static & streaming) |
| **tts** | Text-to-speech | OpenAI, ElevenLabs with HTTP/WebSocket streaming |
| **image** | Image generation | OpenAI DALL-E, Stability AI, Flux, Gemini Imagen, xAI Grok |
| **video** | Video generation | Gemini Veo, OpenAI Sora, KlingAI |
| **semantic_search** | Vector search | Qdrant + OpenAI embeddings, hybrid search with BM25 |
| **garmin** | Garmin API | Health data fetching, translation, validation |
| **db/blood** | Blood tests | Blood test result tracking and queries |
| **db/garmin** | Garmin storage | Health metrics persistence (sleep, activities, training) |
| **db/ufc** | UFC data | Fighter database, subscriptions, authentication |
| **storage** | File uploads | S3 attachment handling for chat |
| **admin** | Model registry | OpenAI model configuration inspection |
| **legacy_compat** | Backward compat | Legacy mobile client API translation |

## Feature Discovery

For detailed documentation on each feature, see the `CLAUDE.md` file in each subdirectory:
- `features/chat/CLAUDE.md` - Chat engine architecture
- `features/realtime/CLAUDE.md` - Real-time voice implementation
- `features/audio/CLAUDE.md` - Speech-to-text workflows
- `features/tts/CLAUDE.md` - Text-to-speech streaming
- `features/image/CLAUDE.md` - Image generation providers
- `features/video/CLAUDE.md` - Video generation workflow
- `features/semantic_search/CLAUDE.md` - Vector search system
- `features/garmin/CLAUDE.md` - Garmin API integration
- `features/db/CLAUDE.md` - Database features overview
- `features/storage/CLAUDE.md` - S3 file handling
- `features/admin/CLAUDE.md` - Admin endpoints
- `features/legacy_compat/CLAUDE.md` - Legacy API layer

## Key Integration Patterns

**Provider Factory**: Features use `core/providers/` for AI provider resolution:
```python
provider = get_text_provider(settings)  # Chat, realtime
provider = get_tts_provider(settings)   # TTS
provider = get_image_provider(settings) # Image generation
```

**Streaming Manager**: WebSocket features use `core/streaming/manager.py` for event distribution with token-based completion ownership.

**Database Sessions**: DB-backed features use `infrastructure/db/mysql.py` session factories via FastAPI dependencies.

## Adding New Features

1. Create feature directory: `features/<name>/`
2. Add `routes.py` with FastAPI router
3. Add `service.py` for business logic
4. Register router in `main.py`
5. Add `CLAUDE.md` documentation
