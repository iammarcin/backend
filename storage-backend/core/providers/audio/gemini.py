"""Google Gemini speech provider implementation."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Mapping

from google.genai import types as genai_types

from core.clients.ai import get_gemini_client
from core.exceptions import ProviderError
from core.providers.audio.base import (
    BaseAudioProvider,
    SpeechProviderRequest,
    SpeechTranscriptionResult,
)
from core.providers.audio.config import (
    get_gemini_default_model,
    get_transcription_prompt,
    get_translation_prompt,
    normalise_gemini_model,
)
from core.utils.env import is_production

# Re-export normalise_gemini_model for backward compatibility
logger = logging.getLogger(__name__)


def _default_model() -> str:
    """Return the appropriate default Gemini model for the environment."""

    return get_gemini_default_model(is_production())


class GeminiSpeechProvider(BaseAudioProvider):
    """Bridge the Gemini Generative AI audio transcription flow."""

    name = "gemini"
    supports_translation = True

    def __init__(self) -> None:
        self.model = _default_model()

    def configure(self, settings: Mapping[str, Any]) -> None:  # type: ignore[override]
        if not settings:
            return
        model = settings.get("model", self.model)
        self.model = normalise_gemini_model(model, production=is_production())

    async def _prepare_audio(self, request: SpeechProviderRequest) -> tuple[bytes, str]:
        try:
            audio_bytes = request.ensure_bytes()
        except Exception as exc:  # pragma: no cover - defensive conversion
            raise ProviderError(str(exc), provider=self.name) from exc

        filename = request.filename
        if not filename:
            if request.file_path:
                filename = Path(request.file_path).name
            else:
                filename = "recording.wav"

        return audio_bytes, filename

    async def _generate(
        self,
        request: SpeechProviderRequest,
        *,
        translate: bool = False,
    ) -> SpeechTranscriptionResult:
        client = get_gemini_client()
        audio_bytes, filename = await self._prepare_audio(request)

        if translate:
            prompt = get_translation_prompt(
                language=request.language,
                user_prompt=request.prompt,
            )
        else:
            prompt = get_transcription_prompt(user_prompt=request.prompt)

        mime_type = request.mime_type or "audio/wav"
        part = genai_types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        model_name = normalise_gemini_model(request.model or self.model, production=is_production())
        self.model = model_name

        def _invoke():
            return client.models.generate_content(
                model=model_name,
                contents=[prompt, part],
            )

        try:
            response = await asyncio.to_thread(_invoke)
        except Exception as exc:  # pragma: no cover - network failure
            logger.error("Gemini audio request failed: %s", exc, exc_info=True)
            raise ProviderError(
                "Gemini audio request failed", provider=self.name, original_error=exc
            )

        # Extract text from response, handling cases where no speech is detected
        text = getattr(response, "text", None)
        if text is None or text.strip() == "":
            text = "No speech detected in the audio."
        else:
            text = text.strip()

        return SpeechTranscriptionResult(
            text=text,
            provider=self.name,
            language=request.language,
            metadata={
                "model": model_name,
                "filename": filename,
            },
        )

    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        return await self._generate(request, translate=False)

    async def translate_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        return await self._generate(request, translate=True)


__all__ = ["GeminiSpeechProvider", "normalise_gemini_model"]
