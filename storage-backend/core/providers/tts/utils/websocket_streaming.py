"""WebSocket streaming helpers for ElevenLabs."""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping, Optional

import websockets

from core.exceptions import ProviderError

if TYPE_CHECKING:
    from features.chat.utils.websocket_runtime import WorkflowRuntime


logger = logging.getLogger(__name__)


async def stream_websocket_audio(
    *,
    uri: str,
    text: str,
    api_key: str,
    voice_settings: Mapping[str, Any],
    chunk_length_schedule: list[int],
    provider_name: str,
    runtime: Optional["WorkflowRuntime"] = None,
) -> AsyncIterator[bytes]:
    """Yield audio bytes produced by the ElevenLabs websocket streaming endpoint."""

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()

    async def _websocket_handler() -> None:
        """Manage websocket connection lifecycle and enqueue audio chunks."""

        try:
            async with websockets.connect(uri) as ws:
                initial_message = {
                    "text": " ",
                    "voice_settings": dict(voice_settings),
                    "generation_config": {
                        "chunk_length_schedule": chunk_length_schedule,
                    },
                    "xi_api_key": api_key,
                }
                await ws.send(json.dumps(initial_message))
                logger.debug("Sent initial ElevenLabs websocket configuration")

                # Check cancellation before sending text
                if runtime and runtime.is_cancelled():
                    logger.info("%s TTS cancelled, stopping text transmission", provider_name)
                    return

                await ws.send(json.dumps({"text": text}))
                logger.debug("Sent ElevenLabs websocket text: %s", text[:50])

                # Check cancellation before sending EOS
                if runtime and runtime.is_cancelled():
                    logger.info("%s TTS cancelled, stopping EOS transmission", provider_name)
                    return

                await ws.send(json.dumps({"text": ""}))
                logger.debug("Sent ElevenLabs websocket EOS signal")

                async for message in ws:
                    # Check cancellation before processing each message
                    if runtime and runtime.is_cancelled():
                        logger.info("%s TTS cancelled during audio reception", provider_name)
                        break

                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError as exc:
                        logger.warning("Failed to decode ElevenLabs websocket message: %s", exc)
                        continue

                    audio_payload = data.get("audio")
                    if audio_payload:
                        try:
                            audio_bytes = base64.b64decode(audio_payload)
                        except (ValueError, binascii.Error) as exc:
                            logger.warning("Failed to decode ElevenLabs audio chunk: %s", exc)
                        else:
                            loop.call_soon_threadsafe(queue.put_nowait, audio_bytes)

                    if data.get("status") == "finished":
                        logger.debug("ElevenLabs websocket streaming finished")
                        break

        except websockets.exceptions.WebSocketException as exc:
            logger.error("ElevenLabs websocket error: %s", exc)
            loop.call_soon_threadsafe(queue.put_nowait, ("websocket_error", exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected ElevenLabs websocket failure: %s", exc, exc_info=True)
            loop.call_soon_threadsafe(queue.put_nowait, ("error", exc))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, sentinel)

    task = asyncio.create_task(_websocket_handler())

    try:
        while True:
            item = await queue.get()

            if item is sentinel:
                break

            if isinstance(item, tuple):
                label, exc = item
                if label == "websocket_error":
                    raise ProviderError(
                        f"ElevenLabs WebSocket error: {exc}",
                        provider=provider_name,
                        original_error=exc,
                    ) from exc
                raise ProviderError(
                    "ElevenLabs WebSocket streaming failed",
                    provider=provider_name,
                    original_error=exc,
                ) from exc

            if isinstance(item, bytes) and item:
                yield item
    finally:
        if not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        else:
            with suppress(asyncio.CancelledError):
                _ = task.exception()


__all__ = ["stream_websocket_audio"]
