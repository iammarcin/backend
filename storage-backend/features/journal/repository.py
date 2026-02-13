"""Repository for journal data access."""

from datetime import date, datetime, timedelta
from typing import Optional, Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.environment import IS_POSTGRESQL
from features.chat.db_models import ChatMessage


def _json_array_length(column):
    """Get length of JSON array column.

    MySQL: json_length(column)
    PostgreSQL: jsonb_array_length(column)
    """
    if IS_POSTGRESQL:
        return func.jsonb_array_length(column)
    return func.json_length(column)


class JournalRepository:
    """Access journal entries from ChatMessagesNG."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_entries_for_date(
        self,
        session_id: str,
        target_date: date,
    ) -> Sequence[ChatMessage]:
        """Get all journal entries for a specific date, ordered by created_at."""
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        query = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.session_id == session_id,
                    ChatMessage.created_at >= start_of_day,
                    ChatMessage.created_at <= end_of_day,
                )
            )
            .order_by(ChatMessage.created_at.asc())
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_first_entry_for_date(
        self,
        session_id: str,
        target_date: date,
    ) -> Optional[ChatMessage]:
        """Get first entry of the day (typically sleep/day feedback)."""
        entries = await self.get_entries_for_date(session_id, target_date)
        return entries[0] if entries else None

    async def get_second_entry_for_date(
        self,
        session_id: str,
        target_date: date,
    ) -> Optional[ChatMessage]:
        """Get second entry of the day (typically meals)."""
        entries = await self.get_entries_for_date(session_id, target_date)
        return entries[1] if len(entries) > 1 else None

    async def get_messages_with_images(
        self,
        session_id: str,
        limit: int = 50,
        include_with_description: bool = False,
    ) -> Sequence[ChatMessage]:
        """Get messages with images, optionally filtering out those with descriptions."""
        conditions = [
            ChatMessage.session_id == session_id,
            _json_array_length(ChatMessage.image_locations) > 0,
        ]

        # Filter out messages that already have descriptions (in SQL, not Python)
        if not include_with_description:
            conditions.append(
                (ChatMessage.image_description == None) | (ChatMessage.image_description == "")  # noqa: E711
            )

        query = (
            select(ChatMessage)
            .where(and_(*conditions))
            .order_by(ChatMessage.created_at.desc())  # Newest first
            .limit(limit)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def update_image_description(
        self,
        message_id: int,
        description: str,
    ) -> bool:
        """Update image_description for a message."""
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.message_id == message_id)
            .values(image_description=description)
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount > 0

    async def get_message_by_id(
        self,
        message_id: int,
    ) -> Optional[ChatMessage]:
        """Get a single message by ID."""
        query = select(ChatMessage).where(ChatMessage.message_id == message_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_recent_entries(
        self,
        session_id: str,
        days: int = 7,
    ) -> Sequence[ChatMessage]:
        """Get entries from the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        query = (
            select(ChatMessage)
            .where(
                and_(
                    ChatMessage.session_id == session_id,
                    ChatMessage.created_at >= cutoff,
                )
            )
            .order_by(ChatMessage.created_at.desc())
        )
        result = await self._session.execute(query)
        return result.scalars().all()


__all__ = ["JournalRepository"]
