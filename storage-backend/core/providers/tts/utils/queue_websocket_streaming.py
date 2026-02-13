"""Queue-based WebSocket streaming helpers for ElevenLabs."""

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


async def stream_websocket_audio_from_queue(
    *,
    uri: str,
    text_queue: asyncio.Queue[str | None],
    api_key: str,
    voice_settings: Mapping[str, Any],
    chunk_length_schedule: list[int],
    provider_name: str,
    runtime: Optional["WorkflowRuntime"] = None,
) -> AsyncIterator[bytes]:
    """Yield audio bytes produced by the ElevenLabs websocket endpoint using a text queue."""

    loop = asyncio.get_running_loop()
    audio_queue: asyncio.Queue[object] = asyncio.Queue()
    sentinel = object()

    async def _receive_audio(
        ws: websockets.WebSocketClientProtocol,
    ) -> None:
        """Receive audio payloads from the websocket and enqueue them for consumption."""

        try:
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
                        loop.call_soon_threadsafe(audio_queue.put_nowait, audio_bytes)

                if data.get("status") == "finished":
                    logger.debug("ElevenLabs websocket streaming finished")
                    break
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error receiving ElevenLabs websocket audio: %s", exc)
            raise

    async def _websocket_handler() -> None:
        """Manage websocket connection lifecycle while sending queued text chunks."""

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

                receive_task = asyncio.create_task(_receive_audio(ws))

                chunk_count = 0
                try:
                    while True:
                        # Check cancellation before getting next text chunk
                        if runtime and runtime.is_cancelled():
                            logger.info("%s TTS queue sender cancelled", provider_name)
                            break

                        text_chunk = await text_queue.get()

                        if text_chunk is None:
                            # Check cancellation before sending EOS
                            if runtime and runtime.is_cancelled():
                                logger.info("%s TTS cancelled, stopping EOS transmission", provider_name)
                                break

                            logger.debug(
                                "Received text queue sentinel, sending EOS to ElevenLabs (chunks=%d)",
                                chunk_count,
                            )
                            await ws.send(json.dumps({"text": ""}))
                            break

                        chunk_count += 1
                        await ws.send(json.dumps({"text": text_chunk}))
                except Exception as exc:
                    logger.error("Error sending text chunks to ElevenLabs: %s", exc)
                    raise
                finally:
                    # Allow sufficient time for ElevenLabs to finish generating and streaming
                    # all remaining audio chunks after the EOS signal. Long-form audio (5+ min)
                    # can take significant time to fully deliver. ElevenLabs server-side
                    # inactivity_timeout is typically 180s, so we use 300s as a safe margin.
                    try:
                        await asyncio.wait_for(receive_task, timeout=300.0)
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Timeout (300s) waiting for ElevenLabs audio reception to finish "
                            "(chunks_sent=%d)",
                            chunk_count,
                        )
                        receive_task.cancel()
        except websockets.exceptions.WebSocketException as exc:
            logger.error("ElevenLabs websocket error: %s", exc)
            loop.call_soon_threadsafe(audio_queue.put_nowait, ("websocket_error", exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected ElevenLabs websocket failure: %s", exc, exc_info=True)
            loop.call_soon_threadsafe(audio_queue.put_nowait, ("error", exc))
        finally:
            loop.call_soon_threadsafe(audio_queue.put_nowait, sentinel)

    handler_task = asyncio.create_task(_websocket_handler())

    try:
        while True:
            item = await audio_queue.get()

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
        if not handler_task.done():
            handler_task.cancel()
            with suppress(asyncio.CancelledError):
                await handler_task
        else:
            with suppress(asyncio.CancelledError):
                _ = handler_task.exception()


__all__ = ["stream_websocket_audio_from_queue"]
