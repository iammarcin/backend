"""HTTP streaming helpers for the TTS service."""

from __future__ import annotations

import base64
from typing import Any, AsyncIterator, Callable, Dict, Tuple

from core.exceptions import ServiceError, ValidationError

from features.tts.schemas.requests import TTSAction, TTSGenerateRequest
from features.tts.utils import audio_format_to_mime

from .request_builder import build_tts_requests
from .test_mode import build_test_metadata


async def prepare_http_stream(
    *,
    request: TTSGenerateRequest,
    provider_resolver: Callable[[Dict[str, Any]], Any],
) -> Tuple[str, AsyncIterator[bytes], Dict[str, Any]]:
    """Prepare media type, iterator, and metadata for HTTP streaming responses."""

    if request.action is TTSAction.BILLING:
        raise ValidationError("Billing requests cannot be streamed", field="action")

    if not request.user_input.text:
        raise ValidationError("Text input is required", field="user_input.text")

    user_settings = request.user_settings

    if user_settings.general.return_test_data:
        metadata = build_test_metadata(user_settings)

        async def _iterator() -> AsyncIterator[bytes]:
            yield base64.b64decode(b"dGVzdC1hdWRpbw==")

        media_type = audio_format_to_mime(metadata["format"] or "mp3")
        return media_type, _iterator(), metadata

    batch = build_tts_requests(
        text=request.user_input.text,
        user_settings=user_settings,
        customer_id=request.customer_id,
        provider_resolver=provider_resolver,
    )

    if not batch.requests:
        raise ServiceError("No TTS chunks to process")

    metadata = {
        "provider": getattr(batch.provider, "name", "tts"),
        "model": batch.model,
        "voice": batch.voice,
        "format": batch.format,
    }

    async def _generator() -> AsyncIterator[bytes]:
        for tts_request in batch.requests:
            async for chunk in batch.provider.stream(tts_request):
                if chunk:
                    yield chunk

    media_type = audio_format_to_mime(batch.format or "mp3")
    return media_type, _generator(), metadata


__all__ = ["prepare_http_stream"]
