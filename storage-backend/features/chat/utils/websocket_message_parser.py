"""WebSocket message parsing and validation.

Handles JSON decoding, disconnect detection, and error formatting for
WebSocket messages.
"""

import json
import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket
from contextlib import suppress

from core.observability.websocket_logging import log_websocket_error

logger = logging.getLogger(__name__)


async def parse_websocket_message(
    message: Dict[str, Any],
    websocket: WebSocket,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """Parse and validate a WebSocket message.

    Args:
        message: Raw message dict from websocket.receive()
        websocket: WebSocket connection for error responses
        session_id: Session ID for logging

    Returns:
        Parsed data dict, or None if message should be ignored

    Raises:
        WebSocketDisconnect: If disconnect/close frame detected (should be caught by caller)
    """
    # Handle disconnect
    if message.get("type") == "websocket.disconnect":
        logger.info(
            "Client disconnected from session %s",
            session_id,
        )
        return None

    # Handle close frame
    if message.get("type") == "websocket.close":
        logger.info(
            "WebSocket close frame received (session=%s, code=%s)",
            session_id,
            message.get("code"),
        )
        return None

    # Ignore non-text messages
    if "text" not in message:
        has_bytes = "bytes" in message and message["bytes"] is not None
        if not has_bytes:
            logger.debug(
                "Ignoring non-text WebSocket message (session=%s, type=%s, keys=%s)",
                session_id,
                message.get("type"),
                list(message.keys()),
            )
        return None

    # Parse JSON
    try:
        data = json.loads(message["text"])
    except json.JSONDecodeError as exc:
        logger.error(
            "Failed to decode JSON payload (session=%s): %s",
            session_id,
            exc,
        )
        log_websocket_error(
            websocket,
            error=exc,
            context=f"JSON decode (session={session_id})",
        )
        with suppress(Exception):
            await websocket.send_json(
                {
                    "type": "error",
                    "content": "Invalid payload",
                    "stage": "validation",
                    "session_id": session_id,
                }
            )
        return None

    return data


def is_disconnect_message(message: Dict[str, Any]) -> bool:
    """Check if message indicates disconnection."""
    msg_type = message.get("type", "")
    return msg_type in ("websocket.disconnect", "websocket.close")
