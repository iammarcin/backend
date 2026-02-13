"""Message handling for proactive agent - send and receive messages."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from core.exceptions import NotFoundError, ServiceError
from features.proactive_agent.repositories import ProactiveAgentRepository
from features.proactive_agent.schemas import (
    AgentNotificationRequest,
    SendMessageRequest,
)
from features.proactive_agent.utils import (
    extract_thinking_tags,
    strip_thinking_tags,
    try_websocket_push,
)
from infrastructure.aws.queue import SqsQueueService

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handles sending and receiving messages for proactive agent."""

    def __init__(
        self,
        repository: ProactiveAgentRepository,
        queue_service: Optional[SqsQueueService] = None,
    ) -> None:
        self._repository = repository
        self._queue_service = queue_service

    async def send_message(
        self,
        user_id: int,
        request: SendMessageRequest,
    ) -> dict[str, Any]:
        """Send a message from user to the proactive agent."""
        ai_character_name = request.ai_character_name

        session = await self._repository.get_or_create_session(
            user_id=user_id,
            session_id=request.session_id,
            ai_character_name=ai_character_name,
        )
        await self._rotate_claude_session_if_needed(session)

        image_locations, file_locations = self._extract_attachment_urls(request)

        message = await self._repository.create_message(
            session_id=session.session_id,
            customer_id=session.customer_id,
            direction="user_to_agent",
            content=request.content,
            source=request.source.value,
            ai_character_name=ai_character_name,
            image_locations=image_locations if image_locations else None,
            file_locations=file_locations if file_locations else None,
        )

        await try_websocket_push(
            user_id=user_id,
            message=message,
            message_to_dict_func=self._repository.message_to_dict,
        )

        result = {
            "queue_message_id": None,
            "session_id": session.session_id,
            "queued": False,
            "message_id": message.message_id,
        }

        if self._queue_service:
            result = await self._queue_message(
                result, session, request, user_id, ai_character_name
            )

        return result

    async def receive_agent_notification(
        self,
        request: AgentNotificationRequest,
    ) -> dict[str, Any]:
        """Receive a notification/message from the agent (server-to-server).

        Used by heartbeat script to send observations.
        """
        session = await self._repository.get_session_by_id(request.session_id)
        if not session:
            raise NotFoundError(f"Session {request.session_id} not found")

        ai_reasoning = extract_thinking_tags(request.content)
        clean_content = strip_thinking_tags(request.content)
        message = await self._repository.create_message(
            session_id=session.session_id,
            customer_id=session.customer_id,
            direction=request.direction.value,
            content=clean_content,
            source=request.source.value,
            is_heartbeat_ok=request.is_heartbeat_ok,
            ai_character_name=request.ai_character_name,
            ai_reasoning=ai_reasoning,
        )

        logger.info(
            "Proactive agent notification received",
            extra={
                "session_id": session.session_id,
                "user_id": request.user_id,
                "direction": request.direction.value,
                "is_heartbeat_ok": request.is_heartbeat_ok,
                "ai_character_name": request.ai_character_name,
            },
        )

        pushed_via_ws = False
        if not request.is_heartbeat_ok:
            # For non-streaming notifications, include reasoning since no streaming chunks were sent
            pushed_via_ws = await try_websocket_push(
                user_id=request.user_id,
                message=message,
                message_to_dict_func=self._repository.message_to_dict,
                include_reasoning=True,
            )

        return {
            "message_id": message.message_id,
            "session_id": session.session_id,
            "stored": True,
            "pushed_via_ws": pushed_via_ws,
        }

    async def _rotate_claude_session_if_needed(self, session: Any) -> None:
        """Rotate Claude session ID if older than 7 days."""
        if not session.claude_session_id:
            return
        last_update = getattr(session, "last_update", None)
        if not last_update:
            return
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=UTC)
        if datetime.now(UTC) - last_update <= timedelta(days=7):
            return

        await self._repository.update_session_claude_id(
            session_id=session.session_id,
            claude_session_id=None,
        )
        session.claude_session_id = None

    def _extract_attachment_urls(
        self, request: SendMessageRequest
    ) -> tuple[list[str], list[str]]:
        """Extract image and file URLs from attachments."""
        image_locations: list[str] = []
        file_locations: list[str] = []
        if request.attachments:
            for att in request.attachments:
                att_type = att.type.value if hasattr(att.type, "value") else att.type
                if att_type == "image":
                    image_locations.append(att.url)
                else:
                    file_locations.append(att.url)
        return image_locations, file_locations

    async def _queue_message(
        self,
        result: dict[str, Any],
        session: Any,
        request: SendMessageRequest,
        user_id: int,
        ai_character_name: str,
    ) -> dict[str, Any]:
        """Queue message to SQS for processing."""
        try:
            attachments_for_sqs = None
            if request.attachments:
                attachments_for_sqs = [
                    {
                        "type": att.type.value if hasattr(att.type, "value") else att.type,
                        "url": att.url,
                        "filename": att.filename,
                        "mime_type": att.mime_type,
                    }
                    for att in request.attachments
                ]

            queue_result = await self._queue_service.enqueue_timestamped_payload(
                {
                    "type": "user_message",
                    "user_id": user_id,
                    "session_id": session.session_id,
                    "content": request.content,
                    "source": request.source.value,
                    "claude_session_id": session.claude_session_id,
                    "ai_character_name": ai_character_name,
                    "text_model": request.text_model,  # LLM model for Claude Code
                    "tts_settings": request.tts_settings,
                    "attachments": attachments_for_sqs,
                },
                message_group_id=session.session_id,  # FIFO ordering per session
            )
            result["queue_message_id"] = queue_result.message_id
            result["queued"] = True
            logger.info(
                "Proactive agent message queued",
                extra={
                    "session_id": session.session_id,
                    "user_id": user_id,
                    "queue_message_id": queue_result.message_id,
                    "ai_character_name": ai_character_name,
                },
            )
        except ServiceError as exc:
            logger.warning(
                "Failed to queue proactive agent message",
                extra={"session_id": session.session_id, "error": str(exc)},
            )

        return result


__all__ = ["MessageHandler"]
