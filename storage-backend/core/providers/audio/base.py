"""Base types and interfaces for audio providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, MutableMapping

from core.exceptions import ProviderError

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from core.streaming.manager import StreamingManager


@dataclass(slots=True)
class SpeechProviderRequest:
    """Container describing an audio transcription request."""

    file_path: Path | None = None
    file_bytes: bytes | None = None
    filename: str | None = None
    model: str | None = None
    language: str | None = None
    temperature: float | None = None
    prompt: str | None = None
    response_format: str | None = None
    mime_type: str | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def ensure_bytes(self) -> bytes:
        """Return audio bytes, loading them from ``file_path`` when required."""

        if self.file_bytes is not None:
            return self.file_bytes
        if self.file_path is None:
            raise ProviderError("No audio source provided for transcription")
        data = self.file_path.read_bytes()
        self.file_bytes = data
        return data


@dataclass(slots=True)
class SpeechTranscriptionResult:
    """Normalised transcription result returned by providers."""

    text: str
    provider: str
    language: str | None = None
    duration_seconds: float | None = None
    metadata: Mapping[str, Any] | None = None


class BaseAudioProvider(ABC):
    """Common behaviour shared across audio providers."""

    name: str = "audio"
    supports_translation: bool = False
    streaming_capable: bool = False

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Apply provider specific configuration from user supplied settings."""

    @abstractmethod
    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        """Return a transcription for an audio recording."""

    async def translate_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        """Translate an audio recording if supported by the provider."""

        raise ProviderError(
            f"{self.__class__.__name__} does not support translation",
            provider=self.name,
        )

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager: "StreamingManager",
        mode: str = "non-realtime",
    ) -> str:
        """Transcribe audio streamed over an asynchronous iterator."""

        raise ProviderError(
            f"{self.__class__.__name__} does not support streaming",
            provider=self.name,
        )


__all__ = [
    "BaseAudioProvider",
    "SpeechProviderRequest",
    "SpeechTranscriptionResult",
]

