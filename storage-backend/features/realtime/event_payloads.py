from __future__ import annotations

import logging
from typing import Mapping

from core.providers.realtime.base import RealtimeEvent, RealtimeEventType

from .errors import classify_error, is_expected_vad_error
from .schemas import RealtimeSessionSettings


logger = logging.getLogger(__name__)

SUPPRESSED_DEBUG_EVENTS = {
    "assistant.audio.delta",
    "response.output_audio.delta",
    "assistant.text.delta",
    "response.output_text.delta",
    "user.transcript.delta",
    "assistant.transcript.delta",
    "response.output_audio_transcript.delta",
    "audio_chunk",
}


def should_emit_ai_responding(
    *,
    event: RealtimeEvent,
    payload: Mapping[str, object],
    ai_response_started: bool,
) -> bool:
    if ai_response_started:
        return False

    payload_type = payload.get("type")
    if payload_type not in {"text_chunk", "audio"}:
        return False

    if event.type == RealtimeEventType.MESSAGE:
        event_name = str(event.payload.get("event") or "")
        if event_name not in {"assistant.text.delta", "assistant.transcript.delta"}:
            return False
        text_value = str(event.payload.get("text") or "").strip()
        return bool(text_value)

    if event.type == RealtimeEventType.AUDIO_CHUNK:
        audio_chunk = event.payload.get("audio")
        return isinstance(audio_chunk, str) and bool(audio_chunk)

    return False


def build_ai_responding_payload(
    *,
    session_id: str,
    turn_number: int,
    response_id: str | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_id": session_id,
        "type": "control",
        "payload": {
            "event": "turn.ai_responding",
            "turn_number": turn_number,
        },
    }

    if response_id:
        payload["payload"]["response_id"] = response_id

    return payload


def resolve_response_id(
    *,
    event: RealtimeEvent,
    payload: Mapping[str, object],
    fallback: str | None,
) -> str | None:
    candidate = payload.get("response_id")
    if isinstance(candidate, str) and candidate:
        return candidate

    candidate = event.payload.get("response_id")
    if isinstance(candidate, str) and candidate:
        return candidate

    return fallback


def build_websocket_payload(
    *,
    event: RealtimeEvent,
    session_id: str,
    settings: RealtimeSessionSettings | None = None,
) -> dict[str, object] | None:
    """Normalise provider events into websocket-friendly payloads."""

    base_payload: dict[str, object] = {"session_id": session_id}

    if event.type == RealtimeEventType.MESSAGE:
        event_name = str(event.payload.get("event") or "")
        text_value = str(event.payload.get("text") or "")
        response_id = event.payload.get("response_id")

        if event_name in {"assistant.text.delta", "assistant.transcript.delta"}:
            if not text_value:
                return None
            payload = {
                **base_payload,
                "type": "text_chunk",
                "content": text_value,
                "source": "transcript"
                if event_name == "assistant.transcript.delta"
                else "model",
            }
            if response_id:
                payload["response_id"] = response_id
            return payload

        if event_name in {"assistant.text.completed", "assistant.transcript.completed"}:
            payload = {
                **base_payload,
                "type": "text_completed",
                "source": "transcript"
                if event_name == "assistant.transcript.completed"
                else "model",
            }
            if response_id:
                payload["response_id"] = response_id
            return payload

        if event_name.startswith("user.transcript") or event_name.startswith(
            "conversation.item.input_audio_transcription"
        ):
            translation_enabled = bool(getattr(settings, "live_translation", False))
            is_completed = event_name.endswith("completed")

            if translation_enabled:
                if not is_completed and not text_value:
                    return None
                payload = {
                    **base_payload,
                    "type": "translation",
                    "status": "completed" if is_completed else "delta",
                }
                if is_completed or text_value:
                    payload["content"] = text_value
                item_id = event.payload.get("item_id")
                if item_id:
                    payload["item_id"] = item_id
                return payload

            if not is_completed:
                # Skip incremental transcript deltas; clients only need the final text.
                return None
            payload = {
                **base_payload,
                "type": "transcription",
                "status": "completed",
            }
            if text_value:
                payload["content"] = text_value
            item_id = event.payload.get("item_id")
            if item_id:
                payload["item_id"] = item_id
            return payload

    if event.type == RealtimeEventType.ERROR:
        message = str(event.payload.get("message") or "Unknown error")
        code = event.payload.get("code")
        classification = classify_error(code)
        vad_enabled = getattr(settings, "vad_enabled", True) if settings else True

        if is_expected_vad_error(code, vad_enabled):
            logger.info(
                "Expected empty buffer condition in VAD mode (code=%s, session=%s)",
                code,
                session_id,
            )
            return None

        log_level = getattr(
            logging, str(classification.log_level).upper(), logging.ERROR
        )
        logger.log(
            log_level,
            "Realtime provider reported error: %s (code=%s, severity=%s, session=%s)",
            message,
            code,
            classification.severity.value,
            session_id,
        )
        payload = {
            **base_payload,
            "type": "error",
            "message": message,
            "severity": classification.severity.value,
        }
        if code:
            payload["code"] = code
        return payload

    if event.type == RealtimeEventType.AUDIO_CHUNK:
        audio_chunk = event.payload.get("audio")
        audio_event = event.payload.get("event")
        response_id = event.payload.get("response_id")

        if isinstance(audio_chunk, str) and audio_chunk:
            payload = {
                **base_payload,
                "type": "audio_chunk",
                "content": audio_chunk,
            }
            if response_id:
                payload["response_id"] = response_id
            chunk_event_name = str(event.payload.get("event") or "audio_chunk")
            if chunk_event_name not in SUPPRESSED_DEBUG_EVENTS:
                logger.debug(
                    "Forwarding audio chunk to frontend (size=%d bytes)",
                    len(audio_chunk),
                    extra={"session_id": session_id, "response_id": response_id},
                )
            return payload

        if audio_event == "assistant.audio.completed":
            payload = {
                **base_payload,
                "type": "audio_chunk",
                "payload": {k: v for k, v in event.payload.items() if v is not None},
            }
            return payload

    payload = event.to_payload()
    payload["session_id"] = session_id
    return payload


__all__ = [
    "SUPPRESSED_DEBUG_EVENTS",
    "build_ai_responding_payload",
    "build_websocket_payload",
    "resolve_response_id",
    "should_emit_ai_responding",
]
