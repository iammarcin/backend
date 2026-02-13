"""Shared helpers and dependency wiring for chat history services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from core.exceptions import DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.mappers import chat_session_to_dict
from features.chat.repositories import (
    ChatMessageRepository,
    ChatSessionRepository,
    PromptRepository,
    UserRepository,
)
from features.chat.schemas.responses import ChatSessionPayload


@dataclass(slots=True)
class HistoryRepositories:
    """Repository bundle used by the chat history workflows."""

    sessions: ChatSessionRepository
    messages: ChatMessageRepository
    prompts: PromptRepository
    users: UserRepository


def build_repositories(session: AsyncSession) -> HistoryRepositories:
    """Instantiate repository helpers for the provided database session."""

    return HistoryRepositories(
        sessions=ChatSessionRepository(session),
        messages=ChatMessageRepository(session),
        prompts=PromptRepository(session),
        users=UserRepository(session),
    )


def resolve_ai_character(requested_character: str | None, user_settings: Dict[str, Any] | None) -> str:
    """Determine the AI character to associate with a session."""

    if requested_character:
        return requested_character
    settings = user_settings or {}
    text_settings = settings.get("text", {})
    return text_settings.get("ai_character", "assistant")


async def load_session_payload(
    repositories: HistoryRepositories,
    session_id: str,
    *,
    customer_id: int,
    include_messages: bool,
) -> ChatSessionPayload:
    """Load and validate a session payload for API responses."""

    session_obj = await repositories.sessions.get_by_id(
        session_id,
        customer_id=customer_id,
        include_messages=include_messages,
    )
    if session_obj is None:
        raise DatabaseError("Chat session not found", operation="fetch_session")
    session_dict = chat_session_to_dict(
        session_obj, include_messages=include_messages
    )
    return ChatSessionPayload.model_validate(session_dict)
