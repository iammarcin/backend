from __future__ import annotations

import base64
import logging

from core.providers.realtime.base import RealtimeEvent, RealtimeEventType
from core.streaming.manager import StreamingManager

from .context import RealtimeTurnContext
from .errors import classify_error, is_expected_vad_error
from .metrics import RealtimeMetricsCollector
from .schemas import RealtimeSessionSettings
from .state import RealtimeTurnState


logger = logging.getLogger(__name__)


def update_turn_state_from_event(
    *,
    event: RealtimeEvent,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    streaming_manager: StreamingManager,
    session_id: str,
    settings: RealtimeSessionSettings | None = None,
    metrics: RealtimeMetricsCollector | None = None,
) -> None:
    """Mutate ``turn_state`` and ``turn_context`` in response to an event."""

    payload = event.payload
    if event.type == RealtimeEventType.MESSAGE:
        _handle_message_event(
            payload=payload,
            turn_state=turn_state,
            turn_context=turn_context,
            streaming_manager=streaming_manager,
            session_id=session_id,
            settings=settings,
        )
    elif event.type == RealtimeEventType.AUDIO_CHUNK:
        _handle_audio_chunk_event(
            payload=payload,
            turn_state=turn_state,
            turn_context=turn_context,
            streaming_manager=streaming_manager,
            metrics=metrics,
        )
    elif event.type == RealtimeEventType.CONTROL:
        _handle_control_event(
            payload=payload,
            turn_state=turn_state,
            turn_context=turn_context,
        )
    elif event.type == RealtimeEventType.ERROR:
        _handle_error_event(
            event=event,
            turn_state=turn_state,
            settings=settings,
        )


def _handle_message_event(
    *,
    payload: dict[str, object],
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    streaming_manager: StreamingManager,
    session_id: str,
    settings: RealtimeSessionSettings | None,
) -> None:
    event_name = str(payload.get("event") or "")
    translation_enabled = bool(settings and settings.live_translation)
    if event_name in {
        "user.transcript.delta",
        "conversation.item.input_audio_transcription.delta",
    }:
        raw_text = str(payload.get("text") or "")
        text = raw_text.strip()
        if text:
            turn_context.user_transcript_parts.append(text)
            if translation_enabled:
                turn_context.append_live_translation(text)
                streaming_manager.collect_chunk(text, "translation")
        turn_state.start_user_turn()
    elif event_name in {
        "user.transcript.completed",
        "conversation.item.input_audio_transcription.completed",
    }:
        _handle_transcript_completed(
            payload=payload,
            turn_state=turn_state,
            turn_context=turn_context,
            session_id=session_id,
            streaming_manager=streaming_manager,
            translation_enabled=translation_enabled,
        )
    elif event_name == "assistant.text.delta":
        text_delta = str(payload.get("text") or "")
        if text_delta:
            turn_context.assistant_text_parts.append(text_delta)
            streaming_manager.collect_chunk(text_delta, "text")
        if payload.get("response_id"):
            turn_context.response_id = str(payload["response_id"])
        turn_state.start_ai_response(turn_context.response_id)
    elif event_name == "assistant.text.completed":
        if turn_context.assistant_text_parts:
            turn_state.has_ai_text = True
    elif event_name == "assistant.transcript.delta":
        transcript_delta = str(payload.get("text") or "")
        if transcript_delta:
            turn_context.assistant_transcript_parts.append(transcript_delta)
            streaming_manager.collect_chunk(transcript_delta, "transcription")
        turn_state.start_ai_response(turn_context.response_id)
    elif event_name == "assistant.transcript.completed":
        transcript_text = str(payload.get("text") or "").strip()
        if transcript_text:
            turn_context.assistant_transcript_parts.append(transcript_text)
            streaming_manager.collect_chunk(transcript_text, "transcription")
        if turn_context.assistant_transcript_parts:
            turn_state.has_ai_text = True


def _handle_transcript_completed(
    *,
    payload: dict[str, object],
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    session_id: str,
    streaming_manager: StreamingManager,
    translation_enabled: bool,
) -> None:
    transcript_text = str(payload.get("text") or "").strip()
    turn_state.start_user_turn()
    logger.info(
        "Received user transcript (turn=%d, session=%s): '%s'",
        turn_context.turn_number,
        session_id,
        transcript_text,
    )
    if transcript_text:
        turn_context.user_transcript_parts.clear()
        turn_context.user_transcript_parts.append(transcript_text)
        logger.info(
            "Stored user transcript in turn_context (turn=%d, parts=%d)",
            turn_context.turn_number,
            len(turn_context.user_transcript_parts),
        )
    else:
        logger.warning(
            "Received empty user transcript (turn=%d, session=%s)",
            turn_context.turn_number,
            session_id,
        )
    if translation_enabled:
        turn_context.append_live_translation(transcript_text, is_final=True)
        if transcript_text:
            streaming_manager.collect_chunk(transcript_text, "translation")
    turn_state.has_user_transcript = True


def _handle_audio_chunk_event(
    *,
    payload: dict[str, object],
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    streaming_manager: StreamingManager,
    metrics: RealtimeMetricsCollector | None,
) -> None:
    audio_event = payload.get("event")
    audio_chunk = payload.get("audio")
    if isinstance(audio_chunk, str):
        decoded = _safe_base64_decode(audio_chunk)
        if decoded:
            turn_context.audio_chunks.append(decoded)
            streaming_manager.collect_chunk(audio_chunk, "audio")
            if metrics:
                metrics.record_audio_sent(len(decoded))
        turn_state.start_ai_response(payload.get("response_id"))
    if audio_event in {
        "assistant.audio.completed",
        "response.output_audio.completed",
    }:
        turn_state.has_ai_audio = True


def _handle_control_event(
    *,
    payload: dict[str, object],
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
) -> None:
    control_event = payload.get("event")
    response_id = payload.get("response_id")
    if isinstance(response_id, str):
        turn_context.response_id = response_id
    if control_event == "input_audio_buffer.speech_started":
        turn_state.start_user_turn()
    elif control_event in {
        "input_audio_buffer.speech_stopped",
        "input_audio_buffer.committed",
    }:
        turn_state.start_ai_processing()
    elif control_event in {
        "response.created",
        "response.output_text.delta",
        "response.output_audio.delta",
    }:
        turn_state.start_ai_response(turn_context.response_id or response_id)
    elif control_event in {"response.done", "response.completed"}:
        turn_state.mark_response_done()
    elif control_event == "turn.cancelled":
        turn_state.mark_cancelled()
    elif control_event == "turn.completed":
        turn_state.mark_response_done()


def _handle_error_event(
    *,
    event: RealtimeEvent,
    turn_state: RealtimeTurnState,
    settings: RealtimeSessionSettings | None,
) -> None:
    error_code = event.payload.get("code")
    classification = classify_error(error_code)
    vad_enabled = getattr(settings, "vad_enabled", True) if settings else True

    if is_expected_vad_error(error_code, vad_enabled):
        return

    if classification.should_mark_error:
        turn_state.mark_error(
            error_code=str(error_code) if isinstance(error_code, str) else None,
            severity=classification.severity.value,
            should_close=classification.should_close_session,
        )


def _safe_base64_decode(value: str) -> bytes:
    try:
        return base64.b64decode(value)
    except Exception:  # pragma: no cover - defensive
        return b""


__all__ = ["update_turn_state_from_event"]
