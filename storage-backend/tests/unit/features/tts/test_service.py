import asyncio
import base64

import pytest

from core.exceptions import ProviderError
from core.streaming.manager import StreamingManager
from core.providers.tts_base import TTSRequest, TTSResult
from features.tts.schemas.requests import (
    TTSAction,
    TTSGenerateRequest,
    TTSGeneralSettings,
    TTSProviderSettings,
    TTSUserInput,
    TTSUserSettings,
)
from features.tts.service import TTSService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeProvider:
    name = "fake"

    def __init__(self) -> None:
        self.calls: list[TTSRequest] = []
        self.stream_calls: list[TTSRequest] = []
        self.billing_payload = {
            "character_count": 123,
            "character_limit": 456,
            "next_billing_date": "2024-01-01T00:00:00+00:00",
        }

    def get_websocket_format(self) -> str:
        return "pcm"

    async def generate(self, request: TTSRequest) -> TTSResult:
        self.calls.append(request)
        payload = f"chunk-{request.chunk_index}".encode()
        return TTSResult(
            audio_bytes=payload,
            provider=self.name,
            model=request.model or "gpt-4o-mini-tts",
            format=request.format or "pcm",
            voice=request.voice,
            metadata={"chunk_index": request.chunk_index},
        )

    async def stream(self, request: TTSRequest):
        self.stream_calls.append(request)
        for index in range(2):
            yield f"audio-{request.chunk_index}-{index}".encode()

    async def get_billing(self) -> dict[str, object]:
        return self.billing_payload


class FakeStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[bytes, int, str, str | None]] = []

    async def upload_audio(
        self,
        *,
        audio_bytes: bytes,
        customer_id: int,
        file_extension: str,
        content_type: str | None = None,
    ) -> str:
        self.uploads.append((audio_bytes, customer_id, file_extension, content_type))
        return f"https://s3.example/{customer_id}/tts.{file_extension}"


def test_generate_uses_provider_and_uploads_audio():
    provider = FakeProvider()
    storage = FakeStorage()

    service = TTSService(
        provider_resolver=lambda _: provider,
        storage_service_factory=lambda: storage,
    )

    text = "hello " * 900  # ensures chunking across the 4096 char limit
    request = TTSGenerateRequest(
        action=TTSAction.TTS_NO_STREAM,
        user_input=TTSUserInput(text=text),
        user_settings=TTSUserSettings(
            general=TTSGeneralSettings(),
            tts=TTSProviderSettings(model="gpt-4o-mini-tts", format="pcm"),
        ),
        customer_id=42,
    )

    result = asyncio.run(service.generate(request))

    assert len(provider.calls) >= 1
    assert storage.uploads[0][1] == 42
    assert storage.uploads[0][2] == "wav"
    assert storage.uploads[0][3] == "audio/wav"
    assert result.result.startswith("https://s3.example/42/")
    assert result.metadata["provider"] == "fake"
    assert result.metadata["chunk_count"] == len(provider.calls)
    assert result.metadata["format"] == "wav"
    assert result.metadata.get("original_format") == "pcm"


def test_generate_inline_payload_when_s3_disabled():
    provider = FakeProvider()
    storage = FakeStorage()

    service = TTSService(
        provider_resolver=lambda _: provider,
        storage_service_factory=lambda: storage,
    )

    request = TTSGenerateRequest(
        action=TTSAction.TTS_NO_STREAM,
        user_input=TTSUserInput(text="short text"),
        user_settings=TTSUserSettings(
            general=TTSGeneralSettings(save_to_s3=False),
            tts=TTSProviderSettings(model="gpt-4o-mini-tts", format="pcm"),
        ),
        customer_id=5,
    )

    result = asyncio.run(service.generate(request))

    assert result.result.startswith("data:audio/wav;base64,")
    assert "inline_payload_bytes" in result.metadata["extra"]
    assert result.metadata.get("original_format") == "pcm"
    assert not storage.uploads


def test_generate_returns_test_data_when_requested():
    provider = FakeProvider()

    service = TTSService(provider_resolver=lambda _: provider, storage_service_factory=FakeStorage)

    request = TTSGenerateRequest(
        action=TTSAction.TTS_NO_STREAM,
        user_input=TTSUserInput(text="ignored"),
        user_settings=TTSUserSettings(
            general=TTSGeneralSettings(return_test_data=True),
            tts=TTSProviderSettings(),
        ),
        customer_id=7,
    )

    result = asyncio.run(service.generate(request))

    assert result.provider == "test-data"
    assert result.metadata["extra"]["mode"] == "test"
    assert result.result.endswith(".mp3")


def test_get_billing_returns_provider_payload():
    provider = FakeProvider()
    service = TTSService(provider_resolver=lambda _: provider, storage_service_factory=FakeStorage)

    settings = TTSUserSettings(general=TTSGeneralSettings(), tts=TTSProviderSettings(provider="elevenlabs"))

    result = asyncio.run(service.get_billing(settings))

    assert result.result == provider.billing_payload
    assert result.status == "completed"


@pytest.mark.anyio("asyncio")
async def test_stream_text_emits_audio_events() -> None:
    """Verify streaming events without asserting on completion ownership."""

    provider = FakeProvider()
    service = TTSService(provider_resolver=lambda _: provider, storage_service_factory=FakeStorage)
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(queue)

    settings = TTSUserSettings(
        general=TTSGeneralSettings(save_to_s3=False),
        tts=TTSProviderSettings(model="gpt-4o-mini-tts", format="mp3", streaming=True, tts_auto_execute=True),
    )
    timings: dict[str, float] = {}

    metadata = await service.stream_text(
        text="hello world",
        customer_id=9,
        user_settings=settings,
        manager=manager,
        timings=timings,
    )

    raw_items: list[object] = []
    while not queue.empty():
        raw_items.append(await queue.get())

    events: list[dict[str, object]] = [item for item in raw_items if isinstance(item, dict)]

    # Verify event types - using standardized simple format (no custom_event wrapper)
    event_types = [event.get("type") for event in events]
    assert "tts_started" in event_types
    assert "audio_chunk" in event_types
    assert "tts_completed" in event_types
    assert "tts_file_uploaded" in event_types

    expected_chunks = [
        base64.b64encode(f"audio-1-0".encode()).decode(),
        base64.b64encode(f"audio-1-1".encode()).decode(),
    ]
    assert manager.results["audio_chunks"] == expected_chunks
    assert metadata.audio_chunk_count == len(expected_chunks)
    assert "tts_first_response_time" in timings
    assert metadata.audio_file_url is not None
    assert metadata.audio_file_url.startswith("data:audio/")
    assert metadata.storage_metadata is not None


class FailingStreamProvider(FakeProvider):
    def get_websocket_format(self) -> str:
        return "pcm"

    async def stream(self, request: TTSRequest):  # type: ignore[override]
        self.stream_calls.append(request)
        yield b"partial-chunk"
        raise ProviderError("boom", provider=self.name)


@pytest.mark.anyio("asyncio")
async def test_stream_text_propagates_provider_error() -> None:
    """Provider errors should propagate without services signalling completion."""

    provider = FailingStreamProvider()
    service = TTSService(provider_resolver=lambda _: provider, storage_service_factory=FakeStorage)
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(queue)

    settings = TTSUserSettings(
        general=TTSGeneralSettings(save_to_s3=False),
        tts=TTSProviderSettings(model="gpt-4o-mini-tts", format="mp3", streaming=True, tts_auto_execute=True),
    )

    with pytest.raises(ProviderError, match="boom"):
        await service.stream_text(
            text="boom",
            customer_id=1,
            user_settings=settings,
            manager=manager,
            timings={},
        )

    observed: list[object] = []
    while not queue.empty():
        observed.append(await queue.get())

    assert observed, "expected events to be emitted"

    event_types = [
        event.get("type")
        for event in observed
        if isinstance(event, dict)
    ]
    assert "tts_started" in event_types
    assert "tts_error" in event_types

    assert observed[-1] is not None


@pytest.mark.anyio("asyncio")
async def test_stream_http_returns_iterator() -> None:
    provider = FakeProvider()
    service = TTSService(provider_resolver=lambda _: provider, storage_service_factory=FakeStorage)

    request = TTSGenerateRequest(
        action=TTSAction.TTS_STREAM,
        user_input=TTSUserInput(text="sample text"),
        user_settings=TTSUserSettings(
            general=TTSGeneralSettings(save_to_s3=False),
            tts=TTSProviderSettings(model="gpt-4o-mini-tts", format="mp3", streaming=True, tts_auto_execute=True),
        ),
        customer_id=3,
    )

    media_type, iterator, metadata = await service.stream_http(request)

    assert media_type == "audio/mpeg"
    assert metadata["provider"] == "fake"

    chunks = [chunk async for chunk in iterator]
    assert chunks  # ensure audio yielded
