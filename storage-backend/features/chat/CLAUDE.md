**Tags:** `#backend` `#chat` `#websocket` `#streaming` `#deep-research` `#history` `#llm` `#openai` `#anthropic` `#gemini`

# Chat Feature

The largest and most complex feature in BetterAI - implements a multi-modal conversation system with WebSocket streaming, deep research workflows, and persistent chat history.

## System Context

Core feature of the **storage-backend** FastAPI service. Provides the main chat functionality including text conversations, voice input processing, and TTS output.

## Architecture Overview

**Key Capabilities:**
- WebSocket and SSE streaming for real-time responses
- Multi-provider support (OpenAI, Anthropic, Google Gemini, Groq, DeepSeek, xAI)
- Deep research mode with multi-stage search and synthesis
- Full chat history persistence with semantic indexing
- User-initiated workflow cancellation via WebSocket control messages

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/ws` | WebSocket | Main chat endpoint (standard + realtime mode detection) |
| `/chat` | POST | Non-streaming chat (HTTP) |
| `/chat/stream` | POST | Server-Sent Events streaming |
| `/chat/session-name` | POST | Auto-generate session names |
| `/chat/history/*` | Various | Session/message/prompt CRUD |

## Request Types

The WebSocket endpoint supports multiple workflow types:
- `text` - Standard text chat
- `audio` - STT → text → LLM (transcription-based)
- `audio_direct` - Audio + text → Gemini multimodal
- `tts` - Generate text → TTS output
- `realtime` - Routes to realtime voice feature

## WebSocket Connection Flow

```
1. Client connects to /chat/ws?token=<jwt>
2. Server sends: {"type": "websocketReady", "version": "2.0"}
3. Client sends initial payload with requestType, prompt, settings
4. Server authenticates, creates WorkflowSession
5. Server dispatches workflow and streams events
6. Completion events close the stream
```

## Deep Research Workflow

Three-stage pipeline for complex queries:

1. **Optimization** - Refine user query with context
2. **Research** - Multi-source search and synthesis
3. **Analysis** - Final response generation with citations

## Streaming Architecture

**Token-Based Completion Ownership:**
- Dispatcher creates `completion_token` once per request
- Token passed down the call stack
- Only token holder can call `signal_completion()`
- Services/helpers never call completion directly

**Event Types:**
- `text`, `reasoning` - Content chunks
- `audio`, `transcription` - Audio-related
- `cancelled` - User cancellation acknowledgment
- `textCompleted`, `ttsCompleted`, `fullProcessComplete` - Completion signals
- `textNotRequested`, `ttsNotRequested` - Cancellation cleanup signals

## Key Directory Structure

```
chat/
├── routes.py                    # HTTP routes
├── websocket_routes.py          # WebSocket routes
├── websocket.py                 # Connection lifecycle
├── db_models.py                 # ChatSession, ChatMessage ORM
├── services/
│   ├── streaming/               # Core streaming logic
│   │   ├── core.py              # Main orchestration
│   │   ├── standard_provider.py # Standard LLM streaming
│   │   └── deep_research/       # Research workflow
│   └── history/                 # History management
│       └── service.py           # ChatHistoryService
├── repositories/                # Database operations
│   ├── chat_sessions.py
│   └── chat_messages.py
├── utils/
│   ├── websocket_dispatcher.py  # Request routing
│   ├── websocket_workflow_executor.py
│   ├── websocket_workflows/     # Per-type handlers
│   └── history_persistence_*.py # Persistence helpers
└── schemas/                     # Pydantic models
```

## History Persistence

**Standard Flow:**
```
persist_workflow_result()
├─ Build user message from request
├─ Build AI message from workflow result
├─ Create/update session
├─ Queue semantic indexing
└─ Notify frontend via dbOperationExecuted
```

**Special Flows:**
- Deep research: Special message with `is_deep_research=True` + citations
- Session fork: Clone history with subset
- TTS-only: Store timings without generation

## Database Models

**ChatSession:**
- `session_name`, `ai_character_name`
- `ai_text_gen_model`, `auto_trigger_tts`
- `claude_session_id` (used by proactive agent flows)
- `tags` (JSON array)

**ChatMessage:**
- `message`, `ai_reasoning` - Content
- `image_locations`, `file_locations` - Artifacts
- `api_text_gen_model_name`, `api_text_gen_settings` - Config
- `claude_code_data` (JSON) - Proactive agent metadata
- Timer fields for latency tracking

## Dependencies

- `core/providers/` - AI provider registry
- `core/streaming/manager.py` - StreamingManager
- `features/tts/` - Text-to-speech
- `features/audio/` - Speech-to-text
- `features/semantic_search/` - Vector indexing
