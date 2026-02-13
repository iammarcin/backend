import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.text.openai import OpenAITextProvider


@pytest.fixture
def anyio_backend() -> str:
    """Execute async OpenAI provider tests on the asyncio backend."""

    return "asyncio"


@pytest.fixture
def mock_openai_client():
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()

    ai_clients["openai_async"] = client
    try:
        yield client
    finally:
        ai_clients.pop("openai_async", None)


@pytest.mark.anyio("asyncio")
async def test_openai_generate(mock_openai_client):
    mock_response = Mock()
    mock_choice = Mock()
    mock_message = Mock()
    mock_message.content = "Test response"
    mock_message.reasoning_content = None
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"
    mock_response.choices = [mock_choice]
    mock_response.usage = None

    mock_openai_client.chat.completions.create.return_value = mock_response

    provider = OpenAITextProvider()

    response = await provider.generate(prompt="Hello", model="gpt-4o-mini")

    assert response.text == "Test response"
    assert response.provider == "openai"
    assert response.model == "gpt-4o-mini"
    mock_openai_client.chat.completions.create.assert_awaited_once()


@pytest.mark.anyio("asyncio")
async def test_openai_stream(mock_openai_client):
    async def mock_stream():
        for chunk_text in ["Hello", " ", "world"]:
            chunk = Mock()
            delta = Mock()
            delta.content = chunk_text
            delta.reasoning_content = None
            choice = Mock()
            choice.delta = delta
            chunk.choices = [choice]
            yield chunk

    mock_openai_client.chat.completions.create.return_value = mock_stream()

    provider = OpenAITextProvider()

    chunks = []
    async for chunk in provider.stream(prompt="Test"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello world"


@pytest.mark.anyio("asyncio")
async def test_openai_error_handling(mock_openai_client):
    mock_openai_client.chat.completions.create.side_effect = Exception("API error")

    provider = OpenAITextProvider()

    with pytest.raises(ProviderError) as exc:
        await provider.generate(prompt="Hello")

    assert "API error" in str(exc.value)
