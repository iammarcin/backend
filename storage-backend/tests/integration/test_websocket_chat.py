"""Integration tests for the WebSocket chat endpoint."""

from __future__ import annotations

import base64
from typing import AsyncIterator
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider
from core.providers.factory import register_text_provider
import features.chat.service_impl as chat_service_impl
from features.tts.service import TTSStreamingMetadata


class IntegrationStubProvider(BaseTextProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True)

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs,
    ) -> ProviderResponse:
        return ProviderResponse(text="integration", model=model or "stub", provider="stub")

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        runtime=None,
        **kwargs,
    ) -> AsyncIterator[str]:
        for chunk in ["Hello", " ", "world"]:
            yield chunk


@pytest.fixture(autouse=True)
def override_provider():
    from core.providers.registries import _text_providers

    original = _text_providers.get("openai")
    register_text_provider("openai", IntegrationStubProvider)
    try:
        yield
    finally:
        if original:
            _text_providers["openai"] = original
        else:
            _text_providers.pop("openai", None)

def _build_ws_url(token: str, **params: object) -> str:
    query = {"token": token}
    query.update({key: value for key, value in params.items() if value is not None})
    return "/chat/ws?" + urlencode(query)


@pytest.mark.skip(
    reason="after implementing websockets cancelltion this stopped working. so we build dedicated out of docker container tests - with requires_docker flag"
    "See tests/live_api/test_websocket_comprehensive.py::test_basic_chat_flow_with_streaming"
)
def test_websocket_chat(
    chat_test_client: TestClient, auth_token_factory
) -> None:
    with chat_test_client.websocket_connect(_build_ws_url(auth_token_factory())) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "websocket_ready"

        websocket.send_json(
            {
                "prompt": "Say hello",
                "settings": {"text": {"model": "gpt-4o-mini", "temperature": 0.1}},
            }
        )

        chunks: list[str] = []
        while True:
            data = websocket.receive_json()
            if data["type"] == "text_completed":
                break
            if data["type"] == "text_chunk":
                chunks.append(data["content"])
            if data["type"] == "error":
                pytest.fail(f"Received error: {data['content']}")

        assert "".join(chunks) == "Hello world"


def test_websocket_validation_error(
    chat_test_client: TestClient, auth_token_factory
) -> None:
    with chat_test_client.websocket_connect(_build_ws_url(auth_token_factory())) as websocket:
        websocket.receive_json()
        websocket.send_json({"settings": {}})
        try:
            data = websocket.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code in {1000, 1002}
            return
        assert data["type"] == "error"
        assert "prompt" in data["content"].lower() or "required" in data["content"].lower()

@pytest.mark.skip("after implementing websockets cancelltion this stopped working. so we build dedicated out of docker container tests - with requires_docker flag")
def test_websocket_chat_with_tts_events(
    monkeypatch, chat_test_client: TestClient, auth_token_factory
):

    class StubTTSService:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def stream_text(
            self,
            *,
            text: str,
            customer_id: int,
            user_settings,
            manager,
            timings,
        ) -> TTSStreamingMetadata:
            self.calls.append(text)
            chunk = base64.b64encode(b"stub-audio").decode()
            await manager.send_to_queues(
                {
                    "type": "tts_started",
                    "content": {
                        "provider": "stub",
                        "model": "stub-model",
                        "voice": None,
                        "format": "mp3",
                        "text_chunk_count": 1,
                    },
                }
            )
            manager.collect_chunk(chunk, "audio")
            await manager.send_to_queues({"type": "audio_chunk", "content": chunk})
            await manager.send_to_queues(
                {
                    "type": "tts_generation_completed",
                    "content": {
                        "provider": "stub",
                        "model": "stub-model",
                        "voice": None,
                        "format": "mp3",
                        "audio_chunk_count": 1,
                        "text_chunk_count": 1,
                    },
                }
            )
            await manager.send_to_queues({"type": "tts_completed", "content": ""})
            return TTSStreamingMetadata(
                provider="stub",
                model="stub-model",
                voice=None,
                format="mp3",
                text_chunk_count=1,
                audio_chunk_count=1,
            )

    stub_service = StubTTSService()
    monkeypatch.setattr(chat_service_impl, "TTSService", lambda: stub_service)

    with chat_test_client.websocket_connect(_build_ws_url(auth_token_factory())) as websocket:
        websocket.receive_json()
        websocket.send_json(
            {
                "prompt": "Provide narration",
                "settings": {
                    "text": {"model": "gpt-4o-mini"},
                    "tts": {
                        "model": "gpt-4o-mini-tts",
                        "format": "mp3",
                        "streaming": True,
                        "tts_auto_execute": True,
                    },
                },
            }
        )

        audio_events: list[dict[str, object]] = []
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            data = websocket.receive_json()
            if data["type"] == "text_completed":
                text_completed = True
            elif data["type"] in ("tts_completed", "tts_not_requested"):
                tts_completed = True
            if data["type"] == "audio":
                audio_events.append(data)

    assert audio_events
    assert audio_events[0]["content"] == base64.b64encode(b"stub-audio").decode()


def test_websocket_rejects_missing_token(chat_test_client: TestClient) -> None:
    with chat_test_client.websocket_connect("/chat/ws") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_json()
    assert exc.value.code == 4401


def test_websocket_rejects_invalid_token(chat_test_client: TestClient) -> None:
    with chat_test_client.websocket_connect("/chat/ws?token=invalid") as websocket:
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_json()
    assert exc.value.code == 4401
