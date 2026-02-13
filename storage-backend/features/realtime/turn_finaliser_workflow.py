from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import WebSocket

from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.state import RealtimeTurnState

from .context import RealtimeTurnContext
from .event_factory import RealtimeEventFactory
from .message_payload import build_realtime_message_request
from .turn_events import emit_turn_events
from .turn_persistence import persist_chat_history, update_session_tracker

if TYPE_CHECKING:
    from .turn_finaliser import TurnFinaliser


logger = logging.getLogger(__name__)


async def perform_turn_finalisation(
    finaliser: "TurnFinaliser",
    *,
    customer_id: int,
    settings: RealtimeSessionSettings,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    websocket: WebSocket,
    session_id: str,
    event_factory: RealtimeEventFactory,
) -> None:
    """Persist the turn, upload audio, and notify the websocket client."""

    derived_filename = (
        turn_context.adjusted_audio_filename
        or turn_context.generate_turn_filename()
    )
    raw_user_transcript = turn_context.user_transcript()
    _log_transcript(turn_context=turn_context, session_id=session_id)

    user_message_text = raw_user_transcript or "[Voice input]"
    assistant_text = turn_context.assistant_text() or turn_context.assistant_transcript()
    completed_turn_number = turn_context.turn_number

    # Ensure nested helpers reference the latest event factory for this turn.
    finaliser.event_factory = event_factory

    audio_result = await finaliser._process_audio(
        turn_context=turn_context,
        settings=settings,
        websocket=websocket,
        session_id=session_id,
        customer_id=customer_id,
    )

    assistant_message_text = finaliser._assistant_text(
        assistant_text=assistant_text,
        audio_result=audio_result,
    )
    session_name = settings.session_name or f"Realtime session {customer_id}"
    tracked_session_id = finaliser.session_tracker.get_session_id()

    request = build_realtime_message_request(
        customer_id=customer_id,
        session_name=session_name,
        settings=settings,
        user_message_text=user_message_text,
        assistant_message_text=assistant_message_text,
        response_id=turn_context.response_id,
        audio_url=audio_result.audio_url,
        derived_filename=derived_filename,
        translation_text=(
            audio_result.translation_text or turn_context.live_translation_text
        ),
        session_id=tracked_session_id,
        original_user_settings=turn_context.initial_user_settings,
    )

    write_result = await persist_chat_history(
        finaliser=finaliser,
        request=request,
        websocket=websocket,
        session_id=session_id,
        turn_number=completed_turn_number,
        event_factory=event_factory,
    )
    if write_result is None:
        return

    persisted_session_id = write_result.messages.session_id
    update_session_tracker(
        finaliser=finaliser,
        persisted_session_id=persisted_session_id,
        session_id=session_id,
        turn_number=completed_turn_number,
    )

    event_session_id = persisted_session_id or tracked_session_id or session_id
    factory = RealtimeEventFactory(session_id=event_session_id)
    finaliser.event_factory = factory

    next_audio_filename = turn_context.prepare_for_next_turn()
    logger.info(
        "Prepared next audio filename for turn %d: '%s' (empty: %s, base_filename: '%s')",
        completed_turn_number,
        next_audio_filename,
        not bool(next_audio_filename),
        turn_context.base_audio_filename,
    )
    await emit_turn_events(
        factory=factory,
        websocket=websocket,
        turn_number=completed_turn_number,
        user_message_text=user_message_text,
        assistant_message_text=assistant_message_text,
        audio_result=audio_result,
        next_audio_filename=next_audio_filename,
        write_result=write_result,
    )


def _log_transcript(*, turn_context: RealtimeTurnContext, session_id: str) -> None:
    raw_user_transcript = turn_context.user_transcript()
    logger.info(
        "User transcript from turn_context (turn=%d, session=%s): '%s' (length=%d)",
        turn_context.turn_number,
        session_id,
        raw_user_transcript,
        len(raw_user_transcript or ""),
    )
    if not raw_user_transcript:
        logger.warning(
            "User transcript is empty, using placeholder (turn=%d, session=%s)",
            turn_context.turn_number,
            session_id,
        )


__all__ = ["perform_turn_finalisation"]
