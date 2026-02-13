"""Compatibility exports for audio streaming utilities."""

from __future__ import annotations

from typing import AsyncIterator

from websockets.asyncio.client import ClientConnection

from core.streaming.manager import StreamingManager

from . import streaming_forward as _forward_module
from .streaming_transcription import (
    receive_transcription_events as _receive_transcription_events_impl,
)

_commit_audio_buffer = _forward_module._commit_audio_buffer


async def forward_audio_chunks(
    audio_source: AsyncIterator[bytes | None],
    ws_client: ClientConnection,
    *,
    sample_rate: int,
    transcription_only: bool = False,
    vad_enabled: bool = True,
) -> int:
    return await _forward_module.forward_audio_chunks(
        audio_source,
        ws_client,
        sample_rate=sample_rate,
        transcription_only=transcription_only,
        vad_enabled=vad_enabled,
        commit_func=_commit_audio_buffer,
    )


async def receive_transcription_events(
    ws_client: ClientConnection,
    manager: StreamingManager,
    *,
    mode: str,
    provider_name: str,
) -> str:
    return await _receive_transcription_events_impl(
        ws_client,
        manager,
        mode=mode,
        provider_name=provider_name,
    )

__all__ = [
    "forward_audio_chunks",
    "receive_transcription_events",
    "_commit_audio_buffer",
]
