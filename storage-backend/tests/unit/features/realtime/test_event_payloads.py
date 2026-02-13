from __future__ import annotations

from core.providers.realtime.base import RealtimeEvent, RealtimeEventType
from features.realtime.event_payloads import build_websocket_payload
from features.realtime.schemas import RealtimeSessionSettings


def test_build_websocket_payload_emits_translation_delta_when_enabled() -> None:
    event = RealtimeEvent(
        type=RealtimeEventType.MESSAGE,
        payload={
            "event": "conversation.item.input_audio_transcription.delta",
            "text": "Hola",
            "item_id": "item-1",
        },
    )
    settings = RealtimeSessionSettings(live_translation=True)

    payload = build_websocket_payload(
        event=event,
        session_id="session-1",
        settings=settings,
    )

    assert payload == {
        "session_id": "session-1",
        "type": "translation",
        "status": "delta",
        "content": "Hola",
        "item_id": "item-1",
    }


def test_build_websocket_payload_translation_completed_includes_empty_content() -> None:
    event = RealtimeEvent(
        type=RealtimeEventType.MESSAGE,
        payload={
            "event": "user.transcript.completed",
            "text": "",
            "item_id": "item-2",
        },
    )
    settings = RealtimeSessionSettings(live_translation=True)

    payload = build_websocket_payload(
        event=event,
        session_id="session-2",
        settings=settings,
    )

    assert payload == {
        "session_id": "session-2",
        "type": "translation",
        "status": "completed",
        "content": "",
        "item_id": "item-2",
    }


def test_build_websocket_payload_keeps_transcription_when_translation_disabled() -> None:
    event = RealtimeEvent(
        type=RealtimeEventType.MESSAGE,
        payload={
            "event": "user.transcript.completed",
            "text": "Bonjour",
        },
    )

    payload = build_websocket_payload(
        event=event,
        session_id="session-3",
        settings=RealtimeSessionSettings(live_translation=False),
    )

    assert payload == {
        "session_id": "session-3",
        "type": "transcription",
        "status": "completed",
        "content": "Bonjour",
    }
