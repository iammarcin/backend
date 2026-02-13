"""Helpers for chat session-name generation and persistence."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from core.exceptions import ConfigurationError, DatabaseError
from features.chat.repositories.chat_sessions import ChatSessionRepository
from infrastructure.db.mysql import require_main_session_factory, session_scope

logger = logging.getLogger(__name__)


def build_session_name_prompt(user_prompt: Any) -> str:
    """Create the prompt used for session-name generation."""

    return (
        "Based on this conversation starter, generate a short session name (max 50 characters):\n\n"
        f"User: {user_prompt}\n\nGenerate only the session name, nothing else."
    )


def prepare_session_name_settings(settings: dict | None) -> dict:
    """Return a sanitized settings copy suitable for lightweight name generation."""

    settings_copy = deepcopy(settings or {})

    # Always replace the text settings with a lean, deterministic configuration so
    # session-name generation is fast and consistent regardless of user-provided
    # chat settings.
    settings_copy["text"] = {
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 50,
    }

    return settings_copy


async def request_session_name(
    *,
    service,
    session_prompt: str,
    settings: dict,
    customer_id: int,
):
    """Call the chat service to generate a session name."""

    return await service.generate_response(
        prompt=session_prompt,
        settings=settings,
        customer_id=customer_id,
    )


def normalize_session_name(raw_name: str, prompt_preview: str) -> str:
    """Normalize provider output into a bounded session name with fallbacks."""

    name = (raw_name or "").strip().strip('"').strip("'")
    if not name:
        name = (prompt_preview or "")[:50] or "New chat"
    if len(name) > 50:
        name = name[:50].rstrip()
    return name


async def persist_session_name(
    *,
    session_id: str,
    customer_id: int,
    session_name: str,
    logger: logging.Logger,
) -> None:
    """Persist a generated session name for an existing chat session."""

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.warning(
            "Chat database not configured; skipping session name persistence: %s", exc
        )
        return

    try:
        async with session_scope(session_factory) as db_session:
            repository = ChatSessionRepository(db_session)
            await repository.update_session_metadata(
                session_id=session_id,
                customer_id=customer_id,
                session_name=session_name,
                update_last_mod_time=False,
            )
    except DatabaseError as exc:
        logger.warning(
            "Failed to persist session name for session %s: %s", session_id, exc
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Unexpected error while updating session name for %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
    else:
        logger.info(
            "Persisted session name for customer %s (session_id=%s)",
            customer_id,
            session_id,
        )


async def load_session_for_prompt(
    *, session_id: str, customer_id: int, logger: logging.Logger
):
    """Return a chat session with messages for prompt derivation, if available."""

    try:
        session_factory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.warning(
            "Chat database not configured; cannot load session %s: %s", session_id, exc
        )
        return None

    try:
        async with session_scope(session_factory) as db_session:
            repository = ChatSessionRepository(db_session)
            return await repository.get_by_id(
                session_id,
                customer_id=customer_id,
                include_messages=True,
            )
    except DatabaseError as exc:
        logger.warning(
            "Failed to load chat session %s for name generation: %s", session_id, exc
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error(
            "Unexpected error while loading session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
    return None


def build_prompt_from_session_history(session) -> str | None:
    """Construct a naming prompt from the first messages of an existing session."""

    if session is None or not getattr(session, "messages", None):
        return None

    messages = session.messages[:2]
    first_message = (messages[0].message or "") if messages else ""
    second_message = (messages[1].message or "") if len(messages) > 1 else ""

    if not first_message and not second_message:
        return None

    text_to_process = f"request: {first_message}\nresponse: {second_message}".strip()
    prompt = (
        "Following is a message from chat application:\n"
        f"{text_to_process}\n\n"
        "Based on this message please generate a session name, that will represent accurately the topic of this conversation.\n"
        "Please try to make session name as short as possible.\n"
        "Respond with just single sentence consisting of session name. Don't add any other information."
    )

    ai_character = (getattr(session, "ai_character_name", "") or "").lower()
    if ai_character == "developer":
        prompt += (
            "\nIf it's related to any specific programming language or technology, please include it in the session name."
        )

    return prompt


__all__ = [
    "build_session_name_prompt",
    "build_prompt_from_session_history",
    "load_session_for_prompt",
    "normalize_session_name",
    "persist_session_name",
    "prepare_session_name_settings",
    "request_session_name",
]
