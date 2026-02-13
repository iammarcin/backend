import pytest

from core.exceptions import ProviderError
from core.providers.audio.base import SpeechTranscriptionResult
from features.audio.schemas import (
    AudioAction,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)
from config.audio import (
    DEFAULT_TRANSCRIBE_MODEL,
    DEFAULT_TRANSLATE_MODEL,
)
from features.audio.service import STTService


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class DummyProvider:
    def __init__(self, text: str = "transcript", language: str | None = "en"):
        self.calls: list[tuple[str, object]] = []
        self._text = text
        self._language = language

    async def transcribe_file(self, request):
        self.calls.append(("transcribe", request))
        return SpeechTranscriptionResult(
            text=self._text,
            provider="dummy",
            language=self._language,
            metadata={"model": request.model},
        )

    async def translate_file(self, request):
        self.calls.append(("translate", request))
        return SpeechTranscriptionResult(
            text="translated",
            provider="dummy",
            language="es",
            metadata={"model": request.model},
        )


class DummyManager:
    def __init__(self):
        self.events: list[object] = []

    async def send_to_queues(self, payload, queue_type: str = "all"):
        self.events.append(payload)

    async def signal_completion(self, *, token: str) -> None:
        """Accept completion tokens to mirror StreamingManager."""

        self.events.append({"type": "completion", "token": token})


async def test_transcribe_file_forwards_to_provider(monkeypatch, tmp_path):
    provider = DummyProvider()

    monkeypatch.setattr(
        "features.audio.service.get_audio_provider", lambda settings, action=None: provider
    )

    service = STTService()
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"pcm")

    result = await service.transcribe_file(
        action=AudioAction.TRANSCRIBE,
        customer_id=123,
        file_path=audio_file,
        user_input=StaticTranscriptionUserInput(prompt="hello"),
        user_settings=StaticTranscriptionUserSettings(),
    )

    assert result.result == "transcript"
    assert result.provider == "dummy"
    assert provider.calls[0][0] == "transcribe"
    assert provider.calls[0][1].prompt == "hello"
    assert provider.calls[0][1].model == DEFAULT_TRANSCRIBE_MODEL


async def test_transcribe_file_emits_events(monkeypatch, tmp_path):
    provider = DummyProvider()
    monkeypatch.setattr(
        "features.audio.service.get_audio_provider", lambda settings, action=None: provider
    )

    service = STTService()
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"pcm")
    manager = DummyManager()

    await service.transcribe_file(
        action=AudioAction.TRANSCRIBE,
        customer_id=77,
        file_path=audio_file,
        user_settings=StaticTranscriptionUserSettings(),
        manager=manager,
    )

    assert any(event.get("event_type") == "transcriptionStarted" for event in manager.events if isinstance(event, dict))
    assert any(event.get("event_type") == "transcriptionCompleted" for event in manager.events if isinstance(event, dict))


async def test_transcribe_file_handles_translation(monkeypatch, tmp_path):
    provider = DummyProvider()
    monkeypatch.setattr(
        "features.audio.service.get_audio_provider", lambda settings, action=None: provider
    )

    service = STTService()
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"pcm")

    result = await service.transcribe_file(
        action=AudioAction.TRANSLATE,
        customer_id=1,
        file_path=audio_file,
        user_settings=StaticTranscriptionUserSettings(),
    )

    assert result.language == "es"
    assert provider.calls[0][0] == "translate"
    assert provider.calls[0][1].model == DEFAULT_TRANSLATE_MODEL


async def test_transcribe_file_propagates_provider_error(monkeypatch, tmp_path):
    class FailingProvider:
        async def transcribe_file(self, request):
            raise ProviderError("boom", provider="dummy")

    monkeypatch.setattr(
        "features.audio.service.get_audio_provider", lambda settings, action=None: FailingProvider()
    )

    service = STTService()
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"pcm")

    with pytest.raises(ProviderError):
        await service.transcribe_file(
            action=AudioAction.TRANSCRIBE,
            customer_id=9,
            file_path=audio_file,
            user_settings=StaticTranscriptionUserSettings(),
        )


async def test_transcribe_file_applies_rewrite(monkeypatch, tmp_path):
    provider = DummyProvider(text="cloud coat demo")

    monkeypatch.setattr(
        "features.audio.service.get_audio_provider", lambda settings, action=None: provider
    )

    service = STTService()
    audio_file = tmp_path / "audio.wav"
    audio_file.write_bytes(b"pcm")
    manager = DummyManager()

    result = await service.transcribe_file(
        action=AudioAction.TRANSCRIBE,
        customer_id=42,
        file_path=audio_file,
        user_settings=StaticTranscriptionUserSettings(),
        manager=manager,
    )

    assert result.result == "Claude Code demo"
    completion_events = [
        event
        for event in manager.events
        if isinstance(event, dict)
        and event.get("event_type") == "transcriptionCompleted"
    ]
    assert completion_events
    assert completion_events[0]["content"]["transcript"] == "Claude Code demo"


async def test_transcribe_stream_applies_rewrite(monkeypatch):
    async def fake_transcribe_stream(
        provider_settings,
        *,
        audio_source,
        manager,
        mode,
        completion_token=None,
        transcript_rewriter,
    ):
        assert transcript_rewriter is not None
        return transcript_rewriter("CLOUD CODE sample", {"provider": provider_settings.get("provider"), "mode": mode})

    monkeypatch.setattr(
        "features.audio.service.transcribe_streaming_audio", fake_transcribe_stream
    )

    service = STTService()

    async def dummy_source():
        yield b"chunk"
        return

    manager = DummyManager()
    transcript = await service.transcribe_stream(
        audio_source=dummy_source(),
        manager=manager,
        mode="non-realtime",
    )

    assert transcript == "Claude Code sample"
