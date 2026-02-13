"""Canonical WebSocket event types - SINGLE SOURCE OF TRUTH.

Rules:
1. snake_case only (no camelCase)
2. One name per concept (no aliases)
3. All platforms must handle these EXACT names
4. Unknown events MUST be logged, never silently dropped
"""

from enum import StrEnum


class WSEvent(StrEnum):
    """All WebSocket event types."""

    # ═══════════════════════════════════════════════════════════════════
    # CONNECTION LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════

    WEBSOCKET_READY = "websocket_ready"  # Backend ready for payload
    CONNECTED = "connected"  # Proactive connection established
    CLOSING = "closing"  # Connection closing (timeout, shutdown)
    PING = "ping"  # Server keepalive
    PONG = "pong"  # Client keepalive response
    WORKING = "working"  # Request acknowledged

    # ═══════════════════════════════════════════════════════════════════
    # TEXT STREAMING
    # ═══════════════════════════════════════════════════════════════════

    STREAM_START = "stream_start"  # AI response starting
    TEXT_CHUNK = "text_chunk"  # Text content chunk
    THINKING_CHUNK = "thinking_chunk"  # Reasoning/thinking chunk
    TEXT_COMPLETED = "text_completed"  # Text generation done
    STREAM_END = "stream_end"  # Proactive: AI response stream ended
    TEXT_NOT_REQUESTED = "text_not_requested"  # TTS-only mode - no text generation

    # ═══════════════════════════════════════════════════════════════════
    # TTS / AUDIO (Parallel Process)
    # Sequence: tts_started → audio_chunk* → tts_generation_completed → tts_completed
    # ═══════════════════════════════════════════════════════════════════

    TTS_STARTED = "tts_started"  # TTS generation started
    AUDIO_CHUNK = "audio_chunk"  # Audio data chunk
    TTS_GENERATION_COMPLETED = "tts_generation_completed"  # All audio chunks sent
    TTS_COMPLETED = "tts_completed"  # TTS fully complete
    TTS_NOT_REQUESTED = "tts_not_requested"  # TTS was not enabled
    TTS_FILE_UPLOADED = "tts_file_uploaded"  # S3 URL available
    TTS_ERROR = "tts_error"  # TTS failed

    # ═══════════════════════════════════════════════════════════════════
    # ERROR EVENTS
    # ═══════════════════════════════════════════════════════════════════

    STREAM_ERROR = "stream_error"  # Streaming error (rate_limit, context_too_long, etc.)
    ERROR = "error"  # Generic error

    # ═══════════════════════════════════════════════════════════════════
    # TOOL EXECUTION
    # ═══════════════════════════════════════════════════════════════════

    TOOL_START = "tool_start"  # Tool execution started
    TOOL_RESULT = "tool_result"  # Tool execution completed

    # ═══════════════════════════════════════════════════════════════════
    # DATABASE / PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════

    DB_OPERATION_EXECUTED = "db_operation_executed"  # DB op done
    MESSAGE_SENT = "message_sent"  # Proactive: message send ACK
    SEND_ERROR = "send_error"  # Proactive: message send failed

    # ═══════════════════════════════════════════════════════════════════
    # TRANSCRIPTION (STT)
    # ═══════════════════════════════════════════════════════════════════

    TRANSCRIPTION = "transcription"  # Speech-to-text result
    TRANSCRIPTION_IN_PROGRESS = "transcription_in_progress"
    TRANSCRIPTION_COMPLETE = "transcription_complete"
    TRANSLATION = "translation"  # Translation result
    RECORDING_STOPPED = "recording_stopped"  # Recording stopped ACK

    # ═══════════════════════════════════════════════════════════════════
    # SYNC (PROACTIVE)
    # ═══════════════════════════════════════════════════════════════════

    SYNC_COMPLETE = "sync_complete"  # Offline sync completed
    SYNC_ERROR = "sync_error"  # Sync failed
    NOTIFICATION = "notification"  # Proactive notification

    # ═══════════════════════════════════════════════════════════════════
    # CUSTOM / EXTENSIBLE
    # ═══════════════════════════════════════════════════════════════════

    CUSTOM_EVENT = "custom_event"  # Custom event wrapper

    # ═══════════════════════════════════════════════════════════════════
    # REALTIME CONVERSATION (Voice Mode)
    # ═══════════════════════════════════════════════════════════════════

    TURN_USER_SPEAKING = "turn.user_speaking"
    TURN_AI_THINKING = "turn.ai_thinking"
    TURN_AI_RESPONDING = "turn.ai_responding"
    TURN_COMPLETED = "turn.completed"
    TURN_PERSISTED = "turn.persisted"
    SESSION_CLOSED = "session.closed"
    CONTROL = "control"

    # ═══════════════════════════════════════════════════════════════════
    # ROUTING
    # ═══════════════════════════════════════════════════════════════════

    CLAUDE_CODE_QUEUED = "claude_code_queued"  # Routed to Claude Code
    CANCELLED = "cancelled"  # Request cancelled


# ═══════════════════════════════════════════════════════════════════════
# REMOVED EVENTS - No longer sent
# ═══════════════════════════════════════════════════════════════════════

REMOVED_EVENTS = {
    "fullProcessComplete",  # REMOVED: Client uses text_completed + tts_completed flags
    "complete",  # REMOVED: Duplicate of text_completed
    "streamingComplete",  # REMOVED: Duplicate of text_completed
}


__all__ = ["WSEvent", "REMOVED_EVENTS"]
