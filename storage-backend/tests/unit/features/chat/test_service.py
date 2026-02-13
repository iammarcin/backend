import asyncio
from typing import Any, AsyncIterator

import pytest

from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseTextProvider
from core.providers.factory import register_text_provider
from core.streaming.manager import StreamingManager
from features.chat.service import ChatService
from core.exceptions import ValidationError


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    """Limit AnyIO to the asyncio backend for these tests."""

    return "asyncio"


class StubTextProvider(BaseTextProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True)

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> ProviderResponse:
        return ProviderResponse(
            text=f"echo:{prompt}",
            model=model or "gpt-4o-mini",
            provider="stub",
        )

    async def stream(
        self,
        prompt: str,
        model: str | None = None,
        *,
        runtime: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        for chunk in ["hello", " ", "world"]:
            yield chunk


@pytest.fixture(autouse=True)
def register_stub_provider():
    from core.providers.registries import _text_providers

    original = _text_providers.get("openai")
    register_text_provider("openai", StubTextProvider)
    try:
        yield
    finally:
        if original:
            _text_providers["openai"] = original
        else:
            _text_providers.pop("openai", None)


async def test_stream_response_sends_chunks():
    service = ChatService()
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(queue)
    token = manager.create_completion_token()

    result = await service.stream_response(
        prompt="Hi",
        settings={"text": {"model": "gpt-4o-mini"}},
        customer_id=1,
        manager=manager,
    )

    await manager.signal_completion(token=token)

    received = []
    while True:
        item = await queue.get()
        if item is None:
            break
        if isinstance(item, dict) and item.get("type") == "text_chunk":
            received.append(item["content"])

    assert "".join(received) == "hello world"
    assert manager.get_results()["text"] == "hello world"
    assert result["text_response"] == "hello world"


async def test_generate_response_returns_text():
    service = ChatService()

    response = await service.generate_response(
        prompt="Hi",
        settings={"text": {"model": "gpt-4o-mini"}},
        customer_id=1,
    )

    assert response.text == "echo:Hi"
    assert response.provider == "stub"
    assert response.requires_tool_action is False
    assert response.tool_calls in (None, [])


async def test_stream_response_validates_prompt():
    service = ChatService()
    manager = StreamingManager()
    manager.add_queue(asyncio.Queue())

    with pytest.raises(ValidationError):
        await service.stream_response(
            prompt=" ",
            settings={},
            customer_id=1,
            manager=manager,
        )
