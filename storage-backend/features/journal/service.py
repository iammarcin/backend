"""Service layer for journal feature."""

from datetime import date, datetime, timedelta
from typing import Any, Optional

from features.chat.db_models import ChatMessage
from features.journal.repository import JournalRepository
from features.journal.schemas import JournalEntry, JournalResponse


def _message_to_entry(
    message: ChatMessage,
    entry_type: str,
) -> JournalEntry:
    """Convert ChatMessage to JournalEntry."""
    return JournalEntry(
        message_id=message.message_id,
        entry_type=entry_type,
        content=message.message or "",
        image_urls=list(message.image_locations or []),
        image_description=getattr(message, "image_description", None),
        created_at=message.created_at,
    )


class JournalService:
    """Business logic for journal access."""

    def __init__(self, repository: JournalRepository):
        self._repository = repository

    async def get_today_status(
        self,
        session_id: str,
    ) -> JournalResponse:
        """
        Get current status for Sherlock:
        - Today's sleep feedback (first entry of today)
        - Yesterday's meals (second entry of yesterday)
        """
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Today's first entry = sleep/day feedback
        sleep_entry = await self._repository.get_first_entry_for_date(
            session_id, today
        )

        # Yesterday's second entry = meals
        meals_entry = await self._repository.get_second_entry_for_date(
            session_id, yesterday
        )

        return JournalResponse(
            query_date=today.isoformat(),
            today_sleep=_message_to_entry(sleep_entry, "sleep") if sleep_entry else None,
            yesterday_meals=_message_to_entry(meals_entry, "meals") if meals_entry else None,
        )

    async def get_entries_for_date(
        self,
        session_id: str,
        target_date: date,
    ) -> JournalResponse:
        """Get all journal entries for a specific date."""
        entries = await self._repository.get_entries_for_date(session_id, target_date)

        entry_list = []
        for idx, msg in enumerate(entries):
            entry_type = "sleep" if idx == 0 else "meals"
            entry_list.append(_message_to_entry(msg, entry_type))

        return JournalResponse(
            query_date=target_date.isoformat(),
            entries=entry_list,
        )

    async def get_sleep_entries(
        self,
        session_id: str,
        days: int = 7,
    ) -> JournalResponse:
        """Get sleep entries from the last N days."""
        entries = []
        today = date.today()

        for i in range(days):
            target = today - timedelta(days=i)
            entry = await self._repository.get_first_entry_for_date(session_id, target)
            if entry:
                entries.append(_message_to_entry(entry, "sleep"))

        return JournalResponse(
            query_date=today.isoformat(),
            entries=entries,
        )

    async def get_meals_entries(
        self,
        session_id: str,
        days: int = 7,
    ) -> JournalResponse:
        """Get meal entries from the last N days."""
        entries = []
        today = date.today()

        for i in range(days):
            target = today - timedelta(days=i)
            entry = await self._repository.get_second_entry_for_date(session_id, target)
            if entry:
                entries.append(_message_to_entry(entry, "meals"))

        return JournalResponse(
            query_date=today.isoformat(),
            entries=entries,
        )

    async def get_messages_needing_description(
        self,
        session_id: str,
        limit: int = 50,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        """Get messages with images that need descriptions."""
        messages = await self._repository.get_messages_with_images(
            session_id, limit, include_with_description=force
        )
        return [
            {
                "message_id": m.message_id,
                "image_urls": list(m.image_locations or []),
                "content": m.message,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    async def update_image_description(
        self,
        message_id: int,
        description: str,
    ) -> bool:
        """Update image description for a message."""
        return await self._repository.update_image_description(message_id, description)

    async def get_message_by_id(
        self,
        message_id: int,
    ) -> Optional[dict[str, Any]]:
        """Get a single message by ID."""
        message = await self._repository.get_message_by_id(message_id)
        if not message:
            return None
        return {
            "message_id": message.message_id,
            "image_urls": list(message.image_locations or []),
            "content": message.message,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }


__all__ = ["JournalService"]
