# BetterAI Backend

Production-grade FastAPI backend powering the BetterAI platform — a multi-provider AI system that unifies text generation, image/video creation, voice chat, speech-to-text, text-to-speech, semantic search, health data aggregation, and agentic workflows behind a single async API.

Built as a personal project to explore and integrate the full spectrum of modern AI APIs into a cohesive, well-architected backend.

## What This Project Demonstrates

- **Multi-provider AI orchestration** — 40+ models across 8 providers (OpenAI, Anthropic, Google Gemini, xAI, Groq, Perplexity, DeepSeek, ElevenLabs) with a pluggable registry pattern that makes adding new providers a configuration exercise, not a rewrite
- **Real-time streaming architecture** — WebSocket and SSE streaming with token-based completion ownership to prevent race conditions in concurrent streams
- **Clean layered architecture** — strict separation into `core/` (infrastructure), `features/` (business logic), `infrastructure/` (external integrations), and `config/` (centralized configuration)
- **Async-first design** — everything from database queries (SQLAlchemy async) to AWS operations (aioboto3) to AI provider calls runs on async/await
- **Comprehensive testing** — 299 test files covering unit, integration, API, live provider, performance, and regression scenarios
- **18 self-contained feature modules**, each following the same routes → services → repositories pattern

## Tech Stack

| Layer | Technologies |
|---|---|
| **Framework** | FastAPI, Uvicorn, Pydantic v2 |
| **Language** | Python 3.10+ |
| **Databases** | Postgres (Supabase), SQLAlchemy (async ORM), Qdrant (vector DB) |
| **AI Providers** | OpenAI, Anthropic, Google Gemini, xAI, Groq, Perplexity, DeepSeek, Deepgram, ElevenLabs, Stability AI, Flux, KlingAI |
| **Cloud** | AWS (S3, SQS) |
| **Auth** | JWT (python-jose) |
| **Streaming** | WebSockets, Server-Sent Events |
| **Testing** | pytest, pytest-asyncio, testcontainers |

## Features

### AI Generation
- **Chat** — multi-provider text conversation with WebSocket/SSE streaming and session management
- **Image Generation** — OpenAI (GPT Image, DALL-E), Stability AI, Flux, Gemini, xAI Grok
- **Video Generation** — Gemini Veo, OpenAI Sora, KlingAI (text-to-video, image-to-video, video extension, native audio, lip-sync)
- **Realtime Voice** — bidirectional audio streaming via OpenAI Realtime API and Gemini Live
- **Text-to-Speech** — OpenAI and ElevenLabs with real-time WebSocket streaming (audio synthesis starts before text generation completes)
- **Speech-to-Text** — Deepgram, OpenAI Whisper, Gemini (static file and streaming transcription)
- **Batch Processing** — async batch API for OpenAI, Anthropic, and Gemini with 50% cost reduction

### Agentic & Search
- **Agentic Workflows** — multi-iteration tool loops for browser automation, chart generation, and image/video creation
- **Semantic Search** — vector search with Qdrant + OpenAI embeddings, hybrid/keyword/semantic modes, tag and date filtering
- **Proactive Agent** — multi-character AI frameworks - one using Openclaw/Claude Agent SDK as brain, another one Claude Agent SDK with SQS-driven push notifications

### Data & Integrations
- **Garmin Health** — sleep, activity, body composition, HRV, and training readiness data aggregation
- **Blood Tracking** — blood test result storage and analysis
- **S3 Storage** — file upload with signed URLs

## Architecture

```
storage-backend/
├── main.py                    # FastAPI app factory & entry point
├── core/                      # Cross-cutting infrastructure
│   ├── providers/             # Pluggable AI provider registry
│   │   ├── text/              #   8 providers, 40+ models
│   │   ├── image/             #   5 providers (OpenAI, Stability, Flux, Gemini, xAI)
│   │   ├── video/             #   3 providers (Gemini, OpenAI, KlingAI)
│   │   ├── audio/             #   3 providers (Deepgram, OpenAI, Gemini)
│   │   ├── realtime/          #   2 providers (OpenAI, Gemini)
│   │   ├── tts/               #   2 providers (OpenAI, ElevenLabs)
│   │   ├── semantic/          #   Vector embeddings & search
│   │   ├── batch/             #   Batch processing (OpenAI, Anthropic, Gemini)
│   │   └── registry/          #   Model registry & resolution
│   ├── streaming/             # Token-based completion ownership
│   ├── auth/                  # JWT authentication
│   ├── clients/               # AI SDK client initialization
│   └── observability/         # Metrics, tracing, request logging
│
├── features/                  # Domain-specific business logic
│   ├── chat/                  #   Sessions, messages, WebSocket/SSE
│   ├── realtime/              #   Voice chat (OpenAI Realtime, Gemini Live)
│   ├── audio/                 #   Speech-to-text endpoints
│   ├── image/                 #   Image generation
│   ├── video/                 #   Video generation & extension
│   ├── tts/                   #   Text-to-speech with WebSocket streaming
│   ├── semantic_search/       #   Vector search (Qdrant + embeddings)
│   ├── batch/                 #   Batch job submission & results
│   ├── proactive_agent/       #   Multi-character AI framework
│   ├── garmin/                #   Garmin health data integration
│   ├── db/                    #   Blood, Garmin, UFC data features
│   ├── storage/               #   S3 file upload
│   ├── automation/            #   Workflow scheduling
│   └── journal/               #   Journal entries
│
├── infrastructure/            # External integrations
│   ├── db/                    #   MySQL session factories & migrations
│   └── aws/                   #   S3 & SQS clients
│
├── config/                    # Centralized configuration by domain
│   ├── text/                  #   LLM provider configs
│   ├── audio/, tts/, image/   #   Feature-specific settings
│   ├── database/              #   DB connection config
│   └── aws/                   #   AWS credentials & endpoints
│
├── tests/                     # 299 test files
│   ├── unit/                  #   Core & infrastructure unit tests
│   ├── integration/           #   Multi-service integration tests
│   ├── api/                   #   Endpoint tests (httpx AsyncClient)
│   ├── features/              #   Feature-specific tests
│   ├── live_api/              #   Real provider API tests
│   ├── performance/           #   Performance benchmarks
│   └── regression/            #   Regression validation
│
└── DocumentationApp/          # 18 comprehensive handbooks
```

### Key Design Patterns

**Provider Registry** — AI providers are registered at import time and resolved dynamically via factory functions. Adding a new provider means defining model configs, implementing a provider class, and registering it — no changes to existing code.

```python
# Registration
register_text_provider("openai", OpenAITextProvider)

# Resolution — factory picks the right provider based on model name
provider = get_text_provider(settings)
```

**Token-Based Completion Ownership** — the `StreamingManager` prevents race conditions in concurrent WebSocket/TTS streams. Only the code holding the completion token can signal stream completion, enforced at runtime.

**Feature Module Pattern** — each feature is self-contained with a consistent internal structure:

```
features/<domain>/
├── routes.py          # FastAPI router (HTTP/WebSocket)
├── services/          # Business logic
├── repositories/      # Database operations
├── schemas/           # Pydantic request/response models
└── utils/             # Feature-specific helpers
```

## Supported Models (Highlights)

| Category | Providers | Example Models |
|---|---|---|
| **Text** | OpenAI, Anthropic, Google, xAI, Groq, Perplexity, DeepSeek | GPT-5, Claude Opus 4, Gemini 2.5 Pro, Grok 4, Sonar Deep Research |
| **Image** | OpenAI, Flux, Stability, Gemini, xAI | GPT Image 1.5, Flux 2 Pro, Stable Diffusion 3.5, Gemini Image |
| **Video** | Gemini, OpenAI, KlingAI | Veo 3.1, Sora 2, Kling V2.6 Pro |
| **Voice** | OpenAI, Google | GPT Realtime, Gemini Live |
| **STT** | Deepgram, OpenAI, Google | Nova-3, Whisper, Gemini 2.5 |
| **TTS** | OpenAI, ElevenLabs | GPT-4o TTS, 25+ custom voices |

## Database Architecture

Four isolated MySQL databases, each served by async SQLAlchemy sessions:

| Database | Purpose |
|---|---|
| **Main** | Chat sessions, messages, user data |
| **Garmin** | Health metrics (sleep, activity, body composition, HRV, training status) |
| **Blood** | Blood test results and analysis |
| **UFC** | Fighter data and subscriptions |

## Getting Started

### Prerequisites
- Python 3.10+
- MySQL
- AWS account (S3, SQS)
- API keys for desired AI providers

### Setup

```bash
cd storage-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure your API keys and database URLs
```

### Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Test

```bash
# Unit and integration tests
pytest

# Specific test categories
pytest -m "not live_api and not requires_docker"
```

## API Overview

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/chat/ws` | WS | Main chat WebSocket (standard + realtime modes) |
| `/chat/stream` | POST | SSE streaming chat |
| `/api/v1/audio/transcribe` | POST | Static file transcription |
| `/api/v1/audio/transcribe-stream` | WS | Streaming transcription |
| `/image/generate` | POST | Image generation |
| `/video/generate` | POST | Video generation |
| `/api/v1/tts/generate` | POST | Sync text-to-speech |
| `/tts/stream` | WS | Streaming text-to-speech |
| `/api/v1/batch/` | POST | Submit batch job |
| `/api/v1/semantic/health` | GET | Semantic search status |
| `/api/v1/garmin/analysis/overview` | GET | Aggregated health data |
| `/api/v1/storage/upload` | POST | S3 file upload |

## Documentation

The [`DocumentationApp/`](storage-backend/DocumentationApp) directory contains 18 detailed handbooks covering architecture, features, database design, testing strategy, WebSocket event contracts, and troubleshooting.

### Architecture & Development
- [**Developer Handbook**](storage-backend/DocumentationApp/storage-backend-ng-developer-handbook.md) — ground truth for architecture, layered structure, and development patterns
- [**Backend Capabilities Reference**](storage-backend/DocumentationApp/backend-capabilities-handbook.md) — comprehensive feature and model catalog
- [**AI Reference (Minimal)**](storage-backend/DocumentationApp/backend-capabilities-minial-ai-reference.md) — token-efficient summary of all features and models
- [**Code Review Instructions**](storage-backend/DocumentationApp/CODE-REVIEW-INSTRUCTIONS.md) — FastAPI-specific review checklist
- [**Troubleshooting Guidelines**](storage-backend/DocumentationApp/TROUBLESHOOTING-GUIDELINES.md) — systematic 6-step debugging framework

### Feature Deep Dives
- [**WebSocket Events Handbook**](storage-backend/DocumentationApp/websocket-events-handbook.md) — complete WebSocket event catalog and frontend contract
- [**WebSocket TTS Streaming**](storage-backend/DocumentationApp/websocket-tts-streaming-handbook.md) — real-time TTS streaming architecture (parallel text + audio)
- [**Semantic Search Handbook**](storage-backend/DocumentationApp/semantic-search-handbook.md) — vector search architecture, Qdrant integration, and configuration
- [**Semantic Search Settings Guide**](storage-backend/DocumentationApp/semantic-search-settings-guide.md) — search mode and filter configuration reference
- [**Image & Video Generation**](storage-backend/DocumentationApp/image-video-generation-system.md) — multi-provider image/video generation systems
- [**Batch API Handbook**](storage-backend/DocumentationApp/batch-api-handbook.md) — batch processing guide (OpenAI, Anthropic, Gemini)
- [**Garmin Integration**](storage-backend/DocumentationApp/garmin-backend-overview.md) — health data aggregation and Garmin API integration
- [**Deep Research Handbook**](storage-backend/DocumentationApp/deep-research-handbook.md) — deep research workflows
- [**Text Providers Config**](storage-backend/DocumentationApp/text-providers-config-handbook.md) — LLM provider configuration details

### Database & Testing
- [**Database Handbook**](storage-backend/DocumentationApp/storage-backend-ng-database-handbook.md) — database design, ORM setup, and migration strategy
- [**Testing Guide**](storage-backend/DocumentationApp/testing-guide-handbook.md) — test strategy, markers, conventions, and E2E scripts
- [**Manual & Live Test Readiness**](storage-backend/DocumentationApp/manual-and-live-provider-test-readiness.md) — provider test readiness checks
