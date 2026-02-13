"""Unit tests covering audio provider resolution logic."""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

import pytest

from core.providers.audio import factory
from core.providers.audio.base import BaseAudioProvider, SpeechProviderRequest, SpeechTranscriptionResult


class DummyDeepgramProvider(BaseAudioProvider):
    """Stub provider representing Deepgram."""

    name = "deepgram"

    async def transcribe_file(self, request: SpeechProviderRequest) -> SpeechTranscriptionResult:
        return SpeechTranscriptionResult(text="", provider=self.name)

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager,
        mode: str = "non-realtime",
    ) -> str:
        return ""


class DummyGeminiProvider(BaseAudioProvider):
    """Stub provider representing Gemini."""

    name = "gemini"

    def configure(self, settings: Mapping[str, Any]) -> None:  # pragma: no cover - no-op for stub
        self._settings = dict(settings)

    async def transcribe_file(self, request: SpeechProviderRequest) -> SpeechTranscriptionResult:
        return SpeechTranscriptionResult(text="", provider=self.name)


@pytest.fixture(autouse=True)
def override_audio_registry():
    """Provide an isolated audio provider registry for each test."""

    original = factory._audio_providers.copy()
    factory._audio_providers.clear()
    factory._audio_providers.update(
        {
            "deepgram": DummyDeepgramProvider,
            "gemini": DummyGeminiProvider,
            "gemini_streaming": DummyGeminiProvider,
        }
    )
    try:
        yield
    finally:
        factory._audio_providers.clear()
        factory._audio_providers.update(original)


def test_static_requests_keep_explicit_deepgram_provider() -> None:
    """Provider selection should respect explicit Deepgram settings for static actions."""

    settings = {"audio": {"provider": "deepgram", "model": "nova-3"}}

    provider = factory.get_audio_provider(settings, action="transcribe")

    assert isinstance(provider, DummyDeepgramProvider)


def test_static_requests_use_deepgram_model_hint() -> None:
    """Model hints targeting Deepgram should not be remapped for static flows."""

    settings = {"audio": {"model": "deepgram-nova-3"}}

    provider = factory.get_audio_provider(settings, action="translate")

    assert isinstance(provider, DummyDeepgramProvider)
