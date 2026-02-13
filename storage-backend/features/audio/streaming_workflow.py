"""Helpers for running streaming transcription sessions.

This module keeps provider invocation and error handling separate from the
service entry point so that streaming orchestration remains focused.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Callable, Mapping

from core.exceptions import ProviderError, ServiceError
from core.providers.audio.factory import get_audio_provider
from core.streaming.manager import StreamingManager

logger = logging.getLogger(__name__)


async def transcribe_streaming_audio(
    provider_settings: Mapping[str, Any],
    *,
    audio_source: AsyncIterator[bytes | None],
    manager: StreamingManager,
    mode: str = "non-realtime",
    completion_token: str | None = None,
    transcript_rewriter: Callable[[str, Mapping[str, Any] | None], str] | None = None,
) -> str:
    """Run a streaming transcription session using the configured provider."""

    try:
        provider = get_audio_provider({"audio": dict(provider_settings)}, action="stream")
        transcription = await provider.transcribe_stream(
            audio_source=audio_source,
            manager=manager,
            mode=mode,
        )
    except ProviderError:
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Streaming transcription failed: %s", exc, exc_info=True)
        raise ServiceError(f"Streaming transcription failed: {exc}") from exc
    finally:
        if completion_token is not None:
            await manager.signal_completion(token=completion_token)

    if transcript_rewriter is not None and transcription:
        rewrite_context: Mapping[str, Any] = {
            "provider": provider_settings.get("provider") or getattr(provider, "name", None),
            "model": provider_settings.get("model"),
            "action": "stream",
            "mode": mode,
        }
        transcription = transcript_rewriter(transcription, rewrite_context)

    logger.info("Streaming transcription finished (mode=%s, chars=%s)", mode, len(transcription))
    return transcription


__all__ = ["transcribe_streaming_audio"]
