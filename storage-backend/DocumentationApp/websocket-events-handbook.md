# WebSocket Events Handbook

**Last Updated:** 2026-01-12
**Scope:** Canonical WebSocket event types for all backend-to-client communication

## Overview

All WebSocket events use **snake_case** naming. The backend `WSEvent` enum (`core/websocket/event_types.py`) is the single source of truth. Clients must handle these exact names - no aliases, no fallbacks.

## Completion Model

Text and TTS are parallel processes. Clients track two flags:

```
textCompleted = false
ttsCompleted = false

on "text_completed" → textCompleted = true; checkCompletion()
on "tts_completed" → ttsCompleted = true; checkCompletion()
on "tts_not_requested" → ttsCompleted = true; checkCompletion()

checkCompletion() → if (textCompleted && ttsCompleted) onStreamingComplete()
```

**Removed events:** `fullProcessComplete`, `complete`, `streamingComplete` - clients use dual flags instead.

## Event Reference

### Connection
| Event | Purpose |
|-------|---------|
| `websocket_ready` | Backend ready for payload |
| `connected` | Proactive connection established |
| `closing` | Connection closing (timeout) |
| `ping` / `pong` | Keepalive |
| `working` | Request acknowledged |

### Text Streaming
| Event | Purpose |
|-------|---------|
| `stream_start` | AI response starting |
| `text_chunk` | Text content chunk |
| `thinking_chunk` | Reasoning/thinking chunk |
| `text_completed` | Text generation done |
| `text_not_requested` | TTS-only mode (no text generation) |

### TTS / Audio
| Event | Purpose |
|-------|---------|
| `tts_started` | TTS generation started |
| `audio_chunk` | Audio data chunk (base64) |
| `tts_generation_completed` | All audio chunks sent |
| `tts_completed` | TTS fully complete |
| `tts_not_requested` | TTS not enabled |
| `tts_file_uploaded` | S3 URL available |
| `tts_error` | TTS failed (followed by `tts_completed`) |

### Tools
| Event | Purpose |
|-------|---------|
| `tool_start` | Tool execution started |
| `tool_result` | Tool execution completed |

### Errors
| Event | Purpose |
|-------|---------|
| `stream_error` | Streaming error (rate_limit, context_too_long) |
| `error` | Generic error with `stage` field |

### Database
| Event | Purpose |
|-------|---------|
| `db_operation_executed` | DB persistence done |

### Transcription
| Event | Purpose |
|-------|---------|
| `transcription` | STT result |
| `transcription_in_progress` | STT interim |
| `transcription_complete` | STT done (includes `recording_id` for ACK correlation) |
| `translation` | Translation result |
| `recording_stopped` | Recording ACK |

**`transcription_complete` payload:**
```json
{
  "type": "transcription_complete",
  "content": "transcribed text here",
  "recording_id": "uuid-from-client"  // Optional: echoed from user_input for queue cleanup
}
```

### Proactive/Sync
| Event | Purpose |
|-------|---------|
| `sync_complete` | Offline sync done |
| `sync_error` | Sync failed |
| `notification` | Proactive notification |
| `message_sent` | Message send ACK |
| `send_error` | Message send failed |

### Voice/Realtime
| Event | Purpose |
|-------|---------|
| `turn.user_speaking` | User speaking in voice mode |
| `turn.ai_thinking` | AI processing |
| `turn.ai_responding` | AI responding |
| `turn.completed` | Turn done |
| `turn.persisted` | Turn saved |
| `session.closed` | Voice session ended |
| `control` | Voice control wrapper |

### Routing
| Event | Purpose |
|-------|---------|
| `claude_code_queued` | Routed to Claude Code |
| `cancelled` | Request cancelled |

### Custom Events
| Event | Purpose |
|-------|---------|
| `custom_event` | Wrapper for extensible events |

**Custom event structure:**
```json
{
  "type": "custom_event",
  "event_type": "reasoning",
  "content": { ... }
}
```

**Known event_type values:** `reasoning`, `claudeSession`, `claudeToolUse`, `claudeCodeFinalResult`, `chart`, `chartGenerationStarted`, `image`, `citations`, `deepResearchStarted`, `deepResearchCompleted`, `toolUse`, `aiTextModelInUse`, `semanticContextAdded`, `clarificationQuestions`, `textGenerationCompleted`, `iterationStarted`, `iterationCompleted`

## TTS Event Sequence

**With TTS enabled:**
```
stream_start → tts_started → text_chunk* → audio_chunk* → text_completed → tts_generation_completed → tts_completed
```

**Without TTS:**
```
stream_start → text_chunk* → text_completed → tts_not_requested
```

**TTS-only mode:**
```
text_not_requested → tts_started → audio_chunk* → tts_generation_completed → tts_completed
```

**On TTS error:**
```
tts_started → tts_error → tts_completed (always sent to prevent client hang)
```

## Key Implementation Files

- **Event enum:** `core/websocket/event_types.py`
- **TTS queue check:** `core/streaming/tts_queue_manager.py` (checks for `text_chunk`)
- **Standard executor:** `features/chat/utils/standard_executor.py`
- **TTS streaming:** `features/tts/service_streaming.py`, `features/tts/service_stream_queue.py`
- **Proactive handlers:** `features/proactive_agent/utils/lifecycle_handlers.py`, `content_handlers.py`

## References

- Implementation plan: `DocumentationApp/websocket-unification-plan.md`
- Proactive agent: `DocumentationApp/sherlock-technical-handbook.md`
