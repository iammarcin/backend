"""Audio forwarding helpers for realtime streaming providers."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator, Awaitable, Callable, Optional

from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)


async def forward_audio_chunks(
    audio_source: AsyncIterator[bytes | None],
    ws_client: ClientConnection,
    *,
    sample_rate: int,
    transcription_only: bool = False,
    vad_enabled: bool = True,
    commit_func: Optional[Callable[[ClientConnection, bool], Awaitable[None]]] = None,
) -> int:
    """Forward audio chunks to OpenAI Realtime API."""

    chunk_count = 0
    total_bytes = 0
    commit = commit_func or _commit_audio_buffer

    try:
        async for audio_chunk in audio_source:
            if audio_chunk is None:
                logger.info(
                    "Audio recording finished (chunks=%s, bytes=%s, vad=%s)",
                    chunk_count,
                    total_bytes,
                    vad_enabled,
                )
                if not vad_enabled:
                    logger.debug("Manually committing buffer (VAD disabled)")
                else:
                    logger.debug("Finalising buffer after VAD session end")

                await commit(ws_client, transcription_only)
                break

            if not audio_chunk:
                logger.debug("Skipping empty audio chunk")
                continue

            encoded = base64.b64encode(audio_chunk).decode("utf-8")

            await ws_client.send(
                json.dumps(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": encoded,
                    }
                )
            )

            chunk_count += 1
            total_bytes += len(audio_chunk)

            if chunk_count % 100 == 0:
                duration_sec = (total_bytes / 2) / sample_rate if total_bytes else 0.0
                logger.debug(
                    "Forwarded %s audio chunks to OpenAI (%.2f seconds)",
                    chunk_count,
                    duration_sec,
                )
    except asyncio.CancelledError:
        logger.info(
            "Audio sending task cancelled after %s chunks",
            chunk_count,
        )
        raise
    except Exception as exc:  # pragma: no cover
        logger.error(
            "Error sending audio chunk %s: %s",
            chunk_count,
            exc,
            exc_info=True,
        )
        raise

    logger.info(
        "Finished sending %s audio chunks to OpenAI (total_bytes=%s)",
        chunk_count,
        total_bytes,
    )
    return chunk_count


async def _commit_audio_buffer(ws_client: ClientConnection, force_transcription: bool = False) -> None:
    """Commit audio buffer to finalize any pending speech."""

    await ws_client.send(json.dumps({"type": "input_audio_buffer.commit"}))

    if not force_transcription:
        await ws_client.send(json.dumps({"type": "response.create"}))


__all__ = ["forward_audio_chunks", "_commit_audio_buffer"]
