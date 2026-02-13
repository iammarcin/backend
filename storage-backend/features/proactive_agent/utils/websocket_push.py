"""WebSocket push helpers for proactive agent notifications."""

from __future__ import annotations

import logging
from typing import Any

from core.connections import get_proactive_registry

logger = logging.getLogger(__name__)


async def try_websocket_push(
    user_id: int,
    message: Any,
    message_to_dict_func: Any,
    include_reasoning: bool = False,
    session_scoped: bool = True,
) -> bool:
    """Attempt to push message via WebSocket if user is connected.

    Args:
        user_id: Target user ID
        message: Database message object to push
        message_to_dict_func: Function to convert message to dict
        include_reasoning: Whether to include ai_reasoning in the push.
            Defaults to False since reasoning is typically sent via streaming chunks.
        session_scoped: If True (default), only push to connections matching
            the message's session_id. If False, push to ALL user connections
            regardless of session (used for cross-session notifications).

    Returns:
        True if push succeeded, False otherwise.
    """
    try:
        registry = get_proactive_registry()
        message_dict = message_to_dict_func(message, include_reasoning=include_reasoning)

        pushed = await registry.push_to_user(
            user_id=user_id,
            message={
                "type": "notification",
                "data": message_dict,
            },
            session_scoped=session_scoped,
        )

        if pushed:
            logger.info(
                "Pushed notification via WebSocket to user %s",
                user_id,
            )
        else:
            logger.debug(
                "User %s not connected via WebSocket, message saved to DB",
                user_id,
            )

        return pushed

    except Exception as exc:
        logger.warning(
            "WebSocket push failed for user %s: %s (message saved to DB)",
            user_id,
            exc,
        )
        return False


async def try_websocket_push_thinking(
    user_id: int,
    session_id: str,
    thinking: str,
    ai_character_name: str,
) -> bool:
    """Push thinking content via WebSocket if user is connected.

    Args:
        user_id: Target user ID
        session_id: Session ID
        thinking: Thinking content to push
        ai_character_name: Character name (sherlock/bugsy)

    Returns:
        True if push succeeded, False otherwise.
    """
    try:
        registry = get_proactive_registry()

        pushed = await registry.push_to_user(
            user_id=user_id,
            message={
                "type": "thinking",
                "data": {
                    "session_id": session_id,
                    "thinking": thinking,
                    "ai_character_name": ai_character_name,
                },
            },
        )

        if pushed:
            logger.info(
                "Pushed thinking via WebSocket to user %s",
                user_id,
            )
        else:
            logger.debug(
                "User %s not connected via WebSocket, thinking not delivered",
                user_id,
            )

        return pushed

    except Exception as exc:
        logger.warning(
            "WebSocket thinking push failed for user %s: %s",
            user_id,
            exc,
        )
        return False


__all__ = ["try_websocket_push", "try_websocket_push_thinking"]
