import types
from types import SimpleNamespace

import pytest

from core.providers.audio.base import SpeechProviderRequest
from core.providers.audio.gemini import GeminiSpeechProvider
from core.providers.audio.openai import OpenAISpeechProvider


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _DummyCall:
    def __init__(self, text: str):
        self.calls: list[dict] = []
        self._text = text

    async def create(self, **payload):
        self.calls.append(payload)
        return SimpleNamespace(text=self._text)


async def test_openai_transcribe_forwards_payload(monkeypatch):
    provider = OpenAISpeechProvider()
    transcriptions = _DummyCall(text="hello world")
    translations = _DummyCall(text="ignored")
    dummy_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions, translations=translations))

    monkeypatch.setattr(
        "core.providers.audio.openai.get_openai_async_client", lambda: dummy_client
    )

    request = SpeechProviderRequest(
        file_bytes=b"pcm-data",
        filename="clip.wav",
        language="en",
        temperature=0.4,
        response_format="text",
        prompt="hint",
    )

    result = await provider.transcribe_file(request)

    assert result.text == "hello world"
    assert result.provider == "openai"
    assert transcriptions.calls[0]["model"] == "gpt-4o-transcribe"
    assert transcriptions.calls[0]["language"] == "en"
    assert transcriptions.calls[0]["prompt"] == "hint"
    assert "response_format" in transcriptions.calls[0]


async def test_openai_translate_uses_translation_endpoint(monkeypatch):
    provider = OpenAISpeechProvider()
    transcriptions = _DummyCall(text="ignored")
    translations = _DummyCall(text="hola mundo")
    dummy_client = SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions, translations=translations))

    monkeypatch.setattr(
        "core.providers.audio.openai.get_openai_async_client", lambda: dummy_client
    )

    request = SpeechProviderRequest(file_bytes=b"pcm", response_format="text")

    result = await provider.translate_file(request)

    assert result.text == "hola mundo"
    assert translations.calls[0]["model"] == "gpt-4o-transcribe"
    assert "language" not in translations.calls[0]


async def test_gemini_transcribe_generates_prompt(monkeypatch):
    provider = GeminiSpeechProvider()
    calls: list[dict] = []

    class DummyModels:
        def generate_content(self, **payload):
            calls.append(payload)
            return SimpleNamespace(text="gemini text")

    dummy_client = SimpleNamespace(models=DummyModels())

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "core.providers.audio.gemini.get_gemini_client", lambda: dummy_client
    )
    monkeypatch.setattr(
        "core.providers.audio.gemini.asyncio.to_thread", immediate_to_thread
    )

    request = SpeechProviderRequest(file_bytes=b"pcm", language="en", prompt=None)

    result = await provider.transcribe_file(request)

    assert result.text == "gemini text"
    assert "Generate a transcript" in calls[0]["contents"][0]
    assert result.provider == "gemini"


async def test_gemini_translate_overrides_prompt(monkeypatch):
    provider = GeminiSpeechProvider()
    calls: list[dict] = []

    class DummyModels:
        def generate_content(self, **payload):
            calls.append(payload)
            return SimpleNamespace(text="translated")

    dummy_client = SimpleNamespace(models=DummyModels())

    async def immediate_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "core.providers.audio.gemini.get_gemini_client", lambda: dummy_client
    )
    monkeypatch.setattr(
        "core.providers.audio.gemini.asyncio.to_thread", immediate_to_thread
    )

    request = SpeechProviderRequest(file_bytes=b"pcm", language="es")

    result = await provider.translate_file(request)

    assert result.text == "translated"
    assert "Translate the provided audio" in calls[0]["contents"][0]
