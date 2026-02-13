"""Business logic service for proactive agent.

This is a facade that delegates to specialized handlers:
- MessageHandler: send/receive messages
- SessionHandler: session and message retrieval

M4 Cleanup Note: StreamingHandler has been removed. The Python poller now
streams directly via WebSocket to /ws/poller-stream, where the backend handles
NDJSON parsing, thinking detection, and marker handling internally.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from features.proactive_agent.repositories import ProactiveAgentRepository
from features.proactive_agent.schemas import (
    AgentNotificationRequest,
    SendMessageRequest,
)
from features.proactive_agent.services.message_handler import MessageHandler
from features.proactive_agent.services.session_handler import SessionHandler
from infrastructure.aws.queue import SqsQueueService


class ProactiveAgentService:
    """Facade service for managing proactive agent interactions.

    Delegates to specialized handlers for different concerns:
    - MessageHandler: Message sending and receiving
    - SessionHandler: Session and message retrieval

    Note: Chart and research handlers are used internally by the WebSocket
    poller stream handler (event_emitter.py), not via this service.
    """

    def __init__(
        self,
        repository: ProactiveAgentRepository,
        queue_service: Optional[SqsQueueService] = None,
    ) -> None:
        self._repository = repository

        # Initialize handlers
        self._message_handler = MessageHandler(repository, queue_service)
        self._session_handler = SessionHandler(repository)

    # Message operations (delegated to MessageHandler)

    async def send_message(
        self,
        user_id: int,
        request: SendMessageRequest,
    ) -> dict[str, Any]:
        """Send a message from user to the proactive agent."""
        return await self._message_handler.send_message(user_id, request)

    async def receive_agent_notification(
        self,
        request: AgentNotificationRequest,
    ) -> dict[str, Any]:
        """Receive a notification/message from the agent (server-to-server).

        Used by heartbeat script to send observations.
        """
        return await self._message_handler.receive_agent_notification(request)

    # Session operations (delegated to SessionHandler)

    async def get_messages(
        self,
        session_id: str,
        user_id: int,
        since: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Get messages for a session."""
        return await self._session_handler.get_messages(
            session_id, user_id, since, limit, offset
        )

    async def get_new_messages(
        self,
        session_id: str,
        user_id: int,
        since: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Get new agent messages since a timestamp (for polling)."""
        return await self._session_handler.get_new_messages(session_id, user_id, since)

    async def get_session(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        ai_character_name: str = "sherlock",
    ) -> dict[str, Any]:
        """Get or create a session for a user."""
        return await self._session_handler.get_session(
            user_id, session_id, ai_character_name
        )


__all__ = ["ProactiveAgentService"]
