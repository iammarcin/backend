# Proactive Agent Feature (Sherlock/Bugsy)

**Tags:** `#backend` `#features` `#proactive-agent` `#sherlock` `#bugsy` `#claude-code`

## System Context

The proactive agent feature enables **Claude Code characters** (Sherlock, Bugsy) that:
- Run on the development server using Claude Code CLI
- Have distinct personalities (Sherlock: detective; Bugsy: dev assistant)
- Proactively check in and share observations/insights
- Communicate via Kotlin mobile app and React web frontend
- Persist conversations in existing `ChatSessionsNG`/`ChatMessagesNG` tables

**Characters:**
- **Sherlock** - Detective persona, heartbeats, memory system
- **Bugsy** - Development assistant, codebase access, no heartbeats

## Architecture: Unified WebSocket

**As of 2025-12-17:** WebSocket connections use the **unified endpoint** at `/chat/ws?mode=proactive`.

The old `/api/v1/proactive-agent/ws/notifications` endpoint has been removed.

### Connection Registry

Location: `core/connections/proactive_registry.py` (shared infrastructure)

Features:
- Multiple connections per user (React + Kotlin simultaneously)
- Push notifications to all user connections
- Ping/pong keepalive (30 seconds)
- Sync mechanism for missed messages

## Directory Structure

```
features/proactive_agent/
├── __init__.py           # Router export
├── routes.py             # REST endpoints only (no WebSocket)
├── service.py            # Business logic, WebSocket push via shared registry
├── dependencies.py       # FastAPI dependencies
├── audio_intercept.py    # Audio transcription routing to SQS
├── schemas/
│   ├── __init__.py       # Schema exports
│   ├── request.py        # Request DTOs
│   └── response.py       # Response DTOs
├── repositories/
│   └── proactive_agent_repository.py  # DB access
├── poller_stream/        # Poller/Heartbeat NDJSON streaming pipeline
│   ├── event_emitter.py      # EventEmitter - normal message streaming
│   ├── heartbeat_emitter.py  # HeartbeatEmitter - silent heartbeat mode
│   ├── ndjson_parser.py      # NDJSON line parser
│   ├── websocket_handler.py  # WebSocket endpoint handler
│   └── schemas.py            # Init/Complete/Error message schemas
└── CLAUDE.md             # This file

# WebSocket handling is in unified location:
core/connections/
├── __init__.py           # Module exports
└── proactive_registry.py # Connection registry

features/chat/
├── routes.py             # Unified WebSocket at /chat/ws
└── services/
    └── proactive_handler.py  # Handler for mode=proactive
```

## API Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/health` | Health check (shows active WS count) | Public |
| GET | `/session` | Get/create session | User |
| POST | `/messages` | Send message (queues to SQS) | User |
| GET | `/messages/{session_id}/poll` | Poll for responses | User |
| POST | `/notifications` | Agent sends notification | Internal |
| POST | `/thinking` | Agent sends thinking content | Internal |
| POST | `/stream` | Agent sends streaming chunks | Internal |
| PATCH | `/session/{id}/claude-session` | Update Claude session ID | Internal |

## WebSocket (Unified)

**Endpoint:** `/chat/ws?mode=proactive&user_id=X&session_id=Y&token=JWT`

**Server → Client Messages:**
- `connected` - Connection established, includes `ping_interval`
- `ping` - Keepalive (every 30s)
- `stream_start`, `text_chunk`, `thinking_chunk`, `stream_end` - Streaming
- `notification` - Complete message from agent
- `sync_complete` - Response to sync request

**Client → Server Messages:**
- `pong` - Response to ping
- `sync` - Request missed messages: `{"type": "sync", "last_seen_at": "ISO8601"}`

## Message Flow

### User → Agent (via Poller)
```
1. POST /messages with ai_character_name
2. Backend saves to DB, queues to SQS
3. Poller on dev server picks up from SQS
4. Poller invokes Claude via SDK daemon
5. Poller streams NDJSON to backend WebSocket
6. Backend parses NDJSON, pushes to frontend, saves to DB
```

### Agent → User (Heartbeat)
```
1. Cron triggers sherlock_heartbeat.sh
2. Heartbeat builds context (weather, calendar, Garmin, journal)
3. Heartbeat invokes Claude via SDK daemon (host → host)
4. Heartbeat streams NDJSON to backend WebSocket (source="heartbeat")
5. Backend HeartbeatEmitter accumulates text silently
6. On finalize: checks HEARTBEAT_OK on clean text (not thinking)
   - If OK: nothing (no DB, no push)
   - If observation: saves to DB, pushes to frontend
```

**Key: Both poller and heartbeat use same SDK daemon + WS streaming pattern.**

## Data Model

Uses existing chat tables with character metadata:

**ChatSession fields:**
- `ai_character_name` = "sherlock" or "bugsy"
- `claude_session_id` = Claude Code session for continuity

**ChatMessage fields:**
- `claudeCodeData` JSON containing:
  - `proactive_agent: true`
  - `direction: "user_to_agent" | "agent_to_user" | "heartbeat"`
  - `source: "text" | "audio_transcription" | "heartbeat"`

## Configuration

**Character definition:** `config/proactive_agent/characters.py`
```python
CLAUDE_CODE_CHARACTERS: set[str] = {"sherlock", "bugsy"}
```

**Environment variables:**
- `AWS_SQS_PROACTIVE_AGENT_QUEUE_URL` - SQS queue URL

## Related Documentation

- `DocumentationApp/sherlock-technical-handbook.md` - Complete system reference
- `DocumentationApp/sherlock-architectural-decisions.md` - **REQUIRED READING** - Non-negotiable architectural rules
- `DocumentationApp/sherlock-poller-true-dumb-pipe-architecture.md` - Streaming architecture specification
- `core/connections/proactive_registry.py` - Connection registry
- `features/chat/services/proactive_handler.py` - WebSocket handler

