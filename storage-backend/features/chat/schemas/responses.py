"""Response schema definitions for chat REST endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from core.pydantic_schemas import ChartPayload


class MessageWriteResult(BaseModel):
    """Identifiers returned when inserting or editing chat messages."""

    model_config = ConfigDict(populate_by_name=True)

    user_message_id: int = Field(...)
    ai_message_id: Optional[int] = Field(default=None)
    session_id: str = Field(...)


class MessageUpdateResult(BaseModel):
    """Result payload for single-message update operations."""

    model_config = ConfigDict(populate_by_name=True)

    message_id: int = Field(...)

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class MessagesRemovedResult(BaseModel):
    """Result payload returned when removing messages or related resources."""

    model_config = ConfigDict(populate_by_name=True)

    removed_count: int = Field(...)
    message_ids: Optional[List[int]] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    prompt_id: Optional[int] = Field(default=None)

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(*args, **kwargs)


class ChatMessagePayload(BaseModel):
    """Serialised chat message returned to clients."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="allow")

    message_id: int = Field(...)
    session_id: str = Field(...)
    customer_id: int = Field(...)
    sender: str
    message: Optional[str] = None
    ai_reasoning: Optional[str] = Field(default=None)
    image_locations: List[str] = Field(default_factory=list)
    file_locations: List[str] = Field(default_factory=list)
    chart_data: Optional[List[Dict[str, Any]]] = Field(default=None)
    created_at: Optional[str] = Field(default=None)

class ChatSessionPayload(BaseModel):
    """Serialised chat session representation."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    session_id: str = Field(...)
    customer_id: int = Field(...)
    session_name: Optional[str] = Field(default=None)
    ai_character_name: Optional[str] = Field(default=None)
    ai_text_gen_model: Optional[str] = Field(default=None)
    auto_trigger_tts: bool = Field(default=False)
    claude_session_id: Optional[str] = Field(default=None)
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[str] = Field(default=None)
    last_update: Optional[str] = Field(default=None)
    messages: Optional[List[ChatMessagePayload]] = None
    # Group info for group chat sessions
    group_id: Optional[str] = Field(default=None)
    group_name: Optional[str] = Field(default=None)
    # Task metadata (nullable — existing sessions return null)
    task_status: Optional[str] = Field(default=None)
    task_priority: Optional[str] = Field(default=None)
    task_description: Optional[str] = Field(default=None)


class MessageWritePayload(BaseModel):
    """High-level payload combining identifiers with optional session data."""

    messages: MessageWriteResult
    session: Optional[ChatSessionPayload] = None

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        payload = super().model_dump(*args, **kwargs)
        message_data = payload.pop("messages", {})
        flattened: Dict[str, Any] = dict(message_data)
        session_data = payload.get("session")
        if session_data is not None:
            flattened["session"] = session_data
        return flattened


class SessionListResult(BaseModel):
    """Payload returned by the session listing endpoint."""

    model_config = ConfigDict(populate_by_name=True)

    sessions: List[ChatSessionPayload] = Field(default_factory=list)
    count: int = Field(default=0)


class SessionDetailResult(BaseModel):
    """Detailed session payload for get-by-id requests."""

    session: ChatSessionPayload

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        kwargs.setdefault("exclude_none", True)
        return self.session.model_dump(*args, **kwargs)


class PromptRecord(BaseModel):
    """Prompt metadata returned to clients."""

    model_config = ConfigDict(populate_by_name=True)

    prompt_id: int = Field(...)
    customer_id: int = Field(...)
    title: str
    prompt: str


class PromptListResult(BaseModel):
    """List payload for prompt endpoints."""

    prompts: List[PromptRecord] = Field(default_factory=list)


class AuthResult(BaseModel):
    """Authentication response payload."""

    model_config = ConfigDict(populate_by_name=True)

    customer_id: int = Field(...)
    username: str
    email: Optional[str] = None
    token: str


class FavoritesResult(BaseModel):
    """Payload describing the virtual favourites session."""

    session: ChatSessionPayload | None = None

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
        if not self.session:
            return {}
        kwargs.setdefault("exclude_none", True)
        return self.session.model_dump(*args, **kwargs)


class FileQueryResult(BaseModel):
    """Result payload for file query endpoints."""

    messages: List[ChatMessagePayload] = Field(default_factory=list)


__all__ = [
    "AuthResult",
    "ChatMessagePayload",
    "ChatSessionPayload",
    "FavoritesResult",
    "FileQueryResult",
    "MessageWritePayload",
    "MessageUpdateResult",
    "MessageWriteResult",
    "MessagesRemovedResult",
    "PromptListResult",
    "PromptRecord",
    "SessionDetailResult",
    "SessionListResult",
]
