"""OpenClaw message router.

Routes messages to OpenClaw Gateway and maps streaming responses back to
the mobile WebSocket event format. Integrates with TTS for parallel audio.

Usage:
    await send_message_to_openclaw(
        user_id=1,
        session_id="session-123",
        message="Hello",
        ai_character_name="sherlock",
        tts_settings={"tts_auto_execute": True, "voice": "alloy"},
    )
"""

import logging
from typing import Any, Optional

from core.connections import get_proactive_registry

from .config import is_openclaw_enabled
from .exceptions import OpenClawError, RequestError
from .session import get_openclaw_session_manager
from features.proactive_agent.poller_stream.marker_detector import MarkerDetector

from .stream_callbacks import StreamCallbacks, _is_tts_enabled

logger = logging.getLogger(__name__)


async def send_message_to_openclaw(
    *,
    user_id: int,
    session_id: str,
    message: str,
    ai_character_name: str = "sherlock",
    tts_settings: Optional[dict[str, Any]] = None,
    attachments: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Send a message to OpenClaw Gateway and stream response to mobile.

    This function:
    1. Gets the shared OpenClaw connection
    2. Sends chat.send request
    3. Maps streaming events to mobile WebSocket format
    4. Pushes events to registered mobile connections
    5. Integrates with TTS for parallel audio generation (when tts_auto_execute=True)

    Args:
        user_id: User ID
        session_id: Session ID for the chat
        message: Message text to send
        ai_character_name: Character name (for logging)
        tts_settings: TTS settings (tts_auto_execute, voice, model, etc.)
        attachments: Message attachments (images, files)

    Returns:
        Dict with run_id and status

    Raises:
        OpenClawError: If connection or send fails
    """
    if not is_openclaw_enabled():
        raise OpenClawError("OpenClaw is not enabled")

    logger.info(
        "Routing message to OpenClaw: user=%s, session=%s, character=%s, tts=%s",
        user_id,
        session_id[:8] if session_id else "none",
        ai_character_name,
        _is_tts_enabled(tts_settings),
    )

    # Get shared session manager and adapter
    session_manager = await get_openclaw_session_manager()
    adapter = await session_manager.get_adapter()

    # Build session key for OpenClaw
    session_key = f"agent:{ai_character_name}:{session_id}"

    # Get proactive registry for pushing events to mobile
    registry = get_proactive_registry()

    # Create callbacks handler
    callbacks = StreamCallbacks(
        user_id=user_id,
        session_id=session_id,
        ai_character_name=ai_character_name,
        tts_settings=tts_settings,
        registry=registry,
        marker_detector=MarkerDetector(),
    )

    try:
        run_id = await adapter.send_message(
            user_id=user_id,
            session_id=session_id,
            session_key=session_key,
            message=message,
            on_stream_start=callbacks.on_stream_start,
            on_text_chunk=callbacks.on_text_chunk,
            on_stream_end=callbacks.on_stream_end,
            on_error=callbacks.on_error,
            on_tool_start=callbacks.on_tool_start,
            on_tool_result=callbacks.on_tool_result,
            on_thinking_chunk=callbacks.on_thinking_chunk,
            attachments=attachments,
        )

        return {
            "run_id": run_id,
            "status": "streaming",
            "session_id": session_id,
        }

    except RequestError as e:
        logger.error(
            "OpenClaw request failed: user=%s, code=%s, message=%s",
            user_id,
            e.code,
            e.message,
        )
        await callbacks.on_error(f"Request failed: {e.message}")
        raise

    except Exception as e:
        logger.error("OpenClaw send failed: user=%s, error=%s", user_id, e)
        await callbacks.on_error(str(e))
        raise OpenClawError(f"Failed to send message: {e}") from e


async def abort_openclaw_stream(run_id: str) -> bool:
    """Abort an active OpenClaw stream.

    Args:
        run_id: Run ID to abort

    Returns:
        True if abort was successful
    """
    if not is_openclaw_enabled():
        return False

    try:
        manager = await get_openclaw_session_manager()
        adapter = await manager.get_adapter()
        return await adapter.abort(run_id)
    except Exception as e:
        logger.error("Failed to abort OpenClaw stream: %s", e)
        return False


async def abort_openclaw_stream_by_session(session_id: str) -> bool:
    """Abort an active OpenClaw stream for a given session.

    Args:
        session_id: Session ID to look up and abort

    Returns:
        True if abort was successful, False if not found or failed
    """
    if not is_openclaw_enabled():
        return False

    try:
        manager = await get_openclaw_session_manager()
        adapter = await manager.get_adapter()
        run_id = adapter.get_run_id_for_session(session_id)
        if not run_id:
            logger.debug("No active OpenClaw stream for session: %s", session_id[:8] if session_id else "none")
            return False
        return await adapter.abort(run_id)
    except Exception as e:
        logger.error("Failed to abort OpenClaw stream for session %s: %s", session_id[:8] if session_id else "none", e)
        return False


