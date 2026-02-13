import base64
from types import SimpleNamespace
from typing import Any

import base64
from types import SimpleNamespace
from typing import Any

import pytest

from core.clients.ai import ai_clients
from core.exceptions import ProviderError
from core.providers.image.openai import OpenAIImageProvider
from core.providers.image.stability import StabilityImageProvider
from core.providers.image.xai import XaiImageProvider


@pytest.fixture
def anyio_backend() -> str:
    """Restrict async tests to the asyncio backend."""

    return "asyncio"


@pytest.fixture
def mock_openai_image_client():
    payload = base64.b64encode(b"img-bytes").decode()

    class Recorder:
        def __init__(self) -> None:
            self.last_kwargs: dict[str, Any] | None = None
            self.image_b64 = payload

        def generate(self, **kwargs: Any):
            self.last_kwargs = kwargs
            return SimpleNamespace(data=[SimpleNamespace(b64_json=self.image_b64)])

    recorder = Recorder()

    # Create responses API support for new provider implementation (must be async)
    async def mock_responses_create(**kwargs):
        recorder.last_kwargs = kwargs  # Track kwargs from responses API too
        return SimpleNamespace(
            id="resp_mock_123",
            result=SimpleNamespace(b64_json=payload)
        )

    async def mock_responses_retrieve(response_id: str):
        """Mock Responses API retrieve - returns completed status immediately."""
        return SimpleNamespace(
            id=response_id,
            status="completed",
            output=[SimpleNamespace(
                type="image",
                image=SimpleNamespace(b64_json=payload)
            )]
        )

    async def mock_responses_cancel(response_id: str):
        """Mock Responses API cancel - no-op for testing."""
        return SimpleNamespace(id=response_id, status="cancelled")

    responses = SimpleNamespace()
    responses.create = mock_responses_create
    responses.retrieve = mock_responses_retrieve
    responses.cancel = mock_responses_cancel

    client = SimpleNamespace(images=recorder, responses=responses)
    original = ai_clients.get("openai")
    ai_clients["openai"] = client
    try:
        yield recorder
    finally:
        if original is None:
            ai_clients.pop("openai", None)
        else:
            ai_clients["openai"] = original


@pytest.mark.anyio("asyncio")
async def test_openai_quality_standard_maps_to_medium(mock_openai_image_client):
    provider = OpenAIImageProvider()

    # Use dall-e-3 (legacy path, not Responses API) to test quality mapping
    result = await provider.generate(prompt="Hello world", width=256, height=256, quality="standard", model="dall-e-3")

    kwargs = mock_openai_image_client.last_kwargs
    assert kwargs is not None
    assert kwargs["size"] == "256x256"
    assert kwargs["quality"] == "medium"
    assert kwargs["response_format"] == "b64_json"
    expected_bytes = base64.b64decode(mock_openai_image_client.image_b64)
    assert result == expected_bytes


class RecordingAsyncClient:
    def __init__(self, response):
        self.response = response
        self.last_post_kwargs: dict[str, Any] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, **kwargs: Any):
        self.last_post_kwargs = kwargs
        return self.response

    async def get(self, url: str, **kwargs: Any):
        return self.response


@pytest.mark.anyio("asyncio")
async def test_stability_provider_uses_multipart(monkeypatch):
    monkeypatch.setenv("STABILITY_API_KEY", "test-key")

    class Response:
        status_code = 200
        headers = {"content-type": "image/png"}
        content = b"png-data"

        def json(self):
            return {}

    client = RecordingAsyncClient(Response())
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: client)

    provider = StabilityImageProvider()
    result = await provider.generate(prompt="Test prompt")

    assert result == b"png-data"
    assert client.last_post_kwargs is not None
    files = client.last_post_kwargs["files"]
    assert files["prompt"][1] == "Test prompt"
    assert files["width"][1] == "1024"
    assert files["height"][1] == "1024"


class RecordingXaiClient:
    def __init__(self):
        self.last_json: dict[str, Any] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, **kwargs: Any):
        self.last_json = kwargs["json"]

        class Response:
            status_code = 200

            def json(self):
                return {
                    "data": [
                        {"b64_json": base64.b64encode(b"payload").decode()},
                    ]
                }

        return Response()

    async def get(self, url: str, **kwargs: Any):
        raise AssertionError("Unexpected GET request in xAI test")


@pytest.mark.anyio("asyncio")
async def test_xai_provider_uses_width_height(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "secret")
    client = RecordingXaiClient()
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: client)

    provider = XaiImageProvider()
    result = await provider.generate(prompt="Example", width=768, height=512, quality="medium")

    payload = client.last_json
    assert payload is not None
    assert payload["width"] == 768
    assert payload["height"] == 512
    assert payload["response_format"] == "b64_json"
    assert "quality" not in payload
    assert provider.last_quality == "medium"
    assert result == b"payload"


@pytest.mark.anyio("asyncio")
async def test_xai_provider_rejects_empty_prompt(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "secret")
    client = RecordingXaiClient()
    monkeypatch.setattr("httpx.AsyncClient", lambda *args, **kwargs: client)

    provider = XaiImageProvider()

    with pytest.raises(ProviderError):
        await provider.generate(prompt="")
