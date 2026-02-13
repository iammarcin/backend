"""Audio forwarding utilities for realtime workflows."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def forward_audio_input(
    websocket: WebSocket, audio_queue: asyncio.Queue[bytes | None]
) -> None:
    """Forward audio from WebSocket to provider's audio queue."""

    logger.info("Starting audio input forwarding")

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"] is not None:
                audio_bytes = message["bytes"]
                await audio_queue.put(audio_bytes)
                logger.debug("Forwarded %d bytes to audio queue", len(audio_bytes))

            elif "text" in message and message["text"] is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON text message during audio input")
                    continue

                if data.get("type") == "audio_complete":
                    await audio_queue.put(None)
                    logger.info("Audio input complete signal received")
                    break

    except asyncio.CancelledError:
        logger.info("Audio input forwarding cancelled")
        await audio_queue.put(None)
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error in audio input forwarding: %s", exc)
        await audio_queue.put(None)
        raise


__all__ = ["forward_audio_input"]
