"""TTS session management utilities for proactive agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from core.streaming.manager import StreamingManager
from config.tts.providers import openai as openai_config
from features.chat.services.streaming.tts_orchestrator import TTSOrchestrator
from features.proactive_agent.streaming_registry import (
    ProactiveStreamingSession,
    create_forwarder_task,
    get_session,
    register_session,
    remove_session,
)
from features.tts.service import TTSService

logger = logging.getLogger(__name__)


async def start_tts_session(
    session_id: str,
    user_id: int,
    tts_settings: Dict[str, Any],
    tts_service: TTSService,
) -> None:
    """Initialize TTS streaming session with orchestrator.

    Args:
        session_id: Proactive agent session ID
        user_id: User ID for the session
        tts_settings: TTS configuration from request
        tts_service: TTS service instance
    """
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(queue)

    provider = tts_settings.get("provider")
    voice = tts_settings.get("voice", "alloy")
    if provider == "openai" and voice not in openai_config.AVAILABLE_VOICES:
        logger.warning(
            "OpenAI TTS voice '%s' is invalid; falling back to '%s'",
            voice,
            openai_config.DEFAULT_VOICE,
        )
        voice = openai_config.DEFAULT_VOICE

    settings = {
        "tts": {
            "voice": voice,
            "model": tts_settings.get("model", "tts-1"),
            "tts_auto_execute": True,
            "streaming": True,
        },
        "general": {
            "tts_auto_execute": True,
        },
    }
    if provider:
        settings["tts"]["provider"] = provider

    orchestrator = TTSOrchestrator(
        manager=manager,
        tts_service=tts_service,
        settings=settings,
        customer_id=user_id,
        timings={},
    )

    forwarder_task = await create_forwarder_task(queue, user_id, session_id)

    await orchestrator.start_tts_streaming()

    streaming_session = ProactiveStreamingSession(
        session_id=session_id,
        manager=manager,
        queue=queue,
        orchestrator=orchestrator,
        forwarder_task=forwarder_task,
        user_id=user_id,
        tts_settings=tts_settings,
    )
    register_session(session_id, user_id, streaming_session)

    logger.info(
        "Started TTS session for session_id=%s user_id=%s",
        session_id,
        user_id,
    )


async def complete_tts_session(
    session_id: str,
    user_id: int,
    message: Any,
    update_audio_url_func: Any,
) -> Optional[str]:
    """Complete TTS streaming and update message with audio URL.

    Args:
        session_id: Proactive agent session ID
        user_id: User ID for the session
        message: Database message object (or None)
        update_audio_url_func: Async function to update message audio URL

    Returns:
        Audio file URL if TTS completed successfully, None otherwise.
    """
    streaming_session = remove_session(session_id, user_id)
    if not streaming_session:
        logger.debug(
            "No TTS session found for session_id=%s user_id=%s",
            session_id,
            user_id,
        )
        return None

    audio_file_url = None

    try:
        # Wait for TTS to complete BEFORE stopping the forwarder
        # The forwarder needs to stay alive to forward audio events to the client
        try:
            metadata = await asyncio.wait_for(
                streaming_session.orchestrator.wait_for_completion(),
                timeout=360.0,
            )
            if metadata and metadata.get("audio_file_url"):
                audio_file_url = metadata["audio_file_url"]

                if message and audio_file_url:
                    await update_audio_url_func(
                        message_id=message.message_id,
                        audio_file_url=audio_file_url,
                    )
                    logger.info(
                        "Updated message %s with audio URL",
                        message.message_id,
                    )

        except asyncio.TimeoutError:
            logger.warning(
                "TTS completion timeout for session %s, continuing without audio",
                session_id,
            )

    except Exception as exc:
        logger.error(
            "Error completing TTS session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )

    finally:
        # Send sentinel to forwarder queue AFTER TTS is complete
        # This ensures all audio events have been forwarded to the client
        await streaming_session.queue.put(None)
        if streaming_session.forwarder_task:
            streaming_session.forwarder_task.cancel()
            try:
                await streaming_session.forwarder_task
            except asyncio.CancelledError:
                pass

    return audio_file_url


async def cancel_tts_session(session_id: str, user_id: int) -> None:
    """Cancel TTS streaming session without waiting for completion."""
    streaming_session = remove_session(session_id, user_id)
    if not streaming_session:
        logger.debug(
            "No TTS session to cancel for session_id=%s user_id=%s",
            session_id,
            user_id,
        )
        return

    try:
        await streaming_session.orchestrator.cleanup()
    except Exception as exc:
        logger.warning(
            "Error cancelling TTS session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
    finally:
        await streaming_session.queue.put(None)
        if streaming_session.forwarder_task:
            streaming_session.forwarder_task.cancel()
            try:
                await streaming_session.forwarder_task
            except asyncio.CancelledError:
                pass


__all__ = ["start_tts_session", "complete_tts_session", "cancel_tts_session"]
