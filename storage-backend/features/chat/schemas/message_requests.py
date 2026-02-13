"""Request models for chat message CRUD operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import Field, model_validator

from .base import BaseChatRequest
from .message_content import MessageContent, MessagePatch


class CreateMessageRequest(BaseChatRequest):
    """Request payload for creating a new chat message pair."""

    session_id: Optional[str] = Field(default=None)
    session_name: Optional[str] = Field(default=None)
    ai_character_name: Optional[str] = Field(default=None)
    ai_text_gen_model: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    auto_trigger_tts: bool = Field(default=False)
    claude_session_id: Optional[str] = Field(default=None)
    user_message: MessageContent = Field(...)
    ai_response: Optional[MessageContent] = Field(default=None)
    update_last_mod_time: bool = Field(default=True)
    claude_code_data: Optional[Dict[str, Any]] = Field(default=None)
    include_messages: bool = Field(default=False)
    user_settings: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ensure_message_content(self) -> "CreateMessageRequest":
        """Ensure that at least one user message field contains data."""

        if not self.user_message.has_content():
            raise ValueError("user_message must contain text or attachments")
        return self


class EditMessageRequest(BaseChatRequest):
    """Request payload for editing existing chat messages."""

    session_id: Optional[str] = Field(default=None)
    session_name: Optional[str] = Field(default=None)
    ai_character_name: Optional[str] = Field(default=None)
    ai_text_gen_model: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    auto_trigger_tts: bool = Field(default=False)
    claude_session_id: Optional[str] = Field(default=None)
    user_message: Optional[MessageContent] = Field(default=None)
    ai_response: Optional[MessageContent] = Field(default=None)
    update_last_mod_time: bool = Field(default=True)
    claude_code_data: Optional[Dict[str, Any]] = Field(default=None)
    user_settings: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _ensure_update_payload(self) -> "EditMessageRequest":
        """Ensure that at least one payload is provided for an update."""

        if not (self.user_message or self.ai_response):
            raise ValueError("at least one message payload must be provided")
        return self


class UpdateMessageRequest(BaseChatRequest):
    """Request payload for updating message metadata or attachments."""

    message_id: int = Field(..., ge=1)
    patch: Optional[MessagePatch] = Field(default=None)
    append_image_locations: bool = Field(default=False)


class RemoveMessagesRequest(BaseChatRequest):
    """Request payload for deleting messages from a session."""

    session_id: str = Field(...)
    message_ids: list[int] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_ids(self) -> "RemoveMessagesRequest":
        """Ensure the provided message identifiers are positive integers."""

        for message_id in self.message_ids:
            if message_id <= 0:
                raise ValueError("message_ids must be positive integers")
        return self


__all__ = [
    "CreateMessageRequest",
    "EditMessageRequest",
    "RemoveMessagesRequest",
    "UpdateMessageRequest",
]
