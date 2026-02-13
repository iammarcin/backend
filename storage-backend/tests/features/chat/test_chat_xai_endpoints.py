from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, ClassVar, Dict, List, Optional
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from core.providers.base import BaseTextProvider
from core.providers.capabilities import ProviderCapabilities
from core.providers.registries import register_text_provider, _text_providers
from core.pydantic_schemas import ProviderResponse
from main import app


@dataclass
class _StubModelConfig:
    model_name: str = "grok-4-latest"
    provider_name: str = "xai"
    supports_temperature: bool = True
    temperature_min: float = 0.0
    temperature_max: float = 1.0
    max_tokens_default: int = 2048
    supports_reasoning_effort: bool = False


class StubXaiProvider(BaseTextProvider):
    """Deterministic provider stub that mimics xAI responses."""

    last_instance: ClassVar[Optional["StubXaiProvider"]] = None

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True, function_calling=True)
        self._model_config = _StubModelConfig()
        self.generate_calls: List[Dict[str, Any]] = []
        self.stream_calls: List[Dict[str, Any]] = []
        StubXaiProvider.last_instance = self

        self._tool_payload = {
            "id": "call-1",
            "type": "function",
            "function": {
                "name": "extract_metadata",
                "arguments": {"city": "Berlin", "attachments": 2},
            },
            "requires_action": True,
        }

    def get_model_config(self):  # noqa: D401 - test helper
        return self._model_config

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 0,
        **kwargs: Any,
    ) -> ProviderResponse:
        self.generate_calls.append({
            "prompt": prompt,
            "model": model,
            **kwargs,
        })
        metadata = {
            "tool_calls": [self._tool_payload],
            "uploaded_file_ids": ["file-abc"],
        }
        return ProviderResponse(
            text="",
            model=model or self._model_config.model_name,
            provider="xai",
            reasoning="Step one",
            metadata=metadata,
        )

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Any]:
        self.stream_calls.append({
            "prompt": prompt,
            "model": model,
            **kwargs,
        })
        yield {"type": "reasoning", "content": "Considering attachments"}
        yield "Partial answer"
        yield {"type": "tool_call", "content": self._tool_payload}


@pytest.fixture(autouse=True)
def register_stub_provider():
    original = _text_providers.get("xai")
    _text_providers["xai"] = StubXaiProvider
    try:
        yield
    finally:
        if original is not None:
            _text_providers["xai"] = original
        else:
            _text_providers.pop("xai", None)
        StubXaiProvider.last_instance = None


def _build_tool_settings() -> Dict[str, Any]:
    return {
        "functions": [
            {
                "name": "extract_metadata",
                "description": "Summarise uploaded artefacts",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "attachments": {"type": "integer"},
                    },
                },
            }
        ],
        "tool_choice": {"type": "auto"},
    }


def test_chat_endpoint_returns_tool_metadata(authenticated_client):
    payload = {
        "prompt": [
            {"type": "text", "text": "Inspect the attached resources"},
            {"type": "image_url", "image_url": {"url": "https://example.com/diagram.png", "detail": "high"}},
            {"type": "file_url", "file_url": {"url": "https://example.com/notes.pdf", "filename": "notes.pdf"}},
        ],
        "settings": {"text": {"model": "grok-4", "tools": _build_tool_settings()}},
        "customer_id": 1,
    }

    response = authenticated_client.post("/chat/", json=payload)
    assert response.status_code == 200

    data = response.json()["data"]
    assert data["tool_calls"][0]["function"]["name"] == "extract_metadata"
    assert data["metadata"]["uploaded_file_ids"] == ["file-abc"]
    assert data["requires_tool_action"] is True
    assert data["reasoning"] == "Step one"

    stub = StubXaiProvider.last_instance
    assert stub is not None
    assert stub.generate_calls[-1]["tool_settings"] == _build_tool_settings()


@pytest.mark.skip(
    reason="after implementing websockets cancelltion this stopped working. so we build dedicated out of docker container tests - with requires_docker flag"
    "See tests/live_api/test_websocket_comprehensive.py::test_tool_call_event_ordering"
)
def test_websocket_flow_emits_ordered_tool_call_events(auth_token_factory) -> None:
    client = TestClient(app)

    url = "/chat/ws?" + urlencode({"token": auth_token_factory(), "customer_id": 1})

    with client.websocket_connect(url) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "websocket_ready"

        websocket.send_json(
            {
                "prompt": "Summarise the attachments",
                "settings": {"text": {"model": "grok-4", "tools": _build_tool_settings()}},
            }
        )

        events: List[tuple[str, Optional[str]]] = []
        tool_events: List[Dict[str, Any]] = []
        text_completed = False
        tts_completed = False
        while not (text_completed and tts_completed):
            message = websocket.receive_json()
            message_type = message["type"]
            content_type = None
            if isinstance(message.get("content"), dict):
                content_type = message["content"].get("type")
            events.append((message_type, content_type))
            if message_type == "tool_start":
                tool_events.append(message)
            if message_type == "text_completed":
                text_completed = True
            elif message_type in ("tts_completed", "tts_not_requested"):
                tts_completed = True

        filtered_events = [evt for evt in events if evt[0] != "websocket_ready"]
        assert filtered_events[0][0] == "working"
        assert filtered_events[1] == ("custom_event", "aiTextModelInUse")
        assert filtered_events[2] == ("custom_event", "reasoning")
        assert filtered_events[3][0] == "text_chunk"

        event_types = [evt[0] for evt in filtered_events]
        assert "tool_start" in event_types, "Expected a toolCall event in the stream"
        tool_call_index = event_types.index("tool_start")

        assert (
            filtered_events[tool_call_index - 1] == ("custom_event", "toolUse")
        ), "toolUse event should precede the toolCall"
        assert "text_completed" in [evt[0] for evt in filtered_events]

        assert tool_events, "Expected a toolCall event"
        tool_content = tool_events[0].get("content", {})
        if "function" in tool_content:
            function_payload = tool_content["function"]
        else:
            function_payload = (tool_content.get("value") or [{}])[0]["function"]
        assert function_payload["name"] == "extract_metadata"

    stub = StubXaiProvider.last_instance
    assert stub is not None
    assert stub.stream_calls[-1]["tool_settings"] == _build_tool_settings()
