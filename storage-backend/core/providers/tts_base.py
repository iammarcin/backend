"""Base classes and schemas for text-to-speech providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, MutableMapping, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from core.exceptions import ProviderError


@dataclass(slots=True)
class TTSRequest:
    """Container describing a text-to-speech generation request."""

    text: str
    customer_id: int
    model: str | None = None
    voice: str | None = None
    format: str = "mp3"
    speed: float | None = None
    instructions: str | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TTSResult:
    """Normalised text-to-speech response returned by providers."""

    audio_bytes: bytes
    provider: str
    model: str
    format: str
    voice: str | None = None
    duration_seconds: float | None = None
    metadata: Mapping[str, Any] | None = None


class BaseTTSProvider(ABC):
    """Base interface for text-to-speech providers."""

    name: str = "tts"
    supports_input_stream: bool = False

    def configure(self, settings: Mapping[str, Any]) -> None:
        """Apply provider specific configuration settings."""

    @abstractmethod
    async def generate(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> TTSResult:
        """Return generated audio for the supplied text request."""

    async def stream(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> AsyncIterator[bytes]:  # pragma: no cover - default impl
        """Yield audio chunks for the supplied text request.

        Providers that do not support streaming may rely on the base implementation
        which raises a :class:`ProviderError` to signal the unsupported mode.
        """

        raise ProviderError(
            f"{self.__class__.__name__} does not support streaming", provider=self.name
        )

    async def get_billing(self) -> Mapping[str, Any]:
        """Return billing usage data when supported."""

        raise ProviderError(
            f"{self.__class__.__name__} does not expose billing information",
            provider=self.name,
        )

    def get_websocket_format(self) -> str:
        """Return the PCM format string to use for websocket streaming.

        Providers may require explicit sample rate suffixes in their format
        identifiers when delivering raw PCM audio over websocket connections.
        The default implementation returns ``"pcm"``, which aligns with the
        OpenAI TTS API expectations (16-bit, 24 kHz, mono). Providers that need
        a different format, such as ElevenLabs requiring ``"pcm_24000"`` to
        indicate the sample rate, should override this method.

        Returns:
            str: The format identifier to apply to websocket TTS requests.
        """

        return "pcm"

    def resolve_model(self, requested_model: str | None) -> str | None:
        """Return a valid model for this provider based on the requested model.

        When a provider is selected based on voice (rather than model), the
        requested model may not be valid for that provider. This method allows
        providers to validate and resolve the model to an appropriate value.

        The base implementation returns the requested model unchanged.
        Providers should override this to validate against their supported models.

        Args:
            requested_model: The model requested in user settings.

        Returns:
            A valid model for this provider, or None to use provider defaults.
        """
        return requested_model


__all__ = ["TTSRequest", "TTSResult", "BaseTTSProvider"]