"""REST helpers for the ElevenLabs TTS provider."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping

import requests

from core.exceptions import ProviderError

from .utils import gather_voice_settings, stream_rest_audio

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .elevenlabs import ElevenLabsTTSProvider
    from .utils import TTSRequest, TTSResult


logger = logging.getLogger(__name__)


async def perform_rest_generation(
    provider: "ElevenLabsTTSProvider", request: "TTSRequest"
) -> "TTSResult":
    """Execute a synchronous ElevenLabs generation request."""

    if not request.text or not request.text.strip():
        raise ProviderError("TTS request text cannot be empty", provider=provider.name)

    model = request.model or provider.last_settings.get("model") or provider.default_model
    voice = provider.resolve_voice(request.voice or provider.last_settings.get("voice"))
    output_format = request.format or provider.last_settings.get("format") or "mp3"

    payload: dict[str, Any] = {
        "text": request.text,
        "model_id": model,
        "output_format": output_format,
    }

    voice_settings = gather_voice_settings(
        provider.last_settings,
        request.metadata,
        prefer_metadata_when_unset=False,
    )
    if voice_settings:
        payload["voice_settings"] = voice_settings

    headers = {
        "xi-api-key": provider.api_key,
        "Accept": "audio/mpeg" if output_format == "mp3" else "application/octet-stream",
    }

    url = f"{provider.api_base}/text-to-speech/{voice}"
    logger.info(
        "Requesting ElevenLabs TTS (model=%s voice=%s format=%s)",
        model,
        voice,
        output_format,
    )

    try:
        response = await asyncio.to_thread(
            requests.post,
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )
    except Exception as exc:  # pragma: no cover - network failure
        raise ProviderError("ElevenLabs TTS request failed", provider=provider.name, original_error=exc) from exc

    if response.status_code >= 400:
        raise ProviderError(
            f"ElevenLabs TTS returned {response.status_code}: {response.text}",
            provider=provider.name,
        )

    metadata = {
        "provider": provider.name,
        "model": model,
        "voice": voice,
        "format": output_format,
    }
    if request.chunk_index is not None:
        metadata["chunk_index"] = request.chunk_index
        metadata["chunk_count"] = request.chunk_count

    return provider.result_class(
        audio_bytes=response.content,
        provider=provider.name,
        model=model,
        format=output_format,
        voice=voice,
        metadata=metadata,
    )


async def stream_rest_generation(
    provider: "ElevenLabsTTSProvider", request: "TTSRequest"
) -> AsyncIterator[bytes]:
    """Stream audio via the ElevenLabs REST endpoint."""

    if not request.text or not request.text.strip():
        raise ProviderError("TTS request text cannot be empty", provider=provider.name)

    model = request.model or provider.last_settings.get("model") or provider.default_model
    voice = provider.resolve_voice(request.voice or provider.last_settings.get("voice"))
    output_format = request.format or provider.last_settings.get("format") or "mp3"

    payload: dict[str, Any] = {
        "text": request.text,
        "model_id": model,
        "output_format": output_format,
    }

    voice_settings = gather_voice_settings(
        provider.last_settings,
        request.metadata,
        prefer_metadata_when_unset=True,
    )
    if voice_settings:
        payload["voice_settings"] = voice_settings

    headers = {
        "xi-api-key": provider.api_key,
        "Accept": "audio/mpeg" if output_format == "mp3" else "application/octet-stream",
    }

    async for chunk in stream_rest_audio(
        url=f"{provider.api_base}/text-to-speech/{voice}",
        payload=payload,
        headers=headers,
        provider_name=provider.name,
    ):
        yield chunk


async def fetch_billing(provider: "ElevenLabsTTSProvider") -> Mapping[str, Any]:
    """Return ElevenLabs billing information."""

    url = f"{provider.api_base}/user/subscription"
    headers = {"xi-api-key": provider.api_key}

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=30)
    except Exception as exc:  # pragma: no cover - network failure
        raise ProviderError("ElevenLabs billing request failed", provider=provider.name, original_error=exc) from exc

    if response.status_code >= 400:
        raise ProviderError(
            f"ElevenLabs billing returned {response.status_code}: {response.text}",
            provider=provider.name,
        )

    data = response.json()
    return {
        "character_count": data.get("character_count"),
        "character_limit": data.get("character_limit"),
        "next_billing_date": provider.convert_timestamp_to_date(
            data.get("next_character_count_reset_unix")
        ),
    }


__all__ = [
    "perform_rest_generation",
    "stream_rest_generation",
    "fetch_billing",
]
