"""Unit tests for realtime turn finalisation payload construction."""

from __future__ import annotations

import json

import pytest

from core.streaming.manager import StreamingManager
from features.chat.schemas.responses import MessageWritePayload, MessageWriteResult
from features.realtime.audio_finaliser import AudioProcessingResult
from features.realtime.context import RealtimeTurnContext
from features.realtime.finalise import SessionTracker, TurnFinaliser
from features.realtime.event_factory import RealtimeEventFactory
from features.realtime.schemas import RealtimeSessionSettings
from features.realtime.state import RealtimeTurnState


class StubChatHistoryService:
    """Capture create_message payloads for inspection."""

    def __init__(self) -> None:
        self.captured_request = None

    async def create_message(self, request):  # pragma: no cover - exercised via test
        self.captured_request = request
        return MessageWritePayload(
            messages=MessageWriteResult(
                user_message_id=101,
                ai_message_id=202,
                session_id="persisted-session",
            )
        )


class StubAudioFinaliser:
    """Return a deterministic audio processing result."""

    async def process_audio(self, **_):  # pragma: no cover - exercised via test
        return AudioProcessingResult(
            audio_url="https://cdn.example.com/audio.wav",
            translation_text="Gracias",
        )


class StubWebSocket:
    """Collect websocket payloads emitted during finalisation."""

    def __init__(self) -> None:
        self.sent_payloads: list[dict] = []

    async def send_json(self, payload):  # pragma: no cover - exercised via test
        self.sent_payloads.append(payload)

    async def send_text(self, payload: str) -> None:  # pragma: no cover - exercised via test
        self.sent_payloads.append(json.loads(payload))


@pytest.mark.asyncio
async def test_finalise_turn_persists_enriched_payload() -> None:
    """Turn finalisation forwards enriched settings and capitalised senders."""

    chat_service = StubChatHistoryService()
    tracker_state: dict[str, str | None] = {"value": None}

    def get_session_id() -> str | None:
        return tracker_state["value"]

    def set_session_id(value: str) -> None:
        tracker_state["value"] = value

    event_factory = RealtimeEventFactory(session_id="session-123")
    finaliser = TurnFinaliser(
        chat_history_service=chat_service,
        storage_service_factory=lambda: None,
        streaming_manager=StreamingManager(),
        stt_service_factory=lambda: None,
        session_tracker=SessionTracker(
            get_session_id=get_session_id,
            set_session_id=set_session_id,
        ),
        event_factory=event_factory,
    )
    finaliser._audio_finaliser = StubAudioFinaliser()

    turn_context = RealtimeTurnContext()
    turn_context.initial_user_settings = {
        "speech": {
            "voice": "verse",
            "androidFilePath": "/storage/emulated/0/Android/data/com.betterai/files/audio/audio_00.wav",
        },
        "text": {"ai_character": "coach_karen"},
    }
    turn_context.set_base_audio_filename(
        "/storage/emulated/0/Android/data/com.betterai/files/audio/audio_00.wav"
    )
    turn_context.user_transcript_parts.append("Hello from user")
    turn_context.assistant_text_parts.append("Assistant reply")
    turn_context.response_id = "resp_123"

    websocket = StubWebSocket()
    settings = RealtimeSessionSettings(
        model="gpt-realtime",
        voice="verse",
        temperature=0.9,
        vad_enabled=True,
        enable_audio_input=True,
        enable_audio_output=True,
        tts_auto_execute=False,
        live_translation=True,
        translation_language="es",
        session_name="Coaching session",
    )

    await finaliser.finalise_turn(
        customer_id=7,
        settings=settings,
        turn_state=RealtimeTurnState(),
        turn_context=turn_context,
        websocket=websocket,
        session_id="session-123",
        event_factory=event_factory,
    )

    request = chat_service.captured_request
    assert request is not None
    assert request.user_message.sender == "User"
    assert request.ai_response is not None
    assert request.ai_response.sender == "AI"
    assert request.ai_character_name == "coach_karen"
    assert request.user_message.file_names == [
        "/storage/emulated/0/Android/data/com.betterai/files/audio/audio_00.wav"
    ]
    assert request.user_settings["text"]["ai_character"] == "coach_karen"
    assert request.user_settings["speech"]["androidFilePath"] == (
        "/storage/emulated/0/Android/data/com.betterai/files/audio/audio_00.wav"
    )
    assert request.user_settings["speech"]["voice"] == "verse"
    assert request.user_settings["speech"]["live_translation_text"] == "Gracias"
    assert tracker_state["value"] == "persisted-session"
