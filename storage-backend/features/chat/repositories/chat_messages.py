"""Repository helpers for chat messages."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Iterable, Sequence
from uuid import uuid4

from sqlalchemy import String, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute

from config.environment import IS_POSTGRESQL
from core.exceptions import DatabaseError
from features.chat.db_models import ChatMessage
from features.chat.mappers import chat_message_to_dict

from .message_filters import message_matches_file_filter
from .message_mappers import create_message_from_payload, update_message_fields
from .utils import coerce_datetime


def _json_text_length(column: InstrumentedAttribute) -> Any:
    """Get length of JSON column as text.

    MySQL: length() works directly on JSON columns (treated as text).
    PostgreSQL: JSONB requires cast to text first.
    """
    if IS_POSTGRESQL:
        return func.length(column.cast(String))
    return func.length(column)


def _json_as_text(column: InstrumentedAttribute) -> Any:
    """Get JSON column as text for string operations (LIKE, NOT LIKE).

    MySQL: JSON columns work directly with LIKE.
    PostgreSQL: JSONB requires cast to text first.
    """
    if IS_POSTGRESQL:
        return column.cast(String)
    return column


class ChatMessageRepository:
    """Manage chat message persistence operations."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_message(
        self,
        *,
        session_id: str,
        customer_id: int,
        payload: dict[str, Any],
        is_ai_message: bool,
        claude_code_data: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """Insert a chat message with snake_case field semantics."""

        message_obj = create_message_from_payload(
            session_id=session_id,
            customer_id=customer_id,
            payload=payload,
            is_ai_message=is_ai_message,
            claude_code_data=claude_code_data,
        )

        self._session.add(message_obj)
        await self._session.flush()
        return message_obj

    async def update_message_metadata(
        self,
        *,
        message_id: int,
        customer_id: int,
        metadata_updates: Dict[str, Any],
    ) -> ChatMessage:
        """Update metadata-centric fields such as Claude code data or citations."""

        message = await self.get_message_by_id(message_id)
        if message is None or message.customer_id != customer_id:
            raise DatabaseError("Message not found", operation="update_metadata")

        if not metadata_updates:
            return message

        field_map = {
            "claude_code_data": "claude_code_data",
            "api_text_gen_settings": "api_text_gen_settings",
            "api_text_gen_model_name": "api_text_gen_model_name",
        }

        payload: Dict[str, Any] = {}
        for key, value in metadata_updates.items():
            mapped_key = field_map.get(key, key)
            payload[mapped_key] = value

        update_message_fields(message, payload)
        self._session.add(message)
        await self._session.flush()
        return message

    async def get_message_by_id(self, message_id: int) -> ChatMessage | None:
        """Return a message by primary key."""

        query = select(ChatMessage).where(ChatMessage.message_id == message_id)
        result = await self._session.execute(query)
        return result.scalars().first()

    async def update_message(
        self,
        *,
        message_id: int,
        customer_id: int,
        payload: dict[str, Any],
        append_image_locations: bool = False,
    ) -> ChatMessage:
        """Update an existing message with the supplied payload."""

        message = await self.get_message_by_id(message_id)
        if message is None or message.customer_id != customer_id:
            raise DatabaseError("Message not found", operation="update_message")

        update_message_fields(message, payload, append_image_locations)

        self._session.add(message)
        await self._session.flush()
        return message

    async def get_messages_for_session(self, session_id: str) -> Sequence[ChatMessage]:
        """Return all messages for ``session_id`` ordered chronologically."""

        query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at, ChatMessage.message_id)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def fetch_favorites(self, *, customer_id: int) -> dict[str, Any] | None:
        """Return a virtual session composed of the customer's favourite messages."""

        query = (
            select(ChatMessage)
            .where(
                ChatMessage.customer_id == customer_id,
                ChatMessage.favorite.is_(True),
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.message_id.asc())
        )
        result = await self._session.execute(query)
        messages = result.scalars().all()
        if not messages:
            return None

        now_iso = datetime.now(UTC).isoformat()
        return {
            "session_id": f"favorites_{uuid4()}",
            "customer_id": customer_id,
            "session_name": "Favorite Messages",
            "ai_character_name": "tools_artgen",
            "tags": [],
            "created_at": now_iso,
            "last_update": now_iso,
            "messages": [chat_message_to_dict(message) for message in messages],
        }

    async def fetch_messages_with_files(
        self,
        *,
        customer_id: int,
        older_then_date: datetime | str | None = None,
        younger_then_date: datetime | str | None = None,
        exact_filename: str | None = None,
        ai_only: bool = False,
        offset: int = 0,
        limit: int = 30,
        file_extension: str | None = None,
        check_image_locations: bool = False,
    ) -> list[dict[str, Any]]:
        """Return messages matching attachment filters."""

        older_dt = coerce_datetime(older_then_date)
        younger_dt = coerce_datetime(younger_then_date)

        conditions = [ChatMessage.customer_id == customer_id]
        
        # Add SQL-level filters for files
        if check_image_locations:
            # Check both file_locations and image_locations
            # If exact_filename is provided, also check message text for embedded images
            # (e.g., markdown images like ![alt](url))
            if exact_filename:
                conditions.append(
                    or_(
                        _json_text_length(ChatMessage.file_locations) > 3,
                        _json_text_length(ChatMessage.image_locations) > 3,
                        ChatMessage.message.like(f'%{exact_filename}%'),
                    )
                )
            else:
                conditions.append(
                    or_(
                        _json_text_length(ChatMessage.file_locations) > 3,
                        _json_text_length(ChatMessage.image_locations) > 3,
                    )
                )
        else:
            # file_locations only (non image files)
            conditions.append(_json_text_length(ChatMessage.file_locations) > 3)
            conditions.append(_json_as_text(ChatMessage.file_locations).not_like('%emulated%'))
        
        if older_dt is not None:
            conditions.append(ChatMessage.created_at <= older_dt)
        if younger_dt is not None:
            conditions.append(ChatMessage.created_at >= younger_dt)
        if ai_only:
            conditions.append(ChatMessage.sender == "AI")
        if file_extension:
            # Filter by extension at SQL level
            extension_pattern = f"%{file_extension}%"
            if check_image_locations:
                conditions.append(
                    or_(
                        _json_as_text(ChatMessage.file_locations).like(extension_pattern),
                        _json_as_text(ChatMessage.image_locations).like(extension_pattern),
                    )
                )
            else:
                conditions.append(_json_as_text(ChatMessage.file_locations).like(extension_pattern))

        query = (
            select(ChatMessage)
            .where(and_(*conditions))
            .order_by(ChatMessage.created_at.desc(), ChatMessage.message_id.desc())
        )
        result = await self._session.execute(query)
        messages = result.scalars().all()

        # Apply client-side filtering for exact matches and file candidates
        filtered: list[ChatMessage] = []
        for message in messages:
            matches = message_matches_file_filter(
                message,
                exact_filename=exact_filename,
                file_extension=file_extension,
                check_image_locations=check_image_locations,
            )
            if matches:
                filtered.append(message)

        sliced = filtered[offset : offset + limit if limit else None]
        return [chat_message_to_dict(message) for message in sliced]

    async def remove_messages(
        self,
        *,
        session_id: str,
        customer_id: int,
        message_ids: Iterable[int],
    ) -> int:
        """Delete messages by identifier, returning the number removed."""

        if not message_ids:
            return 0

        query = select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.customer_id == customer_id,
            ChatMessage.message_id.in_(list(message_ids)),
        )
        result = await self._session.execute(query)
        messages = result.scalars().all()
        for message in messages:
            await self._session.delete(message)
        await self._session.flush()
        return len(messages)


__all__ = ["ChatMessageRepository"]

