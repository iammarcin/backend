"""Frame handling for OpenClaw WebSocket protocol.

This module handles parsing and dispatching of WebSocket frames:
- Response frames (resolving pending requests)
- Event frames (challenge, tick, chat, etc.)
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class FrameHandler:
    """Handles WebSocket frame parsing and dispatching.

    This class processes incoming frames from the OpenClaw Gateway and
    routes them to appropriate handlers based on frame type.

    Frame types:
    - "res": Response to pending request
    - "event": Event (connect.challenge, chat, tick, etc.)
    """

    def __init__(
        self,
        pending_requests: dict[str, asyncio.Future[dict[str, Any]]],
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
    ):
        """Initialize frame handler.

        Args:
            pending_requests: Dict mapping request IDs to futures
            on_event: Callback for dispatching events
        """
        self._pending_requests = pending_requests
        self._on_event = on_event
        self._challenge_nonce: Optional[str] = None
        self._challenge_received: Optional[asyncio.Event] = None
        self._last_tick: float = 0.0

    @property
    def challenge_nonce(self) -> Optional[str]:
        """Return the challenge nonce received from gateway."""
        return self._challenge_nonce

    @property
    def last_tick(self) -> float:
        """Return timestamp of last tick event."""
        return self._last_tick

    def set_challenge_event(self, event: asyncio.Event) -> None:
        """Set the challenge received event.

        Args:
            event: Event to signal when challenge is received
        """
        self._challenge_received = event

    def reset_challenge(self) -> None:
        """Reset challenge state."""
        self._challenge_nonce = None
        self._challenge_received = None

    async def handle_frame(self, frame: dict[str, Any]) -> None:
        """Dispatch frame to appropriate handler.

        Args:
            frame: Parsed JSON frame from gateway
        """
        frame_type = frame.get("type")

        if frame_type == "res":
            self._handle_response(frame)
        elif frame_type == "event":
            await self._handle_event(frame)
        else:
            logger.warning(f"Unknown frame type: {frame_type}")

    def _handle_response(self, frame: dict[str, Any]) -> None:
        """Handle response frame by resolving pending request.

        Args:
            frame: Response frame with id, ok, payload/error
        """
        request_id = frame.get("id")

        if request_id and request_id in self._pending_requests:
            future = self._pending_requests[request_id]
            if not future.done():
                future.set_result(frame)
        else:
            logger.warning(f"Response for unknown request: {request_id}")

    async def _handle_event(self, frame: dict[str, Any]) -> None:
        """Handle event frame.

        Args:
            frame: Event frame with event name and payload
        """
        event_name = frame.get("event")
        payload = frame.get("payload", {})

        if event_name == "connect.challenge":
            self._challenge_nonce = payload.get("nonce")
            if self._challenge_received:
                self._challenge_received.set()
            logger.debug("Received connect.challenge event")

        elif event_name == "tick":
            self._last_tick = asyncio.get_event_loop().time()

        else:
            # Dispatch to callback (chat events, etc.)
            if event_name != "health" and event_name != "agent" and event_name != "chat":
                logger.debug(f"Dispatching event: {event_name}")
            try:
                await self._on_event(frame)
            except Exception:
                logger.exception(f"Error in event callback for {event_name}")
