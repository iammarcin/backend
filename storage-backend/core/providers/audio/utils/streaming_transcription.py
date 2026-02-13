"""Transcription event handling for realtime audio streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

from websockets.asyncio.client import ClientConnection

from core.exceptions import ProviderError
from core.streaming.manager import StreamingManager

logger = logging.getLogger(__name__)


async def receive_transcription_events(
    ws_client: ClientConnection,
    manager: StreamingManager,
    *,
    mode: str,
    provider_name: str,
) -> str:
    """Receive transcription events from OpenAI Realtime API."""

    all_transcripts: list[str] = []
    current_segment_parts: list[str] = []
    segment_count = 0
    completed_count = 0

    try:
        async for message in ws_client:
            event = _safe_load(message)
            if event is None:
                continue

            event_type = event.get("type")
            logger.debug("Received OpenAI event: %s", event_type)

            if event_type == "session.created":
                session_id = event.get("session", {}).get("id")
                logger.info("Transcription session created: %s", session_id)
                continue

            if event_type == "error":
                handled, error_msg = _handle_error_event(event)
                if handled:
                    continue
                raise ProviderError(
                    f"OpenAI transcription error: {error_msg}",
                    provider=provider_name,
                )

            if event_type == "input_audio_buffer.speech_started":
                await _notify_vad(manager, mode, status="speech_started")
                continue

            if event_type == "input_audio_buffer.speech_stopped":
                await _notify_vad(manager, mode, status="speech_stopped")
                continue

            if event_type == "input_audio_buffer.committed":
                item_id = event.get("item_id")
                logger.debug("Audio buffer committed (item_id=%s)", item_id)
                continue

            if event_type == "conversation.item.input_audio_transcription.delta":
                delta_text = _extract_text(event.get("delta"))
                if not delta_text:
                    continue

                current_segment_parts.append(delta_text)
                segment_count += 1
                manager.collect_chunk(delta_text, "transcription")

                partial_text = _build_partial(all_transcripts, current_segment_parts)
                if mode == "non-realtime":
                    await manager.send_to_queues(
                        {
                            "type": "transcription",
                            "content": delta_text,
                            "partial": partial_text,
                        }
                    )

                logger.debug(
                    "Received transcription delta (segment=%s, chars=%s)",
                    segment_count,
                    len(delta_text),
                )
                continue

            if event_type == "conversation.item.input_audio_transcription.completed":
                transcript_text = _extract_text(event.get("transcript"))
                segment_transcript = transcript_text or "".join(current_segment_parts)

                completed_count += 1
                logger.info(
                    "Transcription segment completed (segment=%s, chars=%s)",
                    completed_count,
                    len(segment_transcript),
                )

                if segment_transcript:
                    all_transcripts.append(segment_transcript)
                    current_segment_parts = []

                if mode == "non-realtime" and completed_count > 1:
                    await manager.send_to_queues(
                        {
                            "type": "custom_event",
                            "event_type": "transcription_segment",
                            "content": {
                                "type": "transcription_segment",
                                "content": segment_transcript,
                                "segment_number": completed_count,
                            },
                        }
                    )

                logger.debug(
                    "Continuing to listen for more speech segments (completed=%s, accumulated_chars=%s)",
                    completed_count,
                    sum(len(t) for t in all_transcripts),
                )
                continue

            if event_type in _IGNORED_EVENTS:
                continue

            logger.debug("Unhandled OpenAI event type: %s", event_type)
    except asyncio.CancelledError:
        logger.info("Transcription receiving task cancelled after %s segments", completed_count)
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error receiving transcription: %s", exc, exc_info=True)
        raise

    final_transcript = " ".join(all_transcripts).strip()
    if not final_transcript and current_segment_parts:
        final_transcript = "".join(current_segment_parts).strip()

    if not final_transcript:
        logger.info("Transcription ended without receiving any text (possibly silence)")
        return ""

    logger.info(
        "Transcription finished (segments=%s, total_chars=%s)",
        completed_count,
        len(final_transcript),
    )

    if mode == "non-realtime":
        await manager.send_to_queues(
            {
                "type": "transcription_complete",
                "content": final_transcript,
                "total_segments": completed_count,
            }
        )

    return final_transcript


def _handle_error_event(event: Dict[str, Any]) -> tuple[bool, str]:
    error_info = event.get("error", {})
    error_msg = error_info.get("message", "Unknown error")
    error_code = error_info.get("code", "unknown")

    if error_code == "input_audio_buffer_commit_empty":
        logger.warning(
            "Empty buffer commit (expected with VAD): %s",
            error_msg,
        )
        return True, error_msg

    logger.error(
        "OpenAI transcription error (code=%s): %s",
        error_code,
        error_msg,
    )
    return False, error_msg


async def _notify_vad(manager: StreamingManager, mode: str, *, status: str) -> None:
    logger.debug("Speech detected by VAD" if status == "speech_started" else "Silence detected by VAD")
    if mode != "non-realtime":
        return
    await manager.send_to_queues(
        {
            "type": "custom_event",
            "event_type": "vad",
            "content": {"type": "vad", "status": status},
        }
    )


def _build_partial(all_transcripts: list[str], current_parts: list[str]) -> str:
    all_text = " ".join(all_transcripts)
    current_text = "".join(current_parts)
    return f"{all_text} {current_text}".strip()


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        for key in ("text", "transcript", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate

    return ""


def _safe_load(message: Any) -> dict[str, Any] | None:
    if isinstance(message, (bytes, bytearray)):
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError:
            logger.warning("Received non-text message: %s", message)
            return None

    try:
        return json.loads(message)
    except json.JSONDecodeError:
        logger.warning("Received non-JSON message: %s", message)
        return None


_IGNORED_EVENTS = {
    "response.created",
    "response.done",
    "rate_limits.updated",
    "response.output_item.added",
    "response.output_item.done",
    "response.content_part.added",
    "response.content_part.done",
    "response.output_audio_transcript.delta",
    "response.output_audio.delta",
    "response.output_audio.done",
    "response.output_text.delta",
    "response.output_text.done",
    "conversation.item.added",
    "conversation.item.done",
    "session.updated",
}


__all__ = ["receive_transcription_events"]
