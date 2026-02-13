from __future__ import annotations

from core.providers.realtime.base import RealtimeEvent, RealtimeEventType
from core.streaming.manager import StreamingManager
from features.realtime.context import RealtimeTurnContext
from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.state import RealtimeTurnState
from features.realtime.turn_state_updates import update_turn_state_from_event


def test_update_turn_state_tracks_live_translation_deltas() -> None:
    manager = StreamingManager()
    turn_state = RealtimeTurnState()
    turn_context = RealtimeTurnContext()
    settings = RealtimeSessionSettings(live_translation=True)

    delta_event = RealtimeEvent(
        type=RealtimeEventType.MESSAGE,
        payload={
            "event": "conversation.item.input_audio_transcription.delta",
            "text": "Hola",
        },
    )

    update_turn_state_from_event(
        event=delta_event,
        turn_state=turn_state,
        turn_context=turn_context,
        streaming_manager=manager,
        session_id="session-1",
        settings=settings,
    )

    assert turn_context.live_translation_text == "Hola"
    assert manager.results["translation_chunks"] == ["Hola"]

    completed_event = RealtimeEvent(
        type=RealtimeEventType.MESSAGE,
        payload={
            "event": "conversation.item.input_audio_transcription.completed",
            "text": "Hola mundo",
        },
    )

    update_turn_state_from_event(
        event=completed_event,
        turn_state=turn_state,
        turn_context=turn_context,
        streaming_manager=manager,
        session_id="session-1",
        settings=settings,
    )

    assert turn_state.has_user_transcript is True
    assert turn_context.live_translation_text == "Hola mundo"
    assert manager.results["translation_chunks"] == ["Hola", "Hola mundo"]
