"""Helpers that construct provider-ready text-to-speech requests.

The previous service module contained a large private method that combined
text preparation, provider resolution, and request creation. Splitting that
behaviour out keeps the orchestration code short while making it easier to
unit test how requests are assembled for different customer settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from core.providers.tts_base import TTSRequest
from features.tts.schemas.requests import TTSUserSettings
from features.tts.utils import split_text_for_tts, tune_text


@dataclass(slots=True)
class TTSRequestBatch:
    """Grouping of resolved provider information and generated requests."""

    provider: Any
    requests: List[TTSRequest]
    model: str | None
    format: str | None
    voice: str | None


def build_tts_requests(
    *,
    text: str,
    user_settings: TTSUserSettings,
    customer_id: int,
    provider_resolver: Callable[[Dict[str, Any]], Any],
) -> TTSRequestBatch:
    """Create fully-populated provider requests for each text chunk."""

    tuned_text = tune_text(text)
    chunks = split_text_for_tts(tuned_text)

    provider = provider_resolver(user_settings.to_provider_payload())

    # Use the provider's resolve_model method to ensure the model is valid
    # This is important when provider is selected based on voice (e.g., ElevenLabs
    # voice with OpenAI model setting) - the provider can correct the model
    requested_model = user_settings.tts.model
    if hasattr(provider, "resolve_model"):
        resolved_model = provider.resolve_model(requested_model)
    else:
        resolved_model = requested_model

    resolved_format = user_settings.tts.format or "mp3"
    resolved_voice = user_settings.tts.voice

    requests: List[TTSRequest] = []
    metadata_template = user_settings.tts.as_provider_settings()

    for index, chunk in enumerate(chunks, start=1):
        requests.append(
            TTSRequest(
                text=chunk,
                customer_id=customer_id,
                model=resolved_model,
                voice=resolved_voice,
                format=resolved_format,
                speed=user_settings.tts.speed,
                instructions=user_settings.tts.instructions,
                chunk_index=index,
                chunk_count=len(chunks),
                metadata=dict(metadata_template),
            )
        )

    return TTSRequestBatch(
        provider=provider,
        requests=requests,
        model=resolved_model,
        format=resolved_format,
        voice=resolved_voice,
    )


__all__ = ["build_tts_requests", "TTSRequestBatch"]

