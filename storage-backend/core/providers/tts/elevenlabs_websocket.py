"""WebSocket helpers for the ElevenLabs TTS provider."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, Optional

from core.exceptions import ProviderError

from .utils import (
    ensure_websocket_defaults,
    parse_chunk_length_schedule,
    stream_websocket_audio,
    stream_websocket_audio_from_queue,
    websocket_format_for,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .elevenlabs import ElevenLabsTTSProvider
    from .utils import TTSRequest


logger = logging.getLogger(__name__)


async def stream_via_websocket(
    provider: "ElevenLabsTTSProvider",
    request: "TTSRequest",
    *,
    chunk_length_schedule: Optional[list[int]] = None,
    runtime: Optional["WorkflowRuntime"] = None,
) -> AsyncIterator[bytes]:
    """Stream audio via ElevenLabs' WebSocket API for progressive playback."""

    if not request.text or not request.text.strip():
        raise ProviderError("TTS request text cannot be empty", provider=provider.name)

    model = request.model or provider.last_settings.get("model") or provider.default_model
    voice = provider.resolve_voice(request.voice or provider.last_settings.get("voice"))
    output_format = request.format or provider.last_settings.get("format") or "pcm"
    websocket_format = websocket_format_for(output_format)

    if chunk_length_schedule is None:
        if request.metadata.get("chunk_length_schedule") is not None:
            chunk_length_schedule = parse_chunk_length_schedule(
                request.metadata["chunk_length_schedule"]
            )
        else:
            chunk_length_schedule = provider.parse_chunk_schedule(
                provider.last_settings.get("chunk_length_schedule")
            )
    else:
        chunk_length_schedule = parse_chunk_length_schedule(chunk_length_schedule)

    voice_settings = provider.gather_voice_settings(
        request.metadata,
        prefer_metadata_when_unset=True,
    )
    ensure_websocket_defaults(voice_settings)

    uri = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{voice}/stream-input"
        f"?model_id={model}"
        f"&inactivity_timeout=360"
        f"&output_format={websocket_format}"
    )

    logger.info(
        "Connecting to ElevenLabs WebSocket (model=%s voice=%s format=%s)",
        model,
        voice,
        websocket_format,
    )

    async for chunk in stream_websocket_audio(
        uri=uri,
        text=request.text,
        api_key=provider.api_key,
        voice_settings=voice_settings,
        chunk_length_schedule=chunk_length_schedule,
        provider_name=provider.name,
        runtime=runtime,
    ):
        yield chunk


async def stream_from_text_queue(
    provider: "ElevenLabsTTSProvider",
    *,
    text_queue: asyncio.Queue[str | None],
    voice: str,
    model: Optional[str] = None,
    audio_format: str = "pcm_24000",
    voice_settings: Optional[Mapping[str, Any]] = None,
    chunk_length_schedule: Optional[list[int]] = None,
    runtime: Optional["WorkflowRuntime"] = None,
) -> AsyncIterator[str]:
    """Stream audio while consuming text chunks from a queue."""

    resolved_voice = provider.resolve_voice(voice)
    resolved_model = model or provider.last_settings.get("model") or provider.default_model
    websocket_format = websocket_format_for(audio_format)

    if chunk_length_schedule is None:
        schedule = provider.parse_chunk_schedule(provider.last_settings.get("chunk_length_schedule"))
    else:
        schedule = parse_chunk_length_schedule(chunk_length_schedule)

    final_voice_settings: dict[str, Any]
    if voice_settings is None:
        final_voice_settings = {}
    else:
        final_voice_settings = dict(voice_settings)
    ensure_websocket_defaults(final_voice_settings)

    uri = (
        f"wss://api.elevenlabs.io/v1/text-to-speech/{resolved_voice}/stream-input"
        f"?model_id={resolved_model}"
        f"&inactivity_timeout=360"
        f"&output_format={websocket_format}"
    )

    logger.info(
        "Starting ElevenLabs queue-based streaming (voice=%s model=%s format=%s)",
        resolved_voice,
        resolved_model,
        websocket_format,
    )

    async for audio_bytes in stream_websocket_audio_from_queue(
        uri=uri,
        text_queue=text_queue,
        api_key=provider.api_key,
        voice_settings=final_voice_settings,
        chunk_length_schedule=schedule,
        provider_name=provider.name,
        runtime=runtime,
    ):
        yield base64.b64encode(audio_bytes).decode("utf-8")


__all__ = [
    "stream_via_websocket",
    "stream_from_text_queue",
]
