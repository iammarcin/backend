"""Helpers for emitting reasoning-related streaming events."""

from __future__ import annotations

from typing import Optional

from core.streaming.manager import StreamingManager


async def emit_reasoning_custom_event(
    manager: StreamingManager,
    *,
    reasoning_text: str,
    queue_type: str = "frontend_only",
    session_id: Optional[str] = None,
) -> None:
    """Emit a thinking_chunk event for frontend reasoning display.

    Sends 'thinking_chunk' type directly (not wrapped in custom_event)
    to match what the frontend event dispatcher expects.

    Frontend schema expects:
    {
        "type": "thinking_chunk",
        "data": {
            "content": str,
            "session_id": str
        }
    }
    """

    if not reasoning_text:
        return

    # Send thinking_chunk directly - frontend dispatcher handles this type
    payload = {
        "type": "thinking_chunk",
        "data": {
            "content": reasoning_text,
        },
    }
    # Session ID will be attached by send_to_frontend if available
    if session_id:
        payload["data"]["session_id"] = session_id

    await manager.send_to_queues(payload, queue_type=queue_type)
