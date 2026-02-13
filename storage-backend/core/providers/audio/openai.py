"""OpenAI speech provider implementation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

from config.audio.providers import openai as openai_config
from core.clients.ai import get_openai_async_client
from core.exceptions import ProviderError
from core.providers.audio.base import (
    BaseAudioProvider,
    SpeechProviderRequest,
    SpeechTranscriptionResult,
)

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class _AsyncAudioCall:
    """Helper representing an asynchronous OpenAI audio SDK call."""

    method: str
    payload: Mapping[str, Any]


class OpenAISpeechProvider(BaseAudioProvider):
    """Bridge the OpenAI audio transcription API."""

    name = "openai"
    supports_translation = True

    def __init__(self) -> None:
        self.model = openai_config.DEFAULT_TRANSCRIBE_MODEL

    def configure(self, settings: Mapping[str, Any]) -> None:  # type: ignore[override]
        if settings:
            model = str(settings.get("model", self.model) or self.model)
            if model:
                self.model = model

    async def _prepare_audio(self, request: SpeechProviderRequest) -> BytesIO:
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

        buffer = BytesIO(audio_bytes)
        buffer.name = filename  # type: ignore[attr-defined] - used by OpenAI SDK
        return buffer

    async def _execute(self, call: _AsyncAudioCall) -> SpeechTranscriptionResult:
        client = get_openai_async_client()
        try:
            if call.method == "transcriptions":
                response = await client.audio.transcriptions.create(**call.payload)
            else:
                response = await client.audio.translations.create(**call.payload)
        except Exception as exc:  # pragma: no cover - network/client failure
            logger.error("OpenAI audio request failed: %s", exc, exc_info=True)
            raise ProviderError("OpenAI audio request failed", provider=self.name, original_error=exc)

        text = getattr(response, "text", None) or getattr(response, "data", None)
        if text is None:
            text = str(response)

        return SpeechTranscriptionResult(
            text=text,
            provider=self.name,
            language=call.payload.get("language"),
            metadata={"model": call.payload.get("model", self.model)},
        )

    async def transcribe_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        audio_file = await self._prepare_audio(request)
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "file": audio_file,
            "prompt": request.prompt,
            "temperature": request.temperature,
        }
        if request.language:
            payload["language"] = request.language
        if request.response_format:
            payload["response_format"] = request.response_format

        call = _AsyncAudioCall(method="transcriptions", payload=payload)
        return await self._execute(call)

    async def translate_file(
        self, request: SpeechProviderRequest
    ) -> SpeechTranscriptionResult:
        audio_file = await self._prepare_audio(request)
        payload: dict[str, Any] = {
            "model": request.model or self.model,
            "file": audio_file,
            "prompt": request.prompt,
            "temperature": request.temperature,
        }
        if request.response_format:
            payload["response_format"] = request.response_format

        call = _AsyncAudioCall(method="translations", payload=payload)
        return await self._execute(call)


__all__ = ["OpenAISpeechProvider"]
