"""Tests for provider base interfaces."""

import pytest

import pytest

from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import BaseImageProvider, BaseTextProvider


@pytest.fixture
def anyio_backend() -> str:
    """Limit async tests to the asyncio backend."""

    return "asyncio"


class FakeTextProvider(BaseTextProvider):
    """Simple fake provider for testing."""

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=True, reasoning=False)

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        return ProviderResponse(text=f"Response to: {prompt}", model="fake-model", provider="fake")

    async def stream(self, prompt: str, **kwargs):  # type: ignore[override]
        for word in ["Hello", " ", "world"]:
            yield word


class FakeImageProvider(BaseImageProvider):
    """Fake image provider implementation."""

    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, prompt: str, **kwargs) -> bytes:  # type: ignore[override]
        return b"image-bytes"


@pytest.mark.anyio("asyncio")
async def test_base_provider_generate() -> None:
    """Text providers should generate a response."""

    provider = FakeTextProvider()
    response = await provider.generate("test prompt")

    assert response.text == "Response to: test prompt"
    assert response.provider == "fake"


@pytest.mark.anyio("asyncio")
async def test_base_provider_stream() -> None:
    """Streaming providers should yield chunks."""

    provider = FakeTextProvider()
    chunks = []

    async for chunk in provider.stream("test"):
        chunks.append(chunk)

    assert "".join(chunks) == "Hello world"


@pytest.mark.anyio("asyncio")
async def test_unsupported_reasoning() -> None:
    """Providers without reasoning should raise NotImplementedError."""

    provider = FakeTextProvider()

    with pytest.raises(NotImplementedError):
        await provider.generate_with_reasoning("test")


@pytest.mark.anyio("asyncio")
async def test_image_provider_generate() -> None:
    """Image providers must return bytes."""

    provider = FakeImageProvider()
    result = await provider.generate("prompt")

    assert isinstance(result, bytes)


@pytest.mark.anyio("asyncio")
async def test_generate_with_audio_not_supported() -> None:
    """Audio input without capability should raise."""

    provider = FakeTextProvider()

    with pytest.raises(NotImplementedError):
        await provider.generate_with_audio(b'data')
