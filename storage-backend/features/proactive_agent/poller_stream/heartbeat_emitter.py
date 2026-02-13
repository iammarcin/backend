"""Heartbeat-specific emitter for poller stream.

Handles heartbeat NDJSON streaming with silent accumulation (no frontend push).
Checks HEARTBEAT_OK on clean text to avoid false positives from thinking tags.
"""

import logging
import re
from typing import Optional

from .ndjson_parser import EventType, ParsedEvent
from .schemas import InitMessage

from ..repositories import ProactiveAgentRepository
from ..schemas import AgentNotificationRequest, MessageDirection, MessageSource
from ..services.message_handler import MessageHandler
from ..utils import extract_thinking_tags, strip_thinking_tags

logger = logging.getLogger(__name__)


class HeartbeatEmitter:
    """Emitter for heartbeat mode - accumulates silently, checks HEARTBEAT_OK.

    Unlike EventEmitter, this does NOT:
    - Stream chunks to frontends
    - Persist messages during stream
    - Handle TTS

    On finalize:
    1. Strips thinking tags to get clean_text
    2. Checks HEARTBEAT_OK regex on clean_text (NOT full text - avoids false positives)
    3. If OK: do nothing (no DB, no push)
    4. If not OK: call receive_agent_notification() with full_content
    """

    def __init__(
        self,
        init_data: InitMessage,
        repository: ProactiveAgentRepository,
    ) -> None:
        self.user_id = init_data.user_id
        self.session_id = init_data.session_id
        self.ai_character_name = init_data.ai_character_name

        self._repository = repository
        self._message_handler = MessageHandler(repository=repository)
        self._accumulated_text = ""
        self._error_emitted = False

    async def emit(self, event: ParsedEvent) -> None:
        """Accumulate text silently - no frontend push.

        We don't need to track tool events for heartbeat mode since
        heartbeat responses are simple observations, not agentic workflows.
        """
        if event.type == EventType.TEXT_CHUNK:
            content = event.data.get("content", "")
            self._accumulated_text += content
        # Log parse errors but don't fail the stream
        elif event.type == EventType.PARSE_ERROR:
            line = event.data.get("line", "")[:100]
            logger.warning(
                "Heartbeat unparseable NDJSON: %s",
                line,
                extra={"session_id": self.session_id},
            )

    async def finalize(self, full_content: str) -> None:
        """Finalize heartbeat stream - check HEARTBEAT_OK and optionally notify.

        Args:
            full_content: Full accumulated text including thinking tags.
        """
        # Strip thinking tags FIRST, then check HEARTBEAT_OK on clean text
        # This prevents false positives from thinking like:
        # "<thinking>HEARTBEAT_OK - all quiet</thinking> Actually, I found an issue..."
        clean_text = strip_thinking_tags(full_content)

        if self._is_heartbeat_ok(clean_text):
            logger.info(
                "HEARTBEAT_OK - no notification needed",
                extra={
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "clean_text_len": len(clean_text),
                },
            )
            return

        # Observation found - send notification via existing handler
        # Pass full_content so MessageHandler can extract reasoning from thinking tags
        logger.info(
            "Heartbeat observation detected",
            extra={
                "session_id": self.session_id,
                "user_id": self.user_id,
                "clean_text_len": len(clean_text),
                "preview": clean_text[:100],
            },
        )
        await self._send_notification(full_content)

    async def emit_error(self, code: str, message: str) -> None:
        """Log error - no persistence in heartbeat mode.

        Heartbeat errors are transient and don't need DB records.
        The next heartbeat cycle will try again.
        """
        if self._error_emitted:
            return
        self._error_emitted = True

        logger.error(
            "Heartbeat stream error",
            extra={
                "session_id": self.session_id,
                "user_id": self.user_id,
                "error_code": code,
                "error_message": message[:200],
            },
        )

    def _is_heartbeat_ok(self, clean_text: str) -> bool:
        """Check if clean text indicates HEARTBEAT_OK (case-insensitive)."""
        return re.search(r"HEARTBEAT_OK", clean_text, re.IGNORECASE) is not None

    async def _send_notification(self, full_content: str) -> None:
        """Send notification via existing MessageHandler.receive_agent_notification."""
        request = AgentNotificationRequest(
            user_id=self.user_id,
            session_id=self.session_id,
            content=full_content,  # Full content - handler extracts reasoning
            direction=MessageDirection.HEARTBEAT,
            source=MessageSource.HEARTBEAT,
            is_heartbeat_ok=False,  # We only call this when NOT ok
            ai_character_name=self.ai_character_name,
        )

        try:
            result = await self._message_handler.receive_agent_notification(request)
            logger.info(
                "Heartbeat notification sent",
                extra={
                    "session_id": self.session_id,
                    "message_id": result.get("message_id"),
                    "pushed_via_ws": result.get("pushed_via_ws"),
                },
            )
        except Exception:
            logger.exception(
                "Failed to send heartbeat notification",
                extra={"session_id": self.session_id},
            )


__all__ = ["HeartbeatEmitter"]
