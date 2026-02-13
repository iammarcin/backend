"""Request models for CRUD operations on saved prompts."""

from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field

from .base import BaseChatRequest


class PromptCreateRequest(BaseChatRequest):
    """Create a new reusable prompt snippet."""

    title: str
    prompt: str = Field(validation_alias=AliasChoices("prompt", "promptText"))


class PromptListRequest(BaseChatRequest):
    """List prompts belonging to a customer."""


class PromptUpdateRequest(BaseChatRequest):
    """Update the metadata or body of a prompt."""

    prompt_id: int = Field(
        ..., ge=1, validation_alias=AliasChoices("prompt_id", "promptId")
    )
    title: Optional[str] = None
    prompt: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("prompt", "promptText")
    )


class PromptDeleteRequest(BaseChatRequest):
    """Delete a prompt and all related metadata."""

    prompt_id: int = Field(
        ..., ge=1, validation_alias=AliasChoices("prompt_id", "promptId")
    )


__all__ = [
    "PromptCreateRequest",
    "PromptDeleteRequest",
    "PromptListRequest",
    "PromptUpdateRequest",
]
