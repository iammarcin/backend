"""Session and message retrieval for proactive agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from core.exceptions import NotFoundError
from features.proactive_agent.repositories import ProactiveAgentRepository


class SessionHandler:
    """Handles session management and message retrieval."""

    def __init__(self, repository: ProactiveAgentRepository) -> None:
        self._repository = repository

    async def get_messages(
        self,
        session_id: str,
        user_id: int,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get messages for a session."""
        session = await self._repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        if session.customer_id != user_id:
            raise NotFoundError(f"Session {session_id} not found")

        messages, total = await self._repository.get_messages_for_session(
            session_id=session_id,
            since=since,
            limit=limit,
            offset=offset,
        )

        return {
            "messages": [self._repository.message_to_dict(m) for m in messages],
            "session_id": session_id,
            "has_more": (offset + len(messages)) < total,
            "total": total,
        }

    async def get_new_messages(
        self,
        session_id: str,
        user_id: int,
        since: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Get new agent messages since a timestamp (for polling)."""
        session = await self._repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Session {session_id} not found")

        if session.customer_id != user_id:
            raise NotFoundError(f"Session {session_id} not found")

        messages = await self._repository.get_new_agent_messages(
            session_id=session_id,
            since=since,
        )

        return [self._repository.message_to_dict(m) for m in messages]

    async def get_session(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        ai_character_name: str = "sherlock",
    ) -> dict[str, Any]:
        """Get or create a session for a user."""
        session = await self._repository.get_or_create_session(
            user_id=user_id,
            session_id=session_id,
            ai_character_name=ai_character_name,
        )

        messages, total = await self._repository.get_messages_for_session(
            session_id=session.session_id,
            limit=1,
        )

        result = self._repository.session_to_dict(session)
        result["message_count"] = total
        return result

    async def update_claude_session_id(
        self,
        session_id: str,
        claude_session_id: str,
    ) -> dict[str, Any]:
        """Update the Claude Code session ID for a session."""
        session = await self._repository.update_session_claude_id(
            session_id=session_id,
            claude_session_id=claude_session_id,
        )
        if not session:
            raise NotFoundError(f"Session {session_id} not found")
        return self._repository.session_to_dict(session)


__all__ = ["SessionHandler"]
