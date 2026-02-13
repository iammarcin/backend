"""Sync handler for proactive WebSocket connections.

Handles client requests to fetch missed messages since a given timestamp.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def handle_sync_request(
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    message: Dict[str, Any],
) -> None:
    """Handle sync request - fetch and send missed messages.

    Client sends: {"type": "sync", "last_seen_at": "2025-12-11T10:00:00Z"}
    Server responds with missed messages since that timestamp.
    """
    from features.proactive_agent.dependencies import get_db_session_direct
    from features.proactive_agent.repositories import ProactiveAgentRepository

    last_seen_str = message.get("last_seen_at")
    if not last_seen_str:
        await websocket.send_json({
            "type": "sync_error",
            "error": "last_seen_at required",
        })
        return

    try:
        last_seen_at = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
    except ValueError:
        await websocket.send_json({
            "type": "sync_error",
            "error": "Invalid timestamp format",
        })
        return

    try:
        async with get_db_session_direct() as db:
            repository = ProactiveAgentRepository(db)
            messages = await repository.get_new_agent_messages(
                session_id=session_id,
                since=last_seen_at,
            )

            for msg in messages:
                await websocket.send_json({
                    "type": "notification",
                    "data": repository.message_to_dict(msg),
                })

            await websocket.send_json({
                "type": "sync_complete",
                "count": len(messages),
                "synced_at": datetime.utcnow().isoformat() + "Z",
            })

            logger.info(
                "Synced %d missed messages for user %s since %s",
                len(messages),
                user_id,
                last_seen_at,
            )

    except Exception as exc:
        logger.error("Sync failed for user %s: %s", user_id, exc)
        await websocket.send_json({
            "type": "sync_error",
            "error": "Failed to fetch messages",
        })
