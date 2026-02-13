"""Pydantic schemas for poller WebSocket protocol messages."""

from pydantic import BaseModel
from typing import Any, Optional


class InitMessage(BaseModel):
    """First message sent by poller to establish session context.

    Contains all metadata needed for the backend to handle the stream.
    """

    type: str  # Must be "init"
    user_id: int
    session_id: str
    ai_character_name: str
    tts_settings: Optional[dict[str, Any]] = None
    source: str  # "text" | "audio_transcription" | "heartbeat"
    claude_session_id: Optional[str] = None


class ErrorMessage(BaseModel):
    """Error message sent by poller when Claude invocation fails.

    Backend should emit stream_error and persist error as final message.
    """

    type: str  # Must be "error"
    code: str  # rate_limit | auth_expired | context_too_long | session_not_found | unknown
    message: str


class CompleteMessage(BaseModel):
    """Completion message sent by poller when Claude finishes successfully.

    After this, poller closes the WebSocket connection.
    """

    type: str  # Must be "complete"
    exit_code: int
