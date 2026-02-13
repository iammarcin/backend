"""Request models for chat session retrieval and updates."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field

from .base import BaseChatRequest


class SessionListRequest(BaseChatRequest):
    """List chat sessions with optional filters and pagination."""

    start_date: Optional[datetime] = Field(default=None)
    end_date: Optional[datetime] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    ai_character_name: Optional[str] = Field(default=None)
    task_status: Optional[Literal["active", "waiting", "done", "any", "none"]] = Field(default=None)
    task_priority: Optional[Literal["high", "medium", "low"]] = Field(default=None)
    offset: int = Field(0, ge=0)
    limit: int = Field(30, ge=0)
    include_messages: bool = Field(default=False)


class SessionDetailRequest(BaseChatRequest):
    """Retrieve a single chat session and optionally its messages."""

    session_id: Optional[str] = Field(default=None)
    ai_character_name: Optional[str] = Field(default=None)
    include_messages: bool = Field(default=True)


class SessionSearchRequest(BaseChatRequest):
    """Search sessions using fuzzy text matching."""

    search_text: Optional[str] = Field(default=None)
    limit: int = Field(30, ge=1)


class UpdateSessionRequest(BaseChatRequest):
    """Update metadata associated with a chat session."""

    session_id: str = Field(...)
    session_name: Optional[str] = Field(default=None)
    ai_character_name: Optional[str] = Field(default=None)
    auto_trigger_tts: Optional[bool] = Field(default=None)
    ai_text_gen_model: Optional[str] = Field(default=None)
    tags: Optional[list[str]] = None
    claude_session_id: Optional[str] = Field(default=None)
    update_last_mod_time: bool = Field(default=True)
    last_update_override: Optional[datetime] = Field(default=None)
    task_status: Optional[Literal["active", "waiting", "done"]] = Field(default=None)
    task_priority: Optional[Literal["high", "medium", "low"]] = Field(default=None)
    task_description: Optional[str] = Field(default=None, max_length=500)
    clear_task_metadata: bool = Field(
        default=False,
        description="When True, clears all task fields (status, priority, description) to None.",
    )


class CreateTaskRequest(BaseChatRequest):
    """Create a new session promoted to a task with metadata."""

    ai_character_name: str = Field(...)
    task_description: str = Field(..., max_length=500)
    task_priority: Literal["high", "medium", "low"] = Field(default="medium")
    session_name: Optional[str] = Field(default=None)


class RemoveSessionRequest(BaseChatRequest):
    """Remove a chat session and its associated messages."""

    session_id: str = Field(...)


__all__ = [
    "CreateTaskRequest",
    "RemoveSessionRequest",
    "SessionDetailRequest",
    "SessionListRequest",
    "SessionSearchRequest",
    "UpdateSessionRequest",
]
