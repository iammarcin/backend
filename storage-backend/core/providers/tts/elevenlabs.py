"""ElevenLabs text-to-speech provider implementation."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

import websockets

from config.tts.providers import elevenlabs as elevenlabs_config
from core.exceptions import ConfigurationError
from core.providers.tts_base import BaseTTSProvider, TTSRequest, TTSResult

from .elevenlabs_rest import fetch_billing, perform_rest_generation, stream_rest_generation
from .elevenlabs_websocket import stream_from_text_queue as websocket_stream_from_queue
from .elevenlabs_websocket import stream_via_websocket
from .utils import (
    API_BASE,
    FORMAT_TO_WEBSOCKET_FORMAT,
    convert_timestamp_to_date,
    gather_voice_settings,
    parse_chunk_length_schedule,
    resolve_voice,
)


logger = logging.getLogger(__name__)

_FORMAT_TO_WEBSOCKET_FORMAT = dict(FORMAT_TO_WEBSOCKET_FORMAT)


class ElevenLabsTTSProvider(BaseTTSProvider):
    """Adapter around the ElevenLabs REST and WebSocket APIs."""

    name = "elevenlabs"
    supports_input_stream = True

    # Valid ElevenLabs model identifiers
    VALID_MODELS = frozenset({
        "eleven_monolingual_v1",
        "eleven_multilingual_v2",
        "eleven_turbo_v2_5",
        "eleven_flash_v2_5",
    })

    def __init__(self) -> None:
        if not elevenlabs_config.API_KEY:
            raise ConfigurationError("ELEVEN_API_KEY must be configured", key="ELEVEN_API_KEY")
        self._api_key = elevenlabs_config.API_KEY
        self._default_model = elevenlabs_config.DEFAULT_MODEL
        self._last_settings: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------
    def configure(self, settings: Mapping[str, Any]) -> None:  # pragma: no cover - simple mapping
        self._last_settings = dict(settings)
        voice = self._last_settings.get("voice")
        if voice is not None:
            self._last_settings["voice"] = resolve_voice(voice)

        chunk_schedule = settings.get("chunk_length_schedule")
        if chunk_schedule is not None:
            self._last_settings["chunk_length_schedule"] = self._parse_chunk_length_schedule(
                chunk_schedule
            )

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def api_base(self) -> str:
        return API_BASE

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def last_settings(self) -> dict[str, Any]:
        return self._last_settings

    @property
    def result_class(self) -> type[TTSResult]:
        return TTSResult

    # ------------------------------------------------------------------
    # Voice helpers exposed for utility modules
    # ------------------------------------------------------------------
    def resolve_voice(self, value: Optional[str]) -> str:
        return resolve_voice(value)

    def gather_voice_settings(
        self, metadata: Mapping[str, Any], *, prefer_metadata_when_unset: bool
    ) -> Mapping[str, Any]:
        return gather_voice_settings(
            self._last_settings,
            metadata,
            prefer_metadata_when_unset=prefer_metadata_when_unset,
        )

    def parse_chunk_schedule(self, value: Any) -> list[int]:
        return self._parse_chunk_length_schedule(value)

    def convert_timestamp_to_date(self, value: Any) -> Any:
        return convert_timestamp_to_date(value)

    # ------------------------------------------------------------------
    # BaseTTSProvider overrides
    # ------------------------------------------------------------------
    def get_websocket_format(self) -> str:
        """Return the PCM format string required for ElevenLabs websocket audio."""

        return elevenlabs_config.DEFAULT_REALTIME_FORMAT

    def resolve_model(self, requested_model: str | None) -> str:
        """Return a valid ElevenLabs model for the requested model.

        When the provider is selected based on voice (e.g., "naval" is an ElevenLabs
        voice), the requested model may be for a different provider (e.g., "gpt-4o-mini-tts"
        is an OpenAI model). This method validates the model and returns the default
        ElevenLabs model if the requested one is not valid.

        Args:
            requested_model: The model requested in user settings.

        Returns:
            A valid ElevenLabs model identifier.
        """
        if requested_model and requested_model.lower() in self.VALID_MODELS:
            return requested_model.lower()

        if requested_model:
            logger.debug(
                "Requested model '%s' is not valid for ElevenLabs, using default '%s'",
                requested_model,
                self._default_model,
            )
        return self._default_model

    async def generate(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> TTSResult:
        return await perform_rest_generation(self, request)

    async def get_billing(self) -> Mapping[str, Any]:
        return await fetch_billing(self)

    async def stream(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> AsyncIterator[bytes]:
        async for chunk in stream_rest_generation(self, request):
            yield chunk

    async def stream_websocket(
        self,
        request: TTSRequest,
        *,
        chunk_length_schedule: Optional[list[int]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
    ) -> AsyncIterator[bytes]:
        async for chunk in stream_via_websocket(
            self,
            request,
            chunk_length_schedule=chunk_length_schedule,
            runtime=runtime,
        ):
            yield chunk

    async def stream_from_text_queue(
        self,
        *,
        text_queue: asyncio.Queue[str | None],
        voice: str,
        model: Optional[str] = None,
        audio_format: str = "pcm_24000",
        voice_settings: Optional[Mapping[str, Any]] = None,
        chunk_length_schedule: Optional[list[int]] = None,
        runtime: Optional["WorkflowRuntime"] = None,
    ) -> AsyncIterator[str]:
        async for chunk in websocket_stream_from_queue(
            self,
            text_queue=text_queue,
            voice=voice,
            model=model,
            audio_format=audio_format,
            voice_settings=voice_settings,
            chunk_length_schedule=chunk_length_schedule,
            runtime=runtime,
        ):
            yield chunk

    # ------------------------------------------------------------------
    # Backwards compatibility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_chunk_length_schedule(value: Any) -> list[int]:
        """Compat helper kept for legacy tests importing private API."""

        return parse_chunk_length_schedule(value)


__all__ = ["ElevenLabsTTSProvider", "_FORMAT_TO_WEBSOCKET_FORMAT", "websockets"]
