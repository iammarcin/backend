from __future__ import annotations

import logging

from fastapi import WebSocket

from core.providers.realtime.base import RealtimeEvent, RealtimeEventType
from core.streaming.manager import StreamingManager

from .context import RealtimeTurnContext
from .event_factory import RealtimeEventFactory
from .event_payloads import (
    SUPPRESSED_DEBUG_EVENTS,
    build_ai_responding_payload,
    build_websocket_payload,
    resolve_response_id,
    should_emit_ai_responding,
)
from .finalise import TurnFinaliser
from .metrics import RealtimeMetricsCollector
from .schemas import RealtimeSessionSettings
from .state import RealtimeTurnState, TurnPhase
from .turn_state_updates import update_turn_state_from_event


logger = logging.getLogger(__name__)


async def handle_provider_event(
    *,
    event: RealtimeEvent,
    websocket: WebSocket,
    session_id: str,
    customer_id: int,
    settings: RealtimeSessionSettings,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    streaming_manager: StreamingManager,
    turn_finaliser: TurnFinaliser,
    event_factory: RealtimeEventFactory,
    metrics: RealtimeMetricsCollector | None = None,
    force_close: bool = False,
) -> bool:
    """Relay a provider event to the websocket client and update turn state."""

    should_close_session = False

    default_event_name = "audio_chunk" if event.type == RealtimeEventType.AUDIO_CHUNK else ""
    event_name = str(event.payload.get("event") or default_event_name)
    if event_name not in SUPPRESSED_DEBUG_EVENTS:
        logger.debug(
            "Handling provider event (session=%s, type=%s, event=%s)",
            session_id,
            event.type.value,
            event_name or "unknown",
        )

    payload = build_websocket_payload(
        event=event, session_id=session_id, settings=settings
    )
    if payload is None:
        return should_close_session

    if should_emit_ai_responding(
        event=event,
        payload=payload,
        ai_response_started=turn_context.ai_response_started,
    ):
        ai_response_payload = build_ai_responding_payload(
            session_id=session_id,
            turn_number=turn_context.turn_number,
            response_id=resolve_response_id(
                event=event,
                payload=payload,
                fallback=turn_context.response_id,
            ),
        )
        await websocket.send_json(ai_response_payload)
        turn_context.ai_response_started = True

    await websocket.send_json(payload)

    update_turn_state_from_event(
        event=event,
        turn_state=turn_state,
        turn_context=turn_context,
        streaming_manager=streaming_manager,
        session_id=session_id,
        settings=settings,
        metrics=metrics,
    )

    control_payload = payload.get("payload", {}) if isinstance(payload, dict) else {}
    control_event_name = str(control_payload.get("event") or "")
    if metrics and control_event_name == "turn.started":
        metrics.start_turn()

    if turn_state.is_turn_complete() and turn_state.phase != TurnPhase.PERSISTING:
        should_close_session = await _finalise_turn(
            websocket=websocket,
            session_id=session_id,
            customer_id=customer_id,
            settings=settings,
            turn_state=turn_state,
            turn_context=turn_context,
            streaming_manager=streaming_manager,
            turn_finaliser=turn_finaliser,
            event_factory=event_factory,
            metrics=metrics,
            force_close=force_close,
        )

    return should_close_session


async def _finalise_turn(
    *,
    websocket: WebSocket,
    session_id: str,
    customer_id: int,
    settings: RealtimeSessionSettings,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    streaming_manager: StreamingManager,
    turn_finaliser: TurnFinaliser,
    event_factory: RealtimeEventFactory,
    metrics: RealtimeMetricsCollector | None,
    force_close: bool,
) -> bool:
    logger.info(
        "Turn complete (phase=%s, has_transcript=%s, has_text=%s, has_audio=%s, response_done=%s)",
        turn_state.phase,
        turn_state.has_user_transcript,
        turn_state.has_ai_text,
        turn_state.has_ai_audio,
        turn_state.response_done,
    )

    turn_state.start_persisting()

    try:
        await turn_finaliser.finalise_turn(
            customer_id=customer_id,
            settings=settings,
            turn_state=turn_state,
            turn_context=turn_context,
            websocket=websocket,
            session_id=session_id,
            event_factory=event_factory,
        )

        turn_state.mark_completed()
        duration = turn_state.get_turn_duration_ms()
        if duration is not None:
            logger.info(
                "Turn %d completed in %.2fms",
                turn_context.turn_number,
                duration,
            )
        else:
            logger.info("Turn %d completed", turn_context.turn_number)

        if metrics:
            metrics.end_turn()

        if not settings.vad_enabled or force_close:
            logger.info(
                "Single-turn realtime session completed; scheduling websocket closure",
                extra={"session_id": session_id},
            )
            turn_context.reset()
            return True

        turn_context.reset()
        turn_state.reset()
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Turn finalisation failed: %s", str(exc))
        turn_state.mark_error()
        raise

    return False


__all__ = ["handle_provider_event"]
