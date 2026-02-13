"""High-level speech-to-text service delegating work to specialised helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncIterator, Mapping, TYPE_CHECKING

from fastapi import WebSocket

from core.streaming.manager import StreamingManager
from features.audio.audio_sources import queue_audio_source as _queue_audio_source
from features.audio.audio_sources import websocket_audio_source as _websocket_audio_source
from features.audio.schemas import (
    AudioAction,
    StaticTranscriptionUserInput,
    StaticTranscriptionUserSettings,
)
from features.audio.static_workflow import (
    StaticTranscriptionResult as _StaticTranscriptionResult,
    execute_static_transcription,
)
from features.audio.streaming_workflow import transcribe_streaming_audio
from features.audio.transcription_rewrite import TranscriptionRewriteService

# Backwards compatibility for tests and legacy imports that patch the factory directly.
from core.providers.audio.factory import get_audio_provider  # noqa: F401

if TYPE_CHECKING:  # pragma: no cover - typing-only reference
    from features.chat.utils.websocket_runtime import WorkflowRuntime


class STTService:
    """Provide speech-to-text capabilities via pluggable providers."""

    StaticTranscriptionResult = _StaticTranscriptionResult

    def __init__(self, *, rewrite_service: TranscriptionRewriteService | None = None) -> None:
        # Lazy import to avoid circular dependency
        from config.audio.defaults import get_streaming_available_models
        from config.audio import StreamingProviderSettings

        self.available_models = set(get_streaming_available_models())
        self._streaming_settings = StreamingProviderSettings()
        self._rewrite_service = rewrite_service or TranscriptionRewriteService()

    def configure(self, settings_dict: dict[str, Any] | None) -> None:
        """Update Deepgram settings from an incoming configuration payload."""

        self._streaming_settings.update_from_payload(settings_dict)

    async def transcribe_file(
        self,
        *,
        action: AudioAction,
        customer_id: int,
        file_path: Path | str | None = None,
        filename: str | None = None,
        file_bytes: bytes | None = None,
        content_type: str | None = None,
        user_input: StaticTranscriptionUserInput | None = None,
        user_settings: StaticTranscriptionUserSettings | None = None,
        manager: StreamingManager | None = None,
    ) -> _StaticTranscriptionResult:
        """Transcribe an uploaded recording using the configured provider."""

        resolved_settings = user_settings or StaticTranscriptionUserSettings()
        return await execute_static_transcription(
            action=action,
            customer_id=customer_id,
            file_path=file_path,
            filename=filename,
            file_bytes=file_bytes,
            content_type=content_type,
            user_input=user_input,
            user_settings=resolved_settings,
            manager=manager,
            provider_factory=get_audio_provider,
            transcript_rewriter=self._rewrite_transcript,
        )

    async def transcribe_stream(
        self,
        *,
        audio_source: AsyncIterator[bytes | None],
        manager: StreamingManager,
        mode: str = "non-realtime",
        completion_token: str | None = None,
    ) -> str:
        """Stream audio to the configured streaming provider."""

        provider_settings = self._streaming_settings.to_provider_dict()
        return await transcribe_streaming_audio(
            provider_settings,
            audio_source=audio_source,
            manager=manager,
            mode=mode,
            completion_token=completion_token,
            transcript_rewriter=self._rewrite_transcript,
        )

    async def websocket_audio_source(
        self,
        websocket: WebSocket,
        *,
        runtime: "WorkflowRuntime | None" = None,
    ) -> AsyncIterator[bytes | None]:
        """Yield audio bytes received over a FastAPI WebSocket connection."""

        async for chunk in _websocket_audio_source(websocket, runtime=runtime):
            yield chunk

    async def queue_audio_source(
        self, audio_queue: asyncio.Queue[bytes | None]
    ) -> AsyncIterator[bytes | None]:
        """Yield audio chunks from an ``asyncio.Queue`` source."""

        async for chunk in _queue_audio_source(audio_queue):
            yield chunk

    @property
    def rewrite_service(self) -> TranscriptionRewriteService | None:
        return self._rewrite_service

    def set_rewrite_service(self, rewrite_service: TranscriptionRewriteService | None) -> None:
        self._rewrite_service = rewrite_service

    def _rewrite_transcript(
        self, text: str, context: Mapping[str, object] | None = None
    ) -> str:
        if not text:
            return text
        if self._rewrite_service is None or not self._rewrite_service.has_rules:
            return text
        return self._rewrite_service.apply(text, context)


__all__ = ["STTService", "get_audio_provider"]
