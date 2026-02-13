"""Process-wide registry for proactive TTS streaming sessions.

This module maintains state across HTTP request boundaries. ProactiveAgentService
is instantiated per-request, but TTS orchestration spans stream_start -> text_chunk -> stream_end.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from core.connections import get_proactive_registry

if TYPE_CHECKING:
    from core.streaming.manager import StreamingManager
    from features.chat.services.streaming.tts_orchestrator import TTSOrchestrator

logger = logging.getLogger(__name__)


@dataclass
class ProactiveStreamingSession:
    """Active TTS streaming session for a proactive agent response."""

    session_id: str
    manager: "StreamingManager"
    queue: asyncio.Queue
    orchestrator: "TTSOrchestrator"
    forwarder_task: asyncio.Task
    user_id: int
    tts_settings: Optional[Dict[str, Any]]


# Module-level registry - survives across request instances
_sessions: Dict[Tuple[str, int], ProactiveStreamingSession] = {}


def register_session(
    session_id: str,
    user_id: int,
    session: ProactiveStreamingSession,
) -> None:
    """Register a new TTS streaming session."""
    key = (session_id, user_id)
    if key in _sessions:
        logger.warning(
            "Overwriting existing session %s for user %s",
            session_id,
            user_id,
        )
    _sessions[key] = session
    logger.debug(
        "Registered TTS session for session_id=%s user_id=%s",
        session_id,
        user_id,
    )


def get_session(
    session_id: str,
    user_id: int,
) -> Optional[ProactiveStreamingSession]:
    """Get an active TTS streaming session."""
    return _sessions.get((session_id, user_id))


def remove_session(session_id: str, user_id: int) -> Optional[ProactiveStreamingSession]:
    """Remove and return a TTS streaming session.

    Returns the removed session for cleanup, or None if not found.
    """
    key = (session_id, user_id)
    session = _sessions.pop(key, None)
    if session:
        logger.debug(
            "Removed TTS session for session_id=%s user_id=%s",
            session_id,
            user_id,
        )
    return session


def get_active_session_count() -> int:
    """Get count of active TTS sessions (for monitoring)."""
    return len(_sessions)


# Event types to forward from StreamingManager to proactive WebSocket
TTS_EVENT_TYPES = frozenset(
    {
        "audio_chunk",
        "tts_started",
        "tts_generation_completed",
        "tts_completed",
        "tts_error",
        "tts_file_uploaded",
        "custom_event",
    }
)


async def create_forwarder_task(
    queue: asyncio.Queue,
    user_id: int,
    session_id: str,
) -> asyncio.Task:
    """Create a task that forwards TTS events from manager queue to proactive WebSocket.

    The forwarder:
    - Reads events from the StreamingManager queue
    - Filters to only TTS-related events (audio, ttsCompleted, etc.)
    - Pushes to ProactiveConnectionRegistry for WebSocket delivery
    - Ignores 'text' events (already pushed by proactive service directly)
    """
    registry = get_proactive_registry()

    async def forward_loop() -> None:
        try:
            while True:
                event = await queue.get()

                # None sentinel signals completion
                if event is None:
                    logger.debug("Forwarder received sentinel, stopping")
                    break

                event_type = event.get("type")

                # Only forward TTS-related events
                if event_type in TTS_EVENT_TYPES:
                    try:
                        if "session_id" not in event:
                            event = {**event, "session_id": session_id}
                        await registry.push_to_user(user_id, event)
                    except Exception as exc:
                        logger.warning(
                            "Failed to push TTS event %s to user %s: %s",
                            event_type,
                            user_id,
                            exc,
                        )

        except asyncio.CancelledError:
            logger.debug("Forwarder task cancelled")
            raise
        except Exception as exc:
            logger.error("Forwarder task error: %s", exc, exc_info=True)

    task = asyncio.create_task(forward_loop())
    return task
