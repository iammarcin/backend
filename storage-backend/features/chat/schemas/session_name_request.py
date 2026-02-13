"""Request schema for generating a chat session name."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator, model_validator

from .base import BaseChatRequest


class SessionNameRequest(BaseChatRequest):
    """Accepts either a prompt or an existing session ID for name generation."""

    prompt: Optional[str | List[Any]] = Field(
        default=None, description="Prompt content used to derive a session name",
    )
    settings: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = Field(
        default=None,
        description="Identifier of an existing session",
    )

    @field_validator("prompt")
    @classmethod
    def _sanitize_prompt(cls, value: Optional[str | List[Any]]) -> Optional[str | List[Any]]:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        if isinstance(value, list) and value:
            return value
        raise ValueError("Prompt must be a non-empty string or list of items")

    @model_validator(mode="after")
    def _ensure_source(self) -> "SessionNameRequest":
        if self.prompt is None and not self.session_id:
            raise ValueError("Either prompt or session_id must be provided")
        return self


__all__ = ["SessionNameRequest"]
