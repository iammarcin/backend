"""Response schemas for proactive agent endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Single message response."""

    message_id: int = Field(..., description="Database message ID")
    session_id: str = Field(..., description="Session ID")
    direction: str = Field(..., description="Message direction")
    content: str = Field(..., description="Message content")
    source: Optional[str] = Field(None, description="Message source")
    is_heartbeat_ok: bool = Field(default=False, description="Was this a suppressed heartbeat")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")


class MessageListResponse(BaseModel):
    """Response containing list of messages."""

    messages: list[MessageResponse] = Field(default_factory=list, description="List of messages")
    session_id: str = Field(..., description="Session ID")
    has_more: bool = Field(default=False, description="More messages available")
    total: int = Field(default=0, description="Total message count")


class SessionResponse(BaseModel):
    """Session details response."""

    session_id: str = Field(..., description="Session ID")
    user_id: int = Field(..., description="User ID")
    claude_session_id: Optional[str] = Field(None, description="Claude Code session ID")
    ai_character_name: str = Field(..., description="Character name")
    is_active: bool = Field(default=True, description="Session active status")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    message_count: int = Field(default=0, description="Number of messages in session")


class SendMessageResponse(BaseModel):
    """Response after sending a message."""

    queue_message_id: Optional[str] = Field(None, description="Queue message ID")
    session_id: str = Field(..., description="Session ID")
    queued: bool = Field(default=False, description="Message was queued to SQS")
    message_id: Optional[int] = Field(None, description="Database message ID")


__all__ = ["MessageResponse", "MessageListResponse", "SessionResponse", "SendMessageResponse"]
