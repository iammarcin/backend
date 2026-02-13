"""OpenAI text-to-speech provider implementation."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
import threading
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, Optional

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime

from config.tts.providers import openai as openai_config
from core.clients.ai import get_openai_client
from core.exceptions import ProviderError
from core.providers.tts_base import BaseTTSProvider, TTSRequest, TTSResult

logger = logging.getLogger(__name__)


class OpenAITTSProvider(BaseTTSProvider):
    """Adapter around the OpenAI text-to-speech API."""

    name = "openai"
    supports_input_stream = False

    def __init__(self) -> None:
        self._client = get_openai_client()
        self._default_voice = openai_config.DEFAULT_VOICE
        self._default_format = openai_config.DEFAULT_AUDIO_FORMAT
        self._supports_instructions = True
        self._last_settings: dict[str, Any] = {}

    def configure(self, settings: Mapping[str, Any]) -> None:  # pragma: no cover - trivial
        self._last_settings = dict(settings)

    def get_websocket_format(self) -> str:
        """Return the PCM audio format expected by OpenAI websocket streaming."""

        return "pcm"

    async def generate(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> TTSResult:
        if not request.text or not request.text.strip():
            raise ProviderError("TTS request text cannot be empty", provider=self.name)

        model = request.model or self._last_settings.get("model") or openai_config.DEFAULT_MODEL
        voice = request.voice or self._last_settings.get("voice") or self._default_voice
        audio_format = request.format or self._last_settings.get("format") or self._default_format
        speed = request.speed or self._last_settings.get("speed", 1.0)
        instructions = request.instructions or self._last_settings.get("instructions")

        payload: dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": request.text,
            "response_format": audio_format,
            "speed": speed,
        }
        if instructions:
            payload["instructions"] = instructions

        logger.info(
            "Requesting OpenAI TTS generation (model=%s voice=%s format=%s)",
            model,
            voice,
            audio_format,
        )

        try:
            response = await asyncio.to_thread(self._client.audio.speech.create, **payload)
        except Exception as exc:  # pragma: no cover - network failure
            raise ProviderError("OpenAI TTS request failed", provider=self.name, original_error=exc) from exc

        path = await _stream_response_to_tempfile(response, audio_format)
        try:
            audio_bytes = await asyncio.to_thread(path.read_bytes)
        finally:
            await asyncio.to_thread(path.unlink, missing_ok=True)

        metadata: dict[str, Any] = {
            "provider": self.name,
            "model": model,
            "voice": voice,
            "format": audio_format,
            "speed": speed,
        }
        if instructions:
            metadata["instructions"] = instructions
        if request.chunk_index is not None:
            metadata["chunk_index"] = request.chunk_index
            metadata["chunk_count"] = request.chunk_count

        return TTSResult(
            audio_bytes=audio_bytes,
            provider=self.name,
            model=model,
            format=audio_format,
            voice=voice,
            metadata=metadata,
        )

    async def stream(
        self, request: TTSRequest, *, runtime: Optional["WorkflowRuntime"] = None
    ) -> AsyncIterator[bytes]:
        if not request.text or not request.text.strip():
            raise ProviderError("TTS request text cannot be empty", provider=self.name)

        model = request.model or self._last_settings.get("model") or openai_config.DEFAULT_MODEL
        voice = request.voice or self._last_settings.get("voice") or self._default_voice
        audio_format = request.format or self._last_settings.get("format") or self._default_format
        speed = request.speed or self._last_settings.get("speed", 1.0)
        instructions = request.instructions or self._last_settings.get("instructions")

        payload: dict[str, Any] = {
            "model": model,
            "voice": voice,
            "input": request.text,
            "response_format": audio_format,
            "speed": speed,
        }
        if instructions:
            payload["instructions"] = instructions

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[object] = asyncio.Queue()
        sentinel = object()

        def _produce() -> None:
            try:
                with self._client.audio.speech.with_streaming_response.create(**payload) as response:
                    # VERY important to specify the size - 1024 - without it, it doesn't work
                    for chunk in response.iter_bytes(1024):
                        if not chunk:
                            continue
                        loop.call_soon_threadsafe(queue.put_nowait, bytes(chunk))
            except Exception as exc:  # pragma: no cover - defensive
                loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        thread = threading.Thread(target=_produce, daemon=True)
        thread.start()

        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                if isinstance(item, tuple) and item and item[0] == "error":
                    exc = item[1]
                    raise ProviderError(
                        "OpenAI TTS streaming failed", provider=self.name, original_error=exc
                    ) from exc
                if isinstance(item, bytes) and item:
                    yield item
        finally:
            await asyncio.to_thread(thread.join)


async def _stream_response_to_tempfile(response: Any, suffix: str) -> Path:
    """Persist a streamed OpenAI response to a temporary file and return its path."""

    def _create_and_stream() -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}")
        tmp.close()
        path = Path(tmp.name)
        try:
            response.stream_to_file(str(path))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    return await asyncio.to_thread(_create_and_stream)


__all__ = ["OpenAITTSProvider"]
