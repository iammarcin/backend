"""Integration coverage for the static transcription REST endpoint."""

from __future__ import annotations

import json
from typing import Any, Callable, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from core.exceptions import ProviderError
from core.providers.audio.base import SpeechProviderRequest, SpeechTranscriptionResult
from features.audio.schemas import AudioAction
from main import app


pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class RecordingProvider:
    """Stub provider capturing invocation metadata for assertions."""

    def __init__(self, *, result_text: str = "stub transcript", language: str | None = "en"):
        self.calls: list[tuple[str, SpeechProviderRequest]] = []
        self._result_text = result_text
        self._language = language

    async def transcribe_file(self, request: SpeechProviderRequest) -> SpeechTranscriptionResult:
        self.calls.append(("transcribe", request))
        request.ensure_bytes()
        return SpeechTranscriptionResult(
            text=self._result_text,
            provider="stub-openai",
            language=self._language,
            duration_seconds=2.4,
            metadata={"model": request.model, "temperature": request.temperature},
        )

    async def translate_file(self, request: SpeechProviderRequest) -> SpeechTranscriptionResult:
        self.calls.append(("translate", request))
        request.ensure_bytes()
        return SpeechTranscriptionResult(
            text="translated transcript",
            provider="stub-gemini",
            language="es",
            duration_seconds=3.1,
            metadata={"model": request.model},
        )


@pytest.mark.anyio
async def test_transcribe_audio_returns_envelope_and_logs(
    monkeypatch: pytest.MonkeyPatch,
    auth_token_factory: Callable[..., str],
) -> None:
    provider = RecordingProvider()
    factory_calls: list[dict[str, Any]] = []

    def _get_audio_provider(settings: dict[str, Any], *, action: str | None = None):
        factory_calls.append({"settings": settings, "action": action})
        return provider

    monkeypatch.setattr("features.audio.service.get_audio_provider", _get_audio_provider)

    token = auth_token_factory(customer_id=42, email="integration@example.com")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files={
                "file": ("sample.wav", b"pcm-bytes", "audio/wav"),
                "action": (None, "transcribe"),
                "category": (None, "speech"),
                "user_input": (None, json.dumps({"prompt": "Hello"})),
                "user_settings": (
                    None,
                    json.dumps({"speech": {"model": "gpt-4o-transcribe", "temperature": 0.2}}),
                ),
                "customer_id": (None, "42"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["result"] == "stub transcript"
    assert payload["data"]["provider"] == "stub-openai"
    assert payload["meta"]["metadata"]["duration_seconds"] == pytest.approx(2.4)

    assert factory_calls[0]["action"] == "transcribe"
    assert factory_calls[0]["settings"]["audio"]["model"] == "gpt-4o-transcribe"

    assert provider.calls
    call_name, request = provider.calls[0]
    assert call_name == "transcribe"
    assert request.metadata["customer_id"] == 42
    assert request.metadata["action"] == "transcribe"


@pytest.mark.anyio
async def test_transcribe_audio_propagates_provider_error(
    monkeypatch: pytest.MonkeyPatch,
    auth_token_factory: Callable[..., str],
) -> None:
    class FailingProvider:
        async def transcribe_file(self, request: SpeechProviderRequest) -> SpeechTranscriptionResult:
            raise ProviderError("mock failure", provider="stub-openai")

    def _get_audio_provider(settings: dict[str, Any], *, action: str | None = None):
        return FailingProvider()

    monkeypatch.setattr("features.audio.service.get_audio_provider", _get_audio_provider)

    token = auth_token_factory(customer_id=7)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files={
                "file": ("broken.wav", b"pcm-bytes", "audio/wav"),
                "action": (None, "transcribe"),
                "category": (None, "speech"),
                "user_input": (None, json.dumps({})),
                "user_settings": (None, json.dumps({"speech": {"model": "gpt-4o-transcribe"}})),
                "customer_id": (None, "7"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 502
    payload = response.json()
    assert payload["success"] is False
    assert payload["code"] == 502
    assert "mock failure" in payload["message"]


@pytest.mark.anyio
async def test_translate_audio_routes_to_translation(
    monkeypatch: pytest.MonkeyPatch,
    auth_token_factory: Callable[..., str],
) -> None:
    provider = RecordingProvider()
    factory_calls: list[dict[str, Any]] = []

    def _get_audio_provider(settings: dict[str, Any], *, action: str | None = None):
        factory_calls.append({"settings": settings, "action": action})
        return provider

    monkeypatch.setattr("features.audio.service.get_audio_provider", _get_audio_provider)

    token = auth_token_factory(customer_id=9)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files={
                "file": ("spanish.wav", b"pcm-bytes", "audio/wav"),
                "action": (None, AudioAction.TRANSLATE.value),
                "category": (None, "speech"),
                "user_input": (None, json.dumps({})),
                "user_settings": (None, json.dumps({"speech": {"model": "gemini-2.5-flash"}})),
                "customer_id": (None, "9"),
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["action"] == "translate"
    assert body["data"]["provider"] == "stub-gemini"
    assert body["data"]["language"] == "es"

    assert factory_calls[0]["action"] == "translate"
    assert provider.calls[0][0] == "translate"
