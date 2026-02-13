import json
from typing import Any, Callable, Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from features.audio.dependencies import get_stt_service
from features.audio.schemas import AudioAction
from features.audio.service import STTService
from main import app


@pytest.fixture(autouse=True)
def reset_dependency_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_transcribe_audio_returns_envelope(auth_token_factory: Callable[..., str]) -> None:
    class StubService:
        async def transcribe_file(self, **kwargs: Any) -> STTService.StaticTranscriptionResult:
            return STTService.StaticTranscriptionResult(
                status="completed",
                result="Stub transcript",
                action=AudioAction.TRANSCRIBE,
                provider="mock",
                filename=kwargs.get("filename", "sample.wav"),
            )

    stub_service = StubService()
    app.dependency_overrides[get_stt_service] = lambda: stub_service

    files = {
        "file": ("sample.wav", b"fake-bytes", "audio/wav"),
        "action": (None, "transcribe"),
        "category": (None, "speech"),
        "user_input": (None, json.dumps({"prompt": "Hello"})),
        "user_settings": (None, json.dumps({"speech": {"model": "gpt-4o-transcribe"}})),
        "customer_id": (None, "1"),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files=files,
            headers={"Authorization": f"Bearer {auth_token_factory()}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 200
    assert payload["success"] is True
    assert payload["data"]["status"] == "completed"
    assert payload["data"]["result"] == "Stub transcript"
    assert payload["data"]["action"] == "transcribe"
    assert payload["meta"]["filename"] == "sample.wav"


@pytest.mark.anyio
async def test_transcribe_audio_requires_authorization() -> None:
    files = {
        "file": ("sample.wav", b"fake-bytes", "audio/wav"),
        "action": (None, "transcribe"),
        "category": (None, "speech"),
        "user_input": (None, json.dumps({})),
        "user_settings": (None, json.dumps({})),
        "customer_id": (None, "1"),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files=files,
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["success"] is False
    assert payload["data"]["reason"] == "token_missing"


@pytest.mark.anyio
async def test_transcribe_audio_rejects_invalid_token() -> None:
    files = {
        "file": ("sample.wav", b"fake-bytes", "audio/wav"),
        "action": (None, "transcribe"),
        "category": (None, "speech"),
        "user_input": (None, json.dumps({})),
        "user_settings": (None, json.dumps({})),
        "customer_id": (None, "1"),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files=files,
            headers={"Authorization": "Bearer invalid"},
        )

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == 401
    assert payload["success"] is False
    assert payload["data"]["reason"] == "token_invalid"


@pytest.mark.anyio
async def test_transcribe_audio_invalid_json_returns_400(
    auth_token_factory: Callable[..., str],
) -> None:
    files = {
        "file": ("sample.wav", b"fake-bytes", "audio/wav"),
        "action": (None, "transcribe"),
        "category": (None, "speech"),
        "user_input": (None, "not-json"),
        "user_settings": (None, json.dumps({})),
        "customer_id": (None, "1"),
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/audio/transcribe",
            files=files,
            headers={"Authorization": f"Bearer {auth_token_factory()}"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == 400
    assert payload["success"] is False
    assert payload["data"]["errors"]
