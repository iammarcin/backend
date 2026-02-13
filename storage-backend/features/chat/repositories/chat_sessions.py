"""Repository for :class:`features.chat.db_models.ChatSession`."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import DatabaseError
from features.chat.db_models import ChatMessage, ChatSession

from .chat_session_mutations import apply_metadata_updates, build_chat_session
from .chat_session_queries import list_customer_sessions, search_customer_sessions


logger = logging.getLogger(__name__)


class ChatSessionRepository:
    """Manage CRUD operations for :class:`ChatSession` rows."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def create_session(
        self,
        *,
        customer_id: int,
        session_name: str = "New chat",
        ai_character_name: str = "assistant",
        ai_text_gen_model: str | None = None,
        tags: Iterable[str] | None = None,
        auto_trigger_tts: bool = False,
        claude_session_id: str | None = None,
        created_at: datetime | str | None = None,
        last_update: datetime | str | None = None,
        session_id: str | None = None,
    ) -> ChatSession:
        """Insert a new chat session and return the ORM instance.

        If session_id is provided, uses that instead of generating a new UUID.
        """

        session_obj = build_chat_session(
            customer_id=customer_id,
            session_name=session_name,
            ai_character_name=ai_character_name,
            ai_text_gen_model=ai_text_gen_model,
            tags=tags,
            auto_trigger_tts=auto_trigger_tts,
            claude_session_id=claude_session_id,
            created_at=created_at,
            last_update=last_update,
            session_id=session_id,
        )

        self._session.add(session_obj)
        await self._session.flush()
        return session_obj

    async def get_by_id(
        self,
        session_id: str,
        *,
        customer_id: int | None = None,
        include_messages: bool = False,
    ) -> ChatSession | None:
        """Return a session by its identifier."""

        query = select(ChatSession).where(ChatSession.session_id == session_id)
        if customer_id is not None:
            query = query.where(ChatSession.customer_id == customer_id)
        if include_messages:
            query = query.options(selectinload(ChatSession.messages))
        result = await self._session.execute(query)
        return result.scalars().unique().first()

    async def get_or_create_for_character(
        self,
        *,
        customer_id: int,
        ai_character_name: str,
        session_name: str = "New chat",
    ) -> ChatSession:
        """Return an existing session for ``ai_character_name`` or create one."""

        query = (
            select(ChatSession)
            .where(
                ChatSession.customer_id == customer_id,
                ChatSession.ai_character_name == ai_character_name,
            )
            .order_by(ChatSession.last_update.desc())
        )
        result = await self._session.execute(query)
        session_obj = result.scalars().first()
        if session_obj is not None:
            return session_obj

        return await self.create_session(
            customer_id=customer_id,
            session_name=session_name,
            ai_character_name=ai_character_name,
        )

    async def list_sessions(
        self,
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
        """Return paginated sessions for a customer with optional filters."""

        return await list_customer_sessions(
            self._session,
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            tags=tags,
            ai_character_name=ai_character_name,
            task_status=task_status,
            task_priority=task_priority,
            offset=offset,
            limit=limit,
            include_messages=include_messages,
        )

    async def search_sessions(
        self,
        *,
        customer_id: int,
        search_text: str | None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Return sessions matching ``search_text`` across metadata and messages."""

        return await search_customer_sessions(
            self._session,
            customer_id=customer_id,
            search_text=search_text,
            limit=limit,
        )

    async def update_session_metadata(
        self,
        *,
        session_id: str,
        customer_id: int,
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
    ) -> ChatSession:
        """Update mutable session fields."""

        session_obj = await self.get_by_id(
            session_id,
            customer_id=customer_id,
            include_messages=False,
        )
        if session_obj is None:
            raise DatabaseError("Chat session not found", operation="update_session")

        apply_metadata_updates(
            session_obj,
            session_name=session_name,
            ai_character_name=ai_character_name,
            auto_trigger_tts=auto_trigger_tts,
            ai_text_gen_model=ai_text_gen_model,
            tags=tags,
            claude_session_id=claude_session_id,
            update_last_mod_time=update_last_mod_time,
            last_update_override=last_update_override,
            task_status=task_status,
            task_priority=task_priority,
            task_description=task_description,
            clear_task_metadata=clear_task_metadata,
        )

        await self._session.flush()
        return session_obj

    async def add_notification_tag(
        self,
        *,
        session_id: str,
        customer_id: int,
    ) -> None:
        """Add ``notification`` tag to a session without overwriting others."""

        session_obj = await self.get_by_id(
            session_id,
            customer_id=customer_id,
            include_messages=False,
        )
        if session_obj is None:
            logger.warning("Cannot add notification tag: session %s not found", session_id)
            return

        current_tags = list(session_obj.tags or [])
        if "notification" in current_tags:
            logger.debug("Notification tag already exists on session %s", session_id)
            return

        current_tags.append("notification")

        try:
            await self.update_session_metadata(
                session_id=session_id,
                customer_id=customer_id,
                tags=current_tags,
                update_last_mod_time=False,
            )
            logger.info("Added notification tag to session %s", session_id)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Failed to append notification tag to session %s: %s", session_id, exc
            )

    async def delete_session(
        self, *, session_id: str, customer_id: int
    ) -> tuple[bool, list[int]]:
        """Remove a session and all associated messages."""

        session_obj = await self.get_by_id(session_id, customer_id=customer_id)
        if session_obj is None:
            return False, []

        result = await self._session.execute(
            select(ChatMessage.message_id).where(ChatMessage.session_id == session_id)
        )
        message_ids = list(result.scalars().all())

        logger.info(
            "Deleting session %s with %d messages", session_id, len(message_ids)
        )

        # Delete session_summaries first to avoid FK constraint violation
        # (even though there's ON DELETE CASCADE, SQLAlchemy tries to nullify FK first)
        from features.semantic_search.db_models import SessionSummary

        await self._session.execute(
            delete(SessionSummary).where(SessionSummary.session_id == session_id)
        )

        # Then delete messages and session
        await self._session.execute(
            delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        await self._session.delete(session_obj)
        await self._session.flush()
        return True, message_ids


__all__ = ["ChatSessionRepository"]

