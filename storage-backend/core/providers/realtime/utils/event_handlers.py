"""Event handler implementations for OpenAI realtime events.

This module contains handler methods for translating specific OpenAI realtime
event types into internal RealtimeEvent instances. Each handler is responsible
for extracting relevant data and constructing the appropriate event payload.
"""

from __future__ import annotations

from typing import Iterable, Mapping, MutableMapping

from ..base import RealtimeEvent, RealtimeEventType
from .event_extractors import (
    extract_audio_delta,
    extract_item_id,
    extract_response_id,
    extract_text_delta,
)


def handle_session_event(
    event_type: str, event: Mapping[str, object]
) -> Iterable[RealtimeEvent]:
    """Handle session-related events."""
    payload = {"event": event_type, "payload": event.get("session") or event}
    return [RealtimeEvent(RealtimeEventType.SESSION, payload)]


def handle_response_created(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle response.created event."""
    response_id = extract_response_id(event)
    status = (event.get("response") or {}).get("status")
    payload = {
        "event": "response.created",
        "response_id": response_id,
        "status": status,
    }
    return [RealtimeEvent(RealtimeEventType.CONTROL, payload)]


def handle_text_delta(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle text delta event."""
    response_id = extract_response_id(event)
    text = extract_text_delta(event)
    if not text:
        return []

    payload = {
        "event": "assistant.text.delta",
        "response_id": response_id,
        "text": text,
    }
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_text_done(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle text completion event."""
    response_id = extract_response_id(event)
    payload = {
        "event": "assistant.text.completed",
        "response_id": response_id,
    }
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_audio_delta(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle audio delta event."""
    response_id = extract_response_id(event)
    chunk, audio_format = extract_audio_delta(event)
    if not chunk:
        return []

    payload = {
        "response_id": response_id,
        "audio": chunk,
        "format": audio_format or "pcm16",
    }
    return [RealtimeEvent(RealtimeEventType.AUDIO_CHUNK, payload)]


def handle_audio_done(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle audio completion event."""
    response_id = extract_response_id(event)
    payload = {
        "response_id": response_id,
        "event": "assistant.audio.completed",
    }
    return [RealtimeEvent(RealtimeEventType.AUDIO_CHUNK, payload)]


def handle_transcript_delta(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle transcript delta event."""
    response_id = extract_response_id(event)
    text = extract_text_delta(event)
    if not text:
        return []

    payload = {
        "event": "assistant.transcript.delta",
        "response_id": response_id,
        "text": text,
    }
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_transcript_done(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle transcript completion event."""
    response_id = extract_response_id(event)
    payload = {
        "event": "assistant.transcript.completed",
        "response_id": response_id,
    }
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_user_transcript_delta(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle user transcript delta event."""
    text = extract_text_delta(event)
    if not text:
        return []

    payload = {
        "event": "user.transcript.delta",
        "item_id": extract_item_id(event),
        "text": text,
    }
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_user_transcript_completed(
    event: Mapping[str, object]
) -> Iterable[RealtimeEvent]:
    """Handle user transcript completion event."""
    transcript = event.get("transcript")
    text = transcript.get("text") if isinstance(transcript, Mapping) else transcript
    payload: MutableMapping[str, object] = {
        "event": "user.transcript.completed",
        "item_id": extract_item_id(event),
    }
    if text:
        payload["text"] = str(text)
    return [RealtimeEvent(RealtimeEventType.MESSAGE, payload)]


def handle_response_completed(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle response completion event."""
    response = event.get("response") or {}
    response_id = response.get("id")
    status = response.get("status") or event.get("status") or "completed"
    payload = {
        "event": "turn.completed",
        "response_id": response_id,
        "status": status,
    }
    return [RealtimeEvent(RealtimeEventType.CONTROL, payload)]


def handle_error(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle error event."""
    error = event.get("error") or {}
    message = error.get("message") or event.get("message") or "Unknown error"
    payload = {
        "event": "provider.error",
        "message": message,
        "code": error.get("code"),
    }
    return [RealtimeEvent(RealtimeEventType.ERROR, payload)]


def handle_rate_limits(event: Mapping[str, object]) -> Iterable[RealtimeEvent]:
    """Handle rate limits update event."""
    payload = {
        "event": "rate_limits.updated",
        "limits": event.get("rate_limits"),
    }
    return [RealtimeEvent(RealtimeEventType.CONTROL, payload)]


__all__ = [
    "handle_session_event",
    "handle_response_created",
    "handle_text_delta",
    "handle_text_done",
    "handle_audio_delta",
    "handle_audio_done",
    "handle_transcript_delta",
    "handle_transcript_done",
    "handle_user_transcript_delta",
    "handle_user_transcript_completed",
    "handle_response_completed",
    "handle_error",
    "handle_rate_limits",
]
