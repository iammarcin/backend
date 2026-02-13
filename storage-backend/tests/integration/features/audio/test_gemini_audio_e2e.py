"""Integration tests covering Gemini audio workflows via the chat websocket."""

from __future__ import annotations

import os

import pytest

# These tests require database access but use stub clients (not real APIs)
pytestmark = [
    pytest.mark.skipif(
        os.getenv("MAIN_DB_URL") is None,
        reason="Requires MAIN_DB_URL environment variable for MySQL connection"
    ),
    pytest.mark.requires_docker,
]

from types import SimpleNamespace
from typing import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient

from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.providers.factory import register_text_provider
from core.providers.audio.gemini_streaming import GeminiStreamingSpeechProvider
from core.pydantic_schemas import ProviderResponse


class _StubTextProvider(BaseTextProvider):
    """Stream deterministic text chunks so websocket assertions stay stable."""

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True)

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 256,
        **_: object,
    ) -> ProviderResponse:
        return ProviderResponse(text="stub-response", model=model or "stub", provider="stub")

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        runtime=None,
        **_: object,
    ) -> AsyncIterator[str]:
        for chunk in ["Gemini", " audio", " response"]:
            yield chunk


@pytest.fixture(autouse=True)
def _override_text_provider() -> Iterator[None]:
    """Ensure OpenAI calls inside the workflow use the deterministic stub."""

    from core.providers.registries import _text_providers

    original = _text_providers.get("openai")
    register_text_provider("openai", _StubTextProvider)
    try:
        yield
    finally:
        if original is not None:
            _text_providers["openai"] = original
        else:
            _text_providers.pop("openai", None)


class _StubGeminiClient:
    """Minimal Gemini client stub used by both STT and multimodal flows."""

    def __init__(self, *, transcription_text: str, stream_chunks: list[str]) -> None:
        self._transcription_text = transcription_text
        self._stream_chunks = stream_chunks
        self.models = self

    # Streaming STT relies on generate_content returning an object with ``text``
    def generate_content(self, *_, **__) -> SimpleNamespace:
        return SimpleNamespace(text=self._transcription_text)

    # Audio-direct workflow uses the streaming variant to deliver chunks.
    def generate_content_stream(self, *_, **__) -> Iterator[SimpleNamespace]:
        for chunk in self._stream_chunks:
            yield SimpleNamespace(text=chunk)


def _make_websocket_payload(*, request_type: str, send_full_audio: bool = False) -> dict[str, object]:
    """Build WebSocket payload using canonical snake_case field names."""
    speech_settings: dict[str, object] = {
        "model": "gemini-flash",
        "recording_sample_rate": 16000,
    }
    if send_full_audio:
        speech_settings["send_full_audio_to_llm"] = True

    prompt_chunks = [{"type": "text", "text": "Please help"}]

    return {
        "request_type": request_type,
        "customer_id": 1,  # Must match a valid user in the database
        "prompt": prompt_chunks,
        "user_input": {
            "prompt": prompt_chunks,
            "chat_history": [],
        },
        "user_settings": {
            "speech": speech_settings,
            "text": {"model": "gpt-4o-mini", "stream": True},
            "tts": {"tts_auto_execute": False},
        },
    }


def test_gemini_streaming_stt_flow(
    monkeypatch: pytest.MonkeyPatch,
    chat_test_client: TestClient,
    websocket_url_factory,
) -> None:
    """Audio websocket request should emit transcription and final text events."""

    stub_client = _StubGeminiClient(
        transcription_text="Test transcription",
        stream_chunks=["Chunk A ", "Chunk B"],
    )
    monkeypatch.setattr(
        "core.providers.audio.gemini_streaming.get_gemini_client",
        lambda: stub_client,
    )
    monkeypatch.setattr(
        "core.clients.ai.get_gemini_client",
        lambda: stub_client,
    )

    async def _mock_transcribe_stream(self, *, audio_source, manager, mode="non-realtime"):
        await manager.send_to_queues({"type": "transcription", "content": "Test transcription"})
        return "Test transcription"

    monkeypatch.setattr(
        GeminiStreamingSpeechProvider,
        "transcribe_stream",
        _mock_transcribe_stream,
    )

    audio_chunk = b"\x00" * (16000 * 2)  # 1 second of 16-bit mono audio

    with chat_test_client.websocket_connect(websocket_url_factory()) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "websocket_ready"

        websocket.send_json(_make_websocket_payload(request_type="audio"))
        websocket.send_bytes(audio_chunk)
        websocket.send_json({"type": "RecordingFinished"})

        text_chunks: list[str] = []
        transcripts: list[str] = []

        # Dual-flag completion pattern: wait for both text_completed and tts completion
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            message = websocket.receive_json()
            if message["type"] == "text_completed":
                text_completed = True
            elif message["type"] in ("tts_completed", "tts_not_requested"):
                tts_completed = True
            elif message["type"] == "transcription":
                transcripts.append(message["content"])
            elif message["type"] == "text_chunk":
                text_chunks.append(message["content"])
            elif message["type"] == "error":
                pytest.fail(f"Received error from websocket: {message}")

        assert transcripts, "Transcription event was not emitted"
        assert transcripts[-1] == "Test transcription"
        assert "".join(text_chunks) == "Gemini audio response"


def test_audio_direct_flow(
    monkeypatch: pytest.MonkeyPatch,
    chat_test_client: TestClient,
    websocket_url_factory,
) -> None:
    """Audio-direct mode should stream Gemini text without transcription."""

    stub_client = _StubGeminiClient(
        transcription_text="Ignored",  # not used in this path
        stream_chunks=["Multimodal", " reply"],
    )
    monkeypatch.setattr(
        "core.providers.audio.gemini_streaming.get_gemini_client",
        lambda: stub_client,
    )
    monkeypatch.setattr(
        "core.clients.ai.get_gemini_client",
        lambda: stub_client,
    )

    audio_chunk = b"\x11" * (16000 * 2)

    with chat_test_client.websocket_connect(websocket_url_factory()) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "websocket_ready"

        websocket.send_json(
            _make_websocket_payload(request_type="audio", send_full_audio=True)
        )
        websocket.send_bytes(audio_chunk)
        websocket.send_json({"type": "RecordingFinished"})

        text_chunks: list[str] = []
        transcription_events: list[str] = []

        # Dual-flag completion pattern: wait for both text_completed and tts completion
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            message = websocket.receive_json()
            if message["type"] == "text_completed":
                text_completed = True
            elif message["type"] in ("tts_completed", "tts_not_requested"):
                tts_completed = True
            elif message["type"] == "transcription":
                transcription_events.append(message["content"])
            elif message["type"] == "text_chunk":
                text_chunks.append(message["content"])
            elif message["type"] == "error":
                pytest.fail(f"Received error from websocket: {message}")

    assert transcription_events, "Placeholder transcription message missing"
    assert any("Recording" in event for event in transcription_events)
    assert "".join(text_chunks) == "Multimodal reply"


def test_tts_integration_after_gemini(
    monkeypatch: pytest.MonkeyPatch,
    chat_test_client: TestClient,
    websocket_url_factory,
) -> None:
    """When TTS auto execute is enabled the workflow should invoke TTS."""

    stub_client = _StubGeminiClient(
        transcription_text="Ignored",
        stream_chunks=["Speech", " summary"],
    )
    monkeypatch.setattr(
        "core.providers.audio.gemini_streaming.get_gemini_client",
        lambda: stub_client,
    )
    monkeypatch.setattr(
        "core.clients.ai.get_gemini_client",
        lambda: stub_client,
    )

    tts_calls: list[str] = []

    async def _fake_handle_tts_workflow(**kwargs: object) -> dict[str, object]:
        manager = kwargs.get("manager")
        if hasattr(manager, "send_to_queues"):
            await manager.send_to_queues({"type": "tts_started", "content": {}})
            await manager.send_to_queues({"type": "tts_completed", "content": ""})
        tts_calls.append("called")
        return {
            "tts": {
                "provider": "elevenlabs",
                "model": "eleven_multilingual_v2",
                "voice": "test_voice",
                "format": "mp3",
                "audio_file_url": "https://example.com/test_audio.mp3",
                "storage_metadata": {"s3_url": "https://s3.example.com/test_audio.mp3"},
            }
        }

    # Patch where handle_tts_workflow is defined and where it's imported
    monkeypatch.setattr(
        "features.chat.utils.websocket_workflows.tts.handle_tts_workflow",
        _fake_handle_tts_workflow,
    )
    monkeypatch.setattr(
        "features.chat.utils.websocket_workflows.gemini_streaming.handle_tts_workflow",
        _fake_handle_tts_workflow,
    )

    payload = _make_websocket_payload(request_type="audio", send_full_audio=True)
    payload["user_settings"]["tts"] = {"tts_auto_execute": True}

    audio_chunk = b"\x22" * (16000 * 2)

    with chat_test_client.websocket_connect(websocket_url_factory()) as websocket:
        websocket.receive_json()
        websocket.send_json(payload)
        websocket.send_bytes(audio_chunk)
        websocket.send_json({"type": "RecordingFinished"})

        event_types: list[str] = []
        # Dual-flag completion pattern: wait for both text_completed and tts_completed
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            message = websocket.receive_json()
            event_types.append(message["type"])
            if message["type"] == "text_completed":
                text_completed = True
            elif message["type"] in ("tts_completed", "tts_not_requested"):
                tts_completed = True
            elif message["type"] == "error":
                pytest.fail(f"Received error from websocket: {message}")

    assert tts_calls, "TTS workflow was not invoked"
    assert "tts_started" in event_types
    assert "tts_completed" in event_types
