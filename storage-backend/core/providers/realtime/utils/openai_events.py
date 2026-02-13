"""Event translation helpers for the OpenAI realtime provider.

`OpenAIRealtimeEventTranslator` converts raw websocket payloads from OpenAI into
:class:`~core.providers.realtime.base.RealtimeEvent` instances consumed by the
rest of the application.  Housing the translation logic here keeps
``openai.py`` focused on transport orchestration while still providing a single
place to evolve the mapping rules.

Event-specific handlers are delegated to :mod:`event_handlers`, while payload
extraction utilities live in :mod:`event_extractors`.
"""

from __future__ import annotations

import logging
from typing import Iterable, Mapping

from ..base import RealtimeEvent
from . import event_handlers
from .event_extractors import extract_response_id

logger = logging.getLogger(__name__)


class OpenAIRealtimeEventTranslator:
    """Translate raw OpenAI realtime events into internal dataclasses."""

    _EVENT_HANDLER_MAP = {
        "response.created": event_handlers.handle_response_created,
        "response.output_text.delta": event_handlers.handle_text_delta,
        "response.output_text.done": event_handlers.handle_text_done,
        "response.output_audio.delta": event_handlers.handle_audio_delta,
        "response.output_audio.done": event_handlers.handle_audio_done,
        "response.audio_transcript.delta": event_handlers.handle_transcript_delta,
        "response.output_audio_transcript.delta": event_handlers.handle_transcript_delta,
        "response.audio_transcript.done": event_handlers.handle_transcript_done,
        "response.output_audio_transcript.done": event_handlers.handle_transcript_done,
        "conversation.item.input_audio_transcription.delta": (
            event_handlers.handle_user_transcript_delta
        ),
        "conversation.item.input_audio_transcription.completed": (
            event_handlers.handle_user_transcript_completed
        ),
        "response.completed": event_handlers.handle_response_completed,
        "response.done": event_handlers.handle_response_completed,
        "error": event_handlers.handle_error,
        "rate_limits.updated": event_handlers.handle_rate_limits,
    }

    def __init__(self) -> None:
        self._current_response_id: str | None = None

    @property
    def current_response_id(self) -> str | None:
        """Return the last seen response id, if any."""
        return self._current_response_id

    def translate(self, event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
        """Translate a raw OpenAI payload into zero or more realtime events."""
        event_type = str(event.get("type", "")).strip()
        if not event_type:
            return []

        if event_type.startswith("session."):
            return event_handlers.handle_session_event(event_type, event)

        handler = self._EVENT_HANDLER_MAP.get(event_type)
        if handler:
            result = handler(event)
            # Track response_id from events that contain it
            response_id = extract_response_id(event)
            if response_id:
                self._current_response_id = response_id
            return result

        logger.debug(
            "Ignoring realtime event %s",
            event_type,
            extra={"event_type": event_type},
        )
        return []


__all__ = ["OpenAIRealtimeEventTranslator"]
