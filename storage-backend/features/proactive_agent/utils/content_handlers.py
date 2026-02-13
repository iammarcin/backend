"""Content streaming handlers for proactive agent (text/thinking chunks)."""

from __future__ import annotations

from typing import Any, Optional

from core.connections import get_proactive_registry
from features.proactive_agent.streaming_registry import get_session


async def handle_text_chunk(
    session: Any,
    user_id: int,
    content: Optional[str],
    ai_character_name: str,
) -> bool:
    """Handle text_chunk event - push text chunk for real-time display.

    Returns True if WebSocket push succeeded.
    """
    registry = get_proactive_registry()

    pushed = await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "text_chunk",
            "data": {
                "session_id": session.session_id,
                "content": content,
                "ai_character_name": ai_character_name,
            },
        },
    )

    streaming_session = get_session(session.session_id, user_id)
    if streaming_session and content:
        await streaming_session.manager.send_to_queues(
            {
                "type": "text_chunk",
                "content": content,
            }
        )

    return pushed


async def handle_thinking_chunk(
    session: Any,
    user_id: int,
    content: Optional[str],
    ai_character_name: str,
) -> bool:
    """Handle thinking_chunk event - push thinking for real-time display.

    Returns True if WebSocket push succeeded.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        "[DEBUG] handle_thinking_chunk called: session=%s content_len=%d",
        session.session_id,
        len(content) if content else 0,
    )

    registry = get_proactive_registry()

    result = await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "thinking_chunk",
            "data": {
                "session_id": session.session_id,
                "content": content,
                "ai_character_name": ai_character_name,
            },
        },
    )
    logger.info("[DEBUG] thinking_chunk pushed: result=%s", result)
    return result


__all__ = ["handle_text_chunk", "handle_thinking_chunk"]
