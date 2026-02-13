"""Helper queries for :mod:`features.chat.repositories.chat_sessions`."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from features.chat.db_models import ChatGroup, ChatMessage, ChatSession
from features.chat.mappers import chat_session_to_dict

from .utils import coerce_datetime, normalise_tags


async def list_customer_sessions(
    session: AsyncSession,
    *,
    customer_id: int,
    start_date: datetime | str | None = None,
    end_date: datetime | str | None = None,
    tags: Iterable[str] | None = None,
    ai_character_name: str | None = None,
    task_status: str | None = None,
    task_priority: str | None = None,
    offset: int = 0,
    limit: int = 30,
    include_messages: bool = True,
) -> list[dict[str, Any]]:
    """Return paginated sessions for a customer with optional filters.

    Includes group information for group chat sessions (group_id, group_name).
    """

    start_dt = coerce_datetime(start_date)
    end_dt = coerce_datetime(end_date)

    # Exclude empty sessions (sessions with no messages)
    has_messages = (
        select(ChatMessage.message_id)
        .where(ChatMessage.session_id == ChatSession.session_id)
        .correlate(ChatSession)
        .exists()
    )

    # Select sessions with optional group info
    query = (
        select(ChatSession, ChatGroup.name.label("group_name"))
        .outerjoin(ChatGroup, ChatSession.group_id == ChatGroup.id)
        .where(ChatSession.customer_id == customer_id)
        .where(or_(has_messages, ChatSession.task_status.isnot(None)))
        .order_by(ChatSession.last_update.desc(), ChatSession.created_at.desc())
    )
    if start_dt is not None:
        query = query.where(ChatSession.last_update >= start_dt)
    if end_dt is not None:
        query = query.where(ChatSession.last_update < end_dt)
    if ai_character_name is not None:
        query = query.where(ChatSession.ai_character_name == ai_character_name)
    if task_status is not None:
        if task_status in ("active", "waiting", "done"):
            query = query.where(ChatSession.task_status == task_status)
        elif task_status == "any":
            query = query.where(ChatSession.task_status.isnot(None))
        elif task_status == "none":
            query = query.where(ChatSession.task_status.is_(None))
    if task_priority is not None:
        query = query.where(ChatSession.task_priority == task_priority)
    if include_messages:
        query = query.options(selectinload(ChatSession.messages))

    filter_tags = {tag.lower() for tag in normalise_tags(tags)}
    if not filter_tags:
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)

    result = await session.execute(query)
    rows = list(result.unique().all())

    if filter_tags:
        rows = [
            (session_obj, group_name)
            for session_obj, group_name in rows
            if any(tag.lower() in filter_tags for tag in (session_obj.tags or []))
        ]

    if filter_tags:
        sliced = rows[offset : offset + limit if limit else None]
    else:
        sliced = rows

    return [
        chat_session_to_dict(session_obj, include_messages=include_messages, group_name=group_name)
        for session_obj, group_name in sliced
    ]


async def search_customer_sessions(
    session: AsyncSession,
    *,
    customer_id: int,
    search_text: str | None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Return sessions matching ``search_text`` across metadata and messages.

    Includes group information for group chat sessions (group_id, group_name).
    Also searches in group names to support finding group chats by name.
    """

    # Exclude empty sessions (sessions with no messages)
    has_messages = (
        select(ChatMessage.message_id)
        .where(ChatMessage.session_id == ChatSession.session_id)
        .correlate(ChatSession)
        .exists()
    )

    # Select sessions with optional group info
    base_query = (
        select(ChatSession, ChatGroup.name.label("group_name"))
        .outerjoin(ChatGroup, ChatSession.group_id == ChatGroup.id)
        .where(ChatSession.customer_id == customer_id)
        .where(or_(has_messages, ChatSession.task_status.isnot(None)))
    )

    if search_text:
        like_pattern = f"%{search_text.lower()}%"
        base_query = (
            base_query.join(
                ChatMessage, ChatMessage.session_id == ChatSession.session_id, isouter=True
            )
            .where(
                or_(
                    func.lower(ChatMessage.message).like(like_pattern),
                    func.lower(ChatSession.session_name).like(like_pattern),
                    func.lower(ChatSession.ai_character_name).like(like_pattern),
                    # Also search in group names
                    func.lower(ChatGroup.name).like(like_pattern),
                )
            )
        )

    base_query = base_query.order_by(
        ChatSession.last_update.desc(), ChatSession.created_at.desc()
    ).limit(limit)

    result = await session.execute(base_query)
    rows = result.unique().all()

    # Build response with group info from joined data
    return [
        chat_session_to_dict(session_obj, include_messages=False, group_name=group_name)
        for session_obj, group_name in rows
    ]


__all__ = ["list_customer_sessions", "search_customer_sessions"]
