"""Repository for session summary persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.db_models import ChatMessage, ChatSession
from features.semantic_search.db_models import SessionSummary

logger = logging.getLogger(__name__)


def _coerce_datetime(value: datetime | str | None, field_name: str) -> datetime:
    """Ensure datetime fields remain datetime objects."""

    if value is None:
        raise ValueError(f"{field_name} must be datetime, got None")
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except (ValueError, AttributeError) as exc:
            logger.warning("Invalid datetime string for %s: %s", field_name, value)
            raise ValueError(f"{field_name} must be datetime, got string: {value}") from exc
    logger.warning("Invalid datetime type for %s: %s", field_name, type(value))
    raise ValueError(f"{field_name} must be datetime, got {type(value)!r}")


class SessionSummaryRepository:
    """Repository for CRUD operations on session_summaries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        *,
        session_id: str,
        customer_id: int,
        summary: str,
        key_topics: Sequence[str],
        main_entities: Sequence[str],
        message_count: int,
        first_message_date: datetime,
        last_message_date: datetime,
        summary_model: str,
        summary_config_version: int,
        tags: Optional[Iterable[str]] = None,
    ) -> SessionSummary:
        """Insert a new session summary."""

        first_message_date = _coerce_datetime(first_message_date, "first_message_date")
        last_message_date = _coerce_datetime(last_message_date, "last_message_date")

        now = datetime.now(UTC)
        summary_obj = SessionSummary(
            session_id=session_id,
            customer_id=customer_id,
            summary=summary,
            key_topics=list(key_topics),
            main_entities=list(main_entities),
            message_count=message_count,
            first_message_date=first_message_date,
            last_message_date=last_message_date,
            tags=list(tags) if tags is not None else [],
            summary_model=summary_model,
            summary_config_version=summary_config_version,
            generated_at=now,
            last_updated=now,
        )

        self.db.add(summary_obj)
        await self.db.flush()
        return summary_obj

    async def update(
        self,
        *,
        session_id: str,
        summary: str,
        key_topics: Sequence[str],
        main_entities: Sequence[str],
        message_count: int,
        last_message_date: datetime,
        summary_model: str,
        summary_config_version: int,
    ) -> Optional[SessionSummary]:
        """Update an existing session summary."""

        last_message_date = _coerce_datetime(last_message_date, "last_message_date")

        summary_obj = await self.get_by_session_id(session_id)
        if summary_obj is None:
            return None

        summary_obj.summary = summary
        summary_obj.key_topics = list(key_topics)
        summary_obj.main_entities = list(main_entities)
        summary_obj.message_count = message_count
        summary_obj.last_message_date = last_message_date
        summary_obj.summary_model = summary_model
        summary_obj.summary_config_version = summary_config_version
        summary_obj.last_updated = datetime.now(UTC)

        await self.db.flush()
        return summary_obj

    async def get_by_session_id(self, session_id: str) -> Optional[SessionSummary]:
        stmt: Select[tuple[SessionSummary]] = select(SessionSummary).where(SessionSummary.session_id == session_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete_by_session_id(self, session_id: str) -> bool:
        summary = await self.get_by_session_id(session_id)
        if summary is None:
            return False
        await self.db.delete(summary)
        await self.db.flush()
        return True

    async def get_stale_summaries(
        self,
        *,
        customer_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> list[tuple[str, datetime]]:
        """Return sessions whose summaries are older than the session data."""

        stmt = (
            select(ChatSession.session_id, ChatSession.last_update)
            .join(SessionSummary, ChatSession.session_id == SessionSummary.session_id)
            .where(ChatSession.last_update > SessionSummary.last_updated)
        )

        if customer_id is not None:
            stmt = stmt.where(ChatSession.customer_id == customer_id)
        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        rows = result.all()
        return [(row.session_id, row.last_update) for row in rows]

    async def get_sessions_without_summary(
        self,
        *,
        customer_id: Optional[int] = None,
        min_messages: int = 3,
        limit: Optional[int] = None,
    ) -> list[str]:
        """Return session IDs that do not yet have summaries."""

        message_count_subquery = (
            select(
                ChatMessage.session_id.label("session_id"),
                func.count(ChatMessage.message_id).label("message_count"),
            )
            .group_by(ChatMessage.session_id)
            .subquery()
        )

        stmt = (
            select(ChatSession.session_id)
            .join(message_count_subquery, ChatSession.session_id == message_count_subquery.c.session_id)
            .outerjoin(SessionSummary, ChatSession.session_id == SessionSummary.session_id)
            .where(SessionSummary.id.is_(None))
            .where(message_count_subquery.c.message_count >= min_messages)
        )

        if customer_id is not None:
            stmt = stmt.where(ChatSession.customer_id == customer_id)
        if limit:
            stmt = stmt.limit(limit)

        stmt = stmt.order_by(ChatSession.last_update)

        result = await self.db.execute(stmt)
        return list(result.scalars())
