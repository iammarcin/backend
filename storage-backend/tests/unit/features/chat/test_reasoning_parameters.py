"""Reasoning configuration parameter handling tests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from unittest.mock import AsyncMock, patch

import pytest

from core.providers.registry.model_config import ModelConfig
from core.pydantic_schemas import ProviderResponse
from features.chat.services.streaming.standard_provider import (
    stream_standard_response,
)
from features.chat.services.streaming.non_streaming import generate_response
from features.chat.utils.prompt_utils import PromptContext


def _async_iterable(chunks: Iterable[str]):
    """Return an async iterator that yields the provided chunks."""

    async def _iterator():
        for item in chunks:
            yield item

    return _iterator()


class _StubStreamingManager:
    """Minimal streaming manager stub collecting streamed messages."""

    def __init__(self) -> None:
        self.sent_messages: List[Dict[str, Any]] = []
        self.collected: List[tuple[str, str]] = []
        self.tool_calls: List[Dict[str, Any]] = []

    async def send_to_queues(
        self, payload: Dict[str, Any], queue_type: str = "all"
    ) -> None:
        payload = dict(payload)
        payload["queue_type"] = queue_type
        self.sent_messages.append(payload)

    def collect_chunk(self, chunk: str, chunk_type: str) -> None:
        self.collected.append((chunk, chunk_type))

    def collect_tool_call(self, payload: Dict[str, Any]) -> None:
        self.tool_calls.append(payload)


@pytest.mark.anyio
async def test_streaming_filters_reasoning_params_when_not_supported() -> None:
    """Providers without reasoning support must not receive reasoning kwargs."""

    model_config = ModelConfig(model_name="llama", provider_name="groq")

    class _StubProvider:
        provider_name = "groq"

        def __init__(self) -> None:
            self._chunks = ["chunk"]
            self.stream_call_kwargs: Optional[Dict[str, Any]] = None

        def get_model_config(self) -> ModelConfig:
            return model_config

        async def stream(self, **kwargs: Any):
            self.stream_call_kwargs = dict(kwargs)
            for item in self._chunks:
                yield item

    provider = _StubProvider()
    manager = _StubStreamingManager()

    outcome = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="hello",
        model="llama",
        temperature=0.2,
        max_tokens=64,
        system_prompt=None,
        messages=[{"role": "user", "content": "hello"}],
        settings={"text": {"enable_reasoning": True}},
    )

    assert outcome.text_chunks == ["chunk"]
    assert outcome.reasoning_chunks == []
    assert outcome.tool_calls == []
    assert provider.stream_call_kwargs is not None
    assert "enable_reasoning" not in provider.stream_call_kwargs
    assert "reasoning_value" not in provider.stream_call_kwargs


@pytest.mark.anyio
async def test_streaming_includes_reasoning_params_when_supported() -> None:
    """Reasoning capable providers should receive the mapped configuration."""

    model_config = ModelConfig(
        model_name="gpt-5-mini",
        provider_name="openai",
        is_reasoning_model=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
    )

    class _StubProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self._chunks = ["chunk"]
            self.stream_call_kwargs: Optional[Dict[str, Any]] = None

        def get_model_config(self) -> ModelConfig:
            return model_config

        async def stream(self, **kwargs: Any):
            self.stream_call_kwargs = dict(kwargs)
            for item in self._chunks:
                yield item

    provider = _StubProvider()
    manager = _StubStreamingManager()

    outcome = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="Solve",
        model="gpt-5-mini",
        temperature=0.2,
        max_tokens=256,
        system_prompt=None,
        messages=[{"role": "user", "content": "Solve"}],
        settings={"text": {"enable_reasoning": True, "reasoning_effort": 1}},
    )

    assert outcome.text_chunks == ["chunk"]
    assert outcome.reasoning_chunks == []
    assert outcome.tool_calls == []
    assert provider.stream_call_kwargs is not None
    assert provider.stream_call_kwargs["enable_reasoning"] is True
    assert provider.stream_call_kwargs["reasoning_value"] == "medium"


@pytest.mark.anyio
async def test_streaming_collects_reasoning_chunks() -> None:
    """Reasoning chunks should be forwarded to frontend-only queues."""

    model_config = ModelConfig(
        model_name="gpt-5-mini",
        provider_name="openai",
        is_reasoning_model=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
    )

    class _ReasoningProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self._chunks: List[Any] = [
                {"type": "reasoning", "content": "Thinking"},
                "Final answer",
            ]

        def get_model_config(self) -> ModelConfig:
            return model_config

        async def stream(self, **_: Any):
            for item in self._chunks:
                yield item

    provider = _ReasoningProvider()
    manager = _StubStreamingManager()

    outcome = await stream_standard_response(
        provider=provider,
        manager=manager,
        prompt_text="Solve",
        model="gpt-5-mini",
        temperature=0.2,
        max_tokens=256,
        system_prompt=None,
        messages=[{"role": "user", "content": "Solve"}],
        settings={"text": {"enable_reasoning": True}},
    )

    assert outcome.text_chunks == ["Final answer"]
    assert outcome.reasoning_chunks == ["Thinking"]
    assert outcome.tool_calls == []
    assert manager.collected == [("Thinking", "reasoning"), ("Final answer", "text")]
    # Reasoning events now use thinking_chunk format
    assert manager.sent_messages[0]["type"] == "thinking_chunk"
    assert manager.sent_messages[0]["data"]["content"] == "Thinking"
    assert manager.sent_messages[0]["queue_type"] == "frontend_only"
    assert manager.sent_messages[1] == {
        "type": "text_chunk",
        "content": "Final answer",
        "queue_type": "all",
    }


@pytest.mark.anyio
async def test_non_streaming_filters_reasoning_params_when_not_supported() -> None:
    """Non-streaming calls should also drop unsupported reasoning kwargs."""

    model_config = ModelConfig(model_name="llama", provider_name="groq")

    class _StubProvider:
        provider_name = "groq"

        def __init__(self) -> None:
            self.generate = AsyncMock(
                return_value=ProviderResponse(text="ok", model="llama", provider="groq")
            )

        def get_model_config(self) -> ModelConfig:
            return model_config

    provider = _StubProvider()

    with patch(
        "features.chat.services.streaming.non_streaming.resolve_prompt_and_provider",
        return_value=(
            PromptContext(text_prompt="hello", image_mode=None, input_image_url=None),
            provider,
            "llama",
            0.1,
            128,
        ),
    ):
        response = await generate_response(
            prompt="hello",
            settings={"text": {"enable_reasoning": True}},
            customer_id=1,
        )

    assert response.text == "ok"
    call_kwargs = provider.generate.call_args.kwargs
    assert "enable_reasoning" not in call_kwargs
    assert "reasoning_value" not in call_kwargs


@pytest.mark.anyio
async def test_non_streaming_includes_reasoning_params_when_supported() -> None:
    """Supported providers should receive the reasoning configuration."""

    model_config = ModelConfig(
        model_name="gpt-5-mini",
        provider_name="openai",
        is_reasoning_model=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
    )

    class _StubProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self.generate = AsyncMock(
                return_value=ProviderResponse(text="ok", model="o3-mini", provider="openai")
            )

        def get_model_config(self) -> ModelConfig:
            return model_config

    provider = _StubProvider()

    with patch(
        "features.chat.services.streaming.non_streaming.resolve_prompt_and_provider",
        return_value=(
            PromptContext(text_prompt="solve", image_mode=None, input_image_url=None),
            provider,
            "gpt-5-mini",
            0.1,
            128,
        ),
    ):
        response = await generate_response(
            prompt="solve",
            settings={"text": {"enable_reasoning": True, "reasoning_effort": 1}},
            customer_id=1,
        )

    assert response.text == "ok"
    call_kwargs = provider.generate.call_args.kwargs
    assert call_kwargs["enable_reasoning"] is True
    assert call_kwargs["reasoning_value"] == "medium"
