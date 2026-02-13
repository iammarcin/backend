"""Repository for proactive agent - wraps existing chat repositories."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.db_models import ChatMessage, ChatSession
from features.chat.repositories.chat_messages import ChatMessageRepository
from features.chat.repositories.chat_sessions import ChatSessionRepository

from .converters import message_to_dict, session_to_dict

logger = logging.getLogger(__name__)

DEFAULT_CHARACTER = "sherlock"

# Character display names for session naming
CHARACTER_DISPLAY_NAMES = {
    "sherlock": "Sherlock",
    "bugsy": "Bugsy",
}


class ProactiveAgentRepository:
    """Database operations for proactive agent using existing chat tables.

    Maps proactive agent concepts to ChatSession/ChatMessage:
    - ProactiveAgentSession → ChatSession with ai_character_name
    - ProactiveAgentMessage → ChatMessage with metadata in claudeCodeData
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chat_session_repo = ChatSessionRepository(session)
        self._chat_message_repo = ChatMessageRepository(session)

    async def get_or_create_session(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        ai_character_name: str = DEFAULT_CHARACTER,
    ) -> ChatSession:
        """Get existing session or create a new one.

        If session_id is provided and doesn't exist, create it with that exact ID
        to ensure frontend's session_id is preserved. If session_id is omitted,
        always create a new session instead of reusing a per-character session.
        """
        session_name = CHARACTER_DISPLAY_NAMES.get(ai_character_name, ai_character_name.title())
        if session_id:
            existing = await self._chat_session_repo.get_by_id(
                session_id, customer_id=user_id
            )
            if existing:
                # Fix character name if it was created with a default and now
                # the real character is known (e.g. session created as 'sherlock'
                # but user is actually talking to 'mycroft').
                if (
                    ai_character_name != DEFAULT_CHARACTER
                    and existing.ai_character_name != ai_character_name
                ):
                    existing.ai_character_name = ai_character_name
                    await self._session.flush()
                return existing

            # Session doesn't exist - create it with the provided session_id
            return await self._chat_session_repo.create_session(
                customer_id=user_id,
                session_name=session_name,
                ai_character_name=ai_character_name,
                session_id=session_id,
            )

        # No session_id provided - create new session
        return await self._chat_session_repo.create_session(
            customer_id=user_id,
            session_name=session_name,
            ai_character_name=ai_character_name,
        )

    async def get_session_by_id(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID."""
        return await self._chat_session_repo.get_by_id(session_id)

    async def update_session_claude_id(
        self,
        session_id: str,
        claude_session_id: Optional[str],
    ) -> Optional[ChatSession]:
        """Update the Claude Code session ID for a session."""
        session = await self.get_session_by_id(session_id)
        if not session:
            return None

        session.claude_session_id = claude_session_id
        await self._session.flush()
        return session

    async def create_message(
        self,
        session_id: str,
        customer_id: int,
        direction: str,
        content: str,
        source: Optional[str] = None,
        is_heartbeat_ok: bool = False,
        ai_character_name: str = DEFAULT_CHARACTER,
        ai_reasoning: Optional[str] = None,
        image_locations: Optional[list[str]] = None,
        file_locations: Optional[list[str]] = None,
        chart_data: Optional[list[dict[str, Any]]] = None,
    ) -> ChatMessage:
        """Create a new message in a session.

        Maps direction to sender and stores extra metadata in claudeCodeData.
        ai_reasoning stores the thinking/reasoning content separately from message.
        image_locations stores attached image URLs.
        file_locations stores attached file URLs (PDFs, etc.).
        chart_data stores chart payloads for inline visualizations.
        """
        # Map direction to sender (User capitalized to match normal chat behavior)
        sender = "User" if direction == "user_to_agent" else "AI"

        # Build claude_code_data with proactive agent metadata
        claude_code_data = {
            "proactive_agent": True,
            "direction": direction,
            "source": source,
            "is_heartbeat_ok": is_heartbeat_ok,
        }

        # Build payload with optional ai_reasoning, attachments, and chart_data
        payload: dict[str, Any] = {
            "message": content,
            "sender": sender,
            "ai_character_name": ai_character_name,
        }
        if ai_reasoning:
            payload["ai_reasoning"] = ai_reasoning
        if image_locations:
            payload["image_locations"] = image_locations
        if file_locations:
            payload["file_locations"] = file_locations
        if chart_data:
            payload["chart_data"] = chart_data

        message = await self._chat_message_repo.insert_message(
            session_id=session_id,
            customer_id=customer_id,
            payload=payload,
            is_ai_message=(sender == "AI"),
            claude_code_data=claude_code_data,
        )

        # Update session last_update
        await self._chat_session_repo.update_session_metadata(
            session_id=session_id,
            customer_id=customer_id,
            update_last_mod_time=True,
        )

        logger.debug(
            "Created proactive agent message",
            extra={
                "session_id": session_id,
                "direction": direction,
                "message_id": message.message_id,
            },
        )
        return message

    async def get_messages_for_session(
        self,
        session_id: str,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChatMessage], int]:
        """Get messages for a session with optional time filter.

        Note: We only filter by session_id, not ai_character_name, because
        the session itself is already filtered by character. User messages
        don't have ai_character_name set (only AI messages do).
        """
        query = select(ChatMessage).where(ChatMessage.session_id == session_id)

        if since:
            query = query.where(ChatMessage.created_at > since)

        # Get total count
        count_result = await self._session.execute(query)
        total = len(count_result.scalars().all())

        # Get paginated results (newest first, then reverse for chronological)
        query = (
            query.order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(query)
        messages = list(result.scalars().all())
        messages.reverse()

        return messages, total

    async def update_message_audio_url(
        self,
        message_id: int,
        audio_file_url: str,
    ) -> None:
        """Update a message with the audio file URL."""
        message = await self._chat_message_repo.get_message_by_id(message_id)
        if not message:
            return

        file_locations = list(message.file_locations or [])
        if audio_file_url not in file_locations:
            file_locations = [audio_file_url, *file_locations]

        await self._chat_message_repo.update_message(
            message_id=message_id,
            customer_id=message.customer_id,
            payload={"file_locations": file_locations},
        )

    async def get_new_agent_messages(
        self,
        session_id: str,
        since: Optional[datetime] = None,
    ) -> list[ChatMessage]:
        """Get new messages from agent (for polling).

        Returns AI messages only (sender='AI'), filtering out suppressed heartbeats.
        """
        query = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.sender == "AI",
            )
            .order_by(ChatMessage.created_at.asc())
        )

        if since:
            query = query.where(ChatMessage.created_at > since)

        result = await self._session.execute(query)
        messages = list(result.scalars().all())

        # Filter out suppressed heartbeats
        return [
            m for m in messages
            if not (m.claude_code_data or {}).get("is_heartbeat_ok", False)
        ]

    def message_to_dict(
        self,
        message: ChatMessage,
        include_reasoning: bool = True,
    ) -> dict[str, Any]:
        """Convert ChatMessage to proactive agent response format.

        Delegates to converters.message_to_dict for actual conversion.
        """
        return message_to_dict(message, include_reasoning)

    def session_to_dict(self, session: ChatSession) -> dict[str, Any]:
        """Convert ChatSession to proactive agent response format.

        Delegates to converters.session_to_dict for actual conversion.
        """
        return session_to_dict(session)


__all__ = ["ProactiveAgentRepository"]
