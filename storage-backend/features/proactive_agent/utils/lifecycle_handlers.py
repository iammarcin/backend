"""Stream lifecycle handlers for proactive agent (start/end)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.connections import get_proactive_registry
from features.proactive_agent.chart_accumulator import get_and_clear_charts
from features.proactive_agent.streaming_registry import get_session
from features.proactive_agent.utils.thinking_tags import (
    extract_thinking_tags,
    strip_thinking_tags,
)

logger = logging.getLogger(__name__)


async def handle_stream_start(
    session: Any,
    user_id: int,
    ai_character_name: str,
    tts_settings: Optional[Dict[str, Any]],
    start_tts_func: Any,
) -> bool:
    """Handle stream_start event - initialize TTS if enabled.

    Returns True if WebSocket push succeeded.
    """
    registry = get_proactive_registry()

    connection_count = len(await registry.get_connections(user_id))
    if connection_count == 0:
        logger.warning(
            "No proactive WS connections for user %s at stream_start (session %s)",
            user_id,
            session.session_id,
        )
    else:
        logger.debug(
            "Proactive WS connections for user %s at stream_start: %d",
            user_id,
            connection_count,
        )

    tts_enabled = bool(
        tts_settings
        and isinstance(tts_settings, dict)
        and tts_settings.get("tts_auto_execute", False)
    )

    if tts_enabled:
        await start_tts_func(
            session_id=session.session_id,
            user_id=user_id,
            tts_settings=tts_settings,
        )

    pushed = await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "stream_start",
            "data": {
                "session_id": session.session_id,
                "ai_character_name": ai_character_name,
            },
        },
    )
    logger.debug(
        "Streaming started for user %s, session %s",
        user_id,
        session.session_id,
    )
    return pushed


async def handle_stream_end(
    session: Any,
    user_id: int,
    full_content: Optional[str],
    ai_character_name: str,
    create_message_func: Any,
    complete_tts_func: Any,
) -> tuple[bool, Optional[Any]]:
    """Handle stream_end event - save to DB and signal completion.

    Returns (pushed_via_ws, message).
    """
    registry = get_proactive_registry()
    message = None
    audio_file_url = None
    clean_content = None

    # Get any accumulated charts from this streaming session
    accumulated_charts = get_and_clear_charts(session.session_id)

    if full_content:
        ai_reasoning = extract_thinking_tags(full_content)
        clean_content = strip_thinking_tags(full_content)
        if clean_content:  # Only save if there's content after stripping
            message = await create_message_func(
                session_id=session.session_id,
                customer_id=session.customer_id,
                direction="agent_to_user",
                content=clean_content,
                source="text",
                ai_character_name=ai_character_name,
                ai_reasoning=ai_reasoning,
                chart_data=accumulated_charts if accumulated_charts else None,
            )
            logger.info(
                "Streaming complete, saved message %s for session %s (charts: %d)",
                message.message_id,
                session.session_id,
                len(accumulated_charts),
            )

    streaming_session = get_session(session.session_id, user_id)
    if streaming_session:
        audio_file_url = await complete_tts_func(
            session_id=session.session_id,
            user_id=user_id,
            message=message,
        )

    # Use session_scoped=False so stream_end reaches ALL user connections.
    # This enables cross-session notifications - user sees toast when AI responds
    # to a session they're not currently viewing. Kotlin already handles this:
    # SherlockNotificationService.kt shows notification for other-session messages.
    pushed = await registry.push_to_user(
        user_id=user_id,
        message={
            "type": "stream_end",
            "data": {
                "session_id": session.session_id,
                "message_id": message.message_id if message else None,
                "content": clean_content,  # Include for notification display
                "audio_file_url": audio_file_url,
                "ai_character_name": ai_character_name,
            },
        },
        session_scoped=False,
    )

    return pushed, message


__all__ = ["handle_stream_start", "handle_stream_end"]
