"""Utilities for streaming TTS integration tests.

These helpers provide lightweight stubs that emulate the behaviour of the
streaming chat pipeline without contacting real AI providers. They are used by
integration, performance, and load tests to simulate text and audio streaming
scenarios deterministically.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Sequence

from features.chat.services.streaming.collector import StreamCollection
from features.chat.utils.prompt_utils import PromptContext
from features.tts.service_models import TTSStreamingMetadata


class StubTTSService:
    """Minimal TTS service stub that emits predictable streaming metadata."""

    def __init__(self, *, audio_delay: float = 0.0, sequential_delay: float = 0.0) -> None:
        self._audio_delay = max(0.0, audio_delay)
        self._sequential_delay = max(0.0, sequential_delay)

    async def stream_from_text_queue(
        self,
        *,
        text_queue: asyncio.Queue[str | None],
        customer_id: int,
        user_settings,
        manager,
        timings: dict[str, float] | None = None,
    ) -> TTSStreamingMetadata:
        """Consume a queue of text chunks and emit synthetic audio events."""

        text_chunk_count = 0
        audio_chunk_count = 0

        while True:
            chunk = await text_queue.get()
            if chunk is None:
                break

            text_chunk_count += 1
            if self._audio_delay:
                await asyncio.sleep(self._audio_delay)

            if timings is not None and "tts_first_response_time" not in timings:
                timings["tts_first_response_time"] = time.time()

            audio_chunk_count += 1
            await manager.send_to_queues(
                {"type": "audio_chunk", "content": f"audio-{audio_chunk_count}"}
            )

        await manager.send_to_queues({"type": "tts_completed", "content": ""})

        if timings is not None and "tts_response_time" not in timings:
            timings["tts_response_time"] = time.time()

        provider_settings = getattr(user_settings, "tts", None)
        provider = getattr(provider_settings, "provider", None) or "stub-tts"
        model = getattr(provider_settings, "model", None) or "stub-model"
        voice = getattr(provider_settings, "voice", None) or "stub-voice"
        audio_format = getattr(provider_settings, "format", None) or "pcm"

        return TTSStreamingMetadata(
            provider=provider,
            model=model,
            voice=voice,
            format=audio_format,
            text_chunk_count=text_chunk_count,
            audio_chunk_count=audio_chunk_count,
            audio_file_url="https://example.com/audio.wav",
            storage_metadata={"mode": "parallel"},
        )

    async def stream_text(
        self,
        *,
        text: str,
        customer_id: int,
        user_settings,
        manager,
        timings: dict[str, float] | None = None,
    ) -> TTSStreamingMetadata:
        """Sequential fallback used when queue-based streaming is disabled."""

        if self._sequential_delay:
            await asyncio.sleep(self._sequential_delay)

        if timings is not None and "tts_first_response_time" not in timings:
            timings["tts_first_response_time"] = time.time()

        await manager.send_to_queues({"type": "audio_chunk", "content": "audio-sequential"})
        await manager.send_to_queues({"type": "tts_completed", "content": ""})

        if timings is not None and "tts_response_time" not in timings:
            timings["tts_response_time"] = time.time()

        provider_settings = getattr(user_settings, "tts", None)
        provider = getattr(provider_settings, "provider", None) or "stub-tts"
        model = getattr(provider_settings, "model", None) or "stub-model"
        voice = getattr(provider_settings, "voice", None) or "stub-voice"
        audio_format = getattr(provider_settings, "format", None) or "pcm"

        word_count = max(1, len(text.split()))

        return TTSStreamingMetadata(
            provider=provider,
            model=model,
            voice=voice,
            format=audio_format,
            text_chunk_count=word_count,
            audio_chunk_count=1,
            audio_file_url="https://example.com/audio.wav",
            storage_metadata={"mode": "sequential"},
        )


def install_streaming_stubs(
    monkeypatch,
    *,
    text_chunks: Sequence[str],
    text_delay: float = 0.0,
    provider_name: str = "stub-text-provider",
    model_name: str = "stub-text-model",
    temperature: float = 0.0,
    max_tokens: int = 256,
) -> None:
    """Patch streaming helpers with deterministic stub implementations."""

    chunks = list(text_chunks)
    delay = max(0.0, text_delay)

    def _resolve_prompt_and_provider(
        *,
        prompt,
        settings,
        customer_id: int,
        model: str | None = None,
    ):
        if isinstance(prompt, str):
            text_prompt = prompt
        else:
            text_prompt = str(prompt)
        context = PromptContext(
            text_prompt=text_prompt,
            image_mode=None,
            input_image_url=None,
        )
        provider = SimpleNamespace(provider_name=provider_name)
        return context, provider, model_name, temperature, max_tokens

    async def _collect_streaming_chunks(
        *,
        provider,
        manager,
        prompt_text: str,
        model: str,
        temperature: float,
        max_tokens: int,
        system_prompt,
        settings,
        timings: dict[str, float],
        user_input=None,
        messages=None,
        customer_id: int | None = None,
        session_id: str | None = None,
    ) -> StreamCollection:
        first_chunk_emitted = False
        for chunk in chunks:
            if timings is not None and not first_chunk_emitted:
                timings["text_first_chunk_time"] = time.time()
                first_chunk_emitted = True
            await manager.send_to_queues({"type": "text_chunk", "content": chunk})
            if delay:
                await asyncio.sleep(delay)

        if timings is not None and not first_chunk_emitted:
            timings["text_first_chunk_time"] = time.time()

        await manager.send_to_queues({"type": "text_completed", "content": ""})

        return StreamCollection(
            chunks=list(chunks),
            reasoning_chunks=[],
            claude_session_id=None,
            tool_calls=[],
            tool_results=[],
            requires_tool_action=False,
        )

    async def _emit_completion_events(**_kwargs) -> None:
        return None

    monkeypatch.setattr(
        "features.chat.services.streaming.core.resolve_prompt_and_provider",
        _resolve_prompt_and_provider,
    )
    monkeypatch.setattr(
        "features.chat.services.streaming.core.collect_streaming_chunks",
        _collect_streaming_chunks,
    )
    monkeypatch.setattr(
        "features.chat.services.streaming.core.emit_completion_events",
        _emit_completion_events,
    )


def make_settings(
    *,
    streaming_enabled: bool = True,
    tts_auto_execute: bool = True,
    provider: str = "elevenlabs",
    voice: str = "Sherlock",
    model: str = "eleven_turbo_v2_5",
    return_test_data: bool = False,
) -> dict[str, object]:
    """Return a canonical chat settings payload for tests."""

    return {
        "text": {
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
        "tts": {
            "tts_auto_execute": tts_auto_execute,
            "streaming": streaming_enabled,
            "provider": provider,
            "voice": voice,
            "model": model,
        },
        "general": {
            "return_test_data": return_test_data,
        },
    }


__all__ = ["StubTTSService", "install_streaming_stubs", "make_settings"]
