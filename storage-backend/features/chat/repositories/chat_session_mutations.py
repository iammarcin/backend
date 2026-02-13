"""Helper functions for constructing and updating chat sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from features.chat.db_models import ChatSession

from .utils import coerce_datetime, normalise_tags


def build_chat_session(
    *,
    customer_id: int,
    session_name: str,
    ai_character_name: str,
    ai_text_gen_model: str | None,
    tags: Iterable[str] | None,
    auto_trigger_tts: bool,
    claude_session_id: str | None,
    created_at: datetime | str | None,
    last_update: datetime | str | None,
    session_id: str | None = None,
) -> ChatSession:
    """Create and initialize a :class:`ChatSession` ORM object.

    If session_id is provided, uses that instead of generating a new UUID.
    """

    created_at_dt = coerce_datetime(created_at)
    last_update_dt = coerce_datetime(last_update) or created_at_dt

    session_obj = ChatSession(
        customer_id=customer_id,
        session_name=session_name,
        ai_character_name=ai_character_name,
        ai_text_gen_model=ai_text_gen_model,
        auto_trigger_tts=auto_trigger_tts,
        claude_session_id=claude_session_id,
        tags=normalise_tags(tags),
    )

    # Override session_id if provided (otherwise uses default UUID factory)
    if session_id is not None:
        session_obj.session_id = session_id

    if created_at_dt is not None:
        session_obj.created_at = created_at_dt
    if last_update_dt is not None:
        session_obj.last_update = last_update_dt

    return session_obj


def apply_metadata_updates(
    session_obj: ChatSession,
    *,
    session_name: str | None = None,
    ai_character_name: str | None = None,
    auto_trigger_tts: bool | None = None,
    ai_text_gen_model: str | None = None,
    tags: Iterable[str] | None = None,
    claude_session_id: str | None = None,
    update_last_mod_time: bool = True,
    last_update_override: datetime | str | None = None,
    task_status: str | None = None,
    task_priority: str | None = None,
    task_description: str | None = None,
    clear_task_metadata: bool = False,
) -> None:
    """Apply metadata changes to an existing session object."""

    if session_name is not None:
        session_obj.session_name = session_name
    if ai_character_name is not None:
        session_obj.ai_character_name = ai_character_name
    if auto_trigger_tts is not None:
        session_obj.auto_trigger_tts = auto_trigger_tts
    if ai_text_gen_model is not None:
        session_obj.ai_text_gen_model = ai_text_gen_model
    if tags is not None:
        session_obj.tags = normalise_tags(tags)
    if claude_session_id is not None:
        session_obj.claude_session_id = claude_session_id
    if clear_task_metadata:
        session_obj.task_status = None
        session_obj.task_priority = None
        session_obj.task_description = None
    else:
        if task_status is not None:
            session_obj.task_status = task_status
        if task_priority is not None:
            session_obj.task_priority = task_priority
        if task_description is not None:
            session_obj.task_description = task_description

    if update_last_mod_time:
        override = coerce_datetime(last_update_override)
        session_obj.last_update = override or datetime.now(UTC)


__all__ = ["build_chat_session", "apply_metadata_updates"]
