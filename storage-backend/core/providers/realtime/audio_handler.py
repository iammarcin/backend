"""Audio queue handling for OpenAI realtime provider.

This module contains audio-specific logic for the realtime provider, including
audio queue management, audio chunk processing, and audio buffer handling.
Separating audio concerns keeps the main provider focused on session orchestration.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from websockets.asyncio.client import ClientConnection

    from .utils.openai_session import SessionConfig

logger = logging.getLogger(__name__)


class AudioQueueHandler:
    """Manages audio input queue and streaming for realtime provider."""

    def __init__(
        self,
        *,
        client: ClientConnection | None = None,
        session_config: SessionConfig | None = None,
    ) -> None:
        self._client = client
        self._session_config = session_config
        self._input_audio_queue: asyncio.Queue[bytes | None] | None = None
        self._audio_sender_task: asyncio.Task[None] | None = None

    def set_client(self, client: ClientConnection | None) -> None:
        """Update the websocket client reference."""
        self._client = client

    def set_session_config(self, config: SessionConfig | None) -> None:
        """Update the session configuration reference."""
        self._session_config = config

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        """Set or replace the audio input queue."""
        self._input_audio_queue = queue
        if self._audio_sender_task and not self._audio_sender_task.done():
            self._audio_sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._audio_sender_task
            self._audio_sender_task = None

    def start_audio_sender(self) -> None:
        """Start the audio queue drain task if conditions are met."""
        if self._input_audio_queue and self._audio_sender_task is None:
            self._audio_sender_task = asyncio.create_task(self._drain_audio_queue())

    async def stop_audio_sender(self) -> None:
        """Stop the audio sender task if running."""
        if self._audio_sender_task and not self._audio_sender_task.done():
            self._audio_sender_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._audio_sender_task
        self._audio_sender_task = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        """Send JSON payload via websocket."""
        if not self._client:
            return
        message = json.dumps(payload)
        await self._client.send(message)

    def build_response_create_event(self) -> dict[str, Any]:
        """Build response.create event payload."""
        if self._session_config:
            modalities = self._session_config.output_modalities()
        else:
            modalities = ["text"]

        response_payload: dict[str, Any] = {
            "type": "response.create",
            "response": {
                "output_modalities": modalities,
            },
        }

        return response_payload

    async def _drain_audio_queue(self) -> None:
        """Continuously drain the audio queue and forward chunks to OpenAI."""
        if not self._input_audio_queue:
            logger.warning("No input audio queue configured for realtime audio stream")
            return

        logger.info(
            "Starting realtime audio queue drain task (VAD: %s)",
            self._session_config.vad_enabled if self._session_config else "unknown",
        )
        audio_chunk_count = 0
        total_bytes = 0

        try:
            while True:
                chunk = await self._input_audio_queue.get()
                if chunk is None:
                    duration_ms = (total_bytes / 2) / 24 if total_bytes else 0.0
                    vad_enabled = (
                        self._session_config.vad_enabled
                        if self._session_config is not None
                        else True
                    )

                    if total_bytes == 0:
                        logger.info(
                            "Realtime audio stream finished with no audio data "
                            "(chunks=%d, bytes=%d); skipping commit",
                            audio_chunk_count,
                            total_bytes,
                        )
                    elif vad_enabled:
                        logger.info(
                            "Realtime audio stream finished in VAD mode "
                            "(chunks=%d, bytes=%d, duration=%.2fms); skipping commit",
                            audio_chunk_count,
                            total_bytes,
                            duration_ms,
                        )
                    else:
                        logger.info(
                            "Realtime audio stream finished; committing buffer "
                            "(chunks=%d, bytes=%d, duration=%.2fms)",
                            audio_chunk_count,
                            total_bytes,
                            duration_ms,
                        )
                        await self._send_json({"type": "input_audio_buffer.commit"})
                        logger.info(
                            "VAD disabled; sending response.create to trigger model"
                        )
                        await self._send_json(self.build_response_create_event())
                    audio_chunk_count = 0
                    total_bytes = 0
                    if self._input_audio_queue.empty():
                        # No more audio pending; exit drain loop to avoid blocking.
                        break
                    continue

                if not chunk:
                    logger.debug("Received empty realtime audio chunk; skipping")
                    continue

                encoded = base64.b64encode(chunk).decode("utf-8")
                await self._send_json(
                    {
                        "type": "input_audio_buffer.append",
                        "audio": encoded,
                    }
                )
                audio_chunk_count += 1
                total_bytes += len(chunk)

                if audio_chunk_count % 100 == 0:
                    logger.debug(
                        "Forwarded %d realtime audio chunks to OpenAI (%.2f seconds)",
                        audio_chunk_count,
                        (total_bytes / 2) / 24000 if total_bytes else 0.0,
                    )
        except asyncio.CancelledError:
            logger.info(
                "Realtime audio drain task cancelled after processing %d chunks",
                audio_chunk_count,
            )
            raise
        except Exception as exc:
            logger.error(
                "Error forwarding realtime audio after %d chunks: %s",
                audio_chunk_count,
                exc,
                exc_info=True,
            )


__all__ = ["AudioQueueHandler"]
