"""Async audio chunk sources consumed by the speech-to-text streaming flow.

The helpers expose reusable generators for websocket and queue based audio
ingestion, keeping :class:`STTService` light-weight.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
from typing import AsyncIterator, Optional, TYPE_CHECKING, Any

from fastapi import WebSocket, WebSocketDisconnect

from features.audio.deepgram_helpers import parse_control_message

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from features.chat.utils.websocket_runtime import WorkflowRuntime

logger = logging.getLogger(__name__)


async def websocket_audio_source(
    websocket: WebSocket,
    *,
    runtime: "WorkflowRuntime | None" = None,
) -> AsyncIterator[bytes | None]:
    """Yield audio bytes received over a FastAPI WebSocket connection."""

    chunk_count = 0
    audio_queue: Optional[asyncio.Queue[Any]] = None
    if runtime is not None:
        audio_queue = runtime.get_audio_queue()
        if audio_queue is None:
            raise RuntimeError("Audio runtime configured without an audio queue")

    try:
        while True:
            if audio_queue is not None:
                message = await audio_queue.get()
                if message is None:
                    logger.debug("Audio queue received sentinel; stopping stream")
                    break
            else:
                message = await websocket.receive()

            message_type = message.get("type")

            if message_type == "websocket.disconnect":
                logger.info("Client disconnected from STT audio stream")
                break

            if "bytes" in message and message["bytes"] is not None:
                audio_bytes = message["bytes"]
                chunk_count += 1
                yield audio_bytes
                continue

            text_data = message.get("text")
            if not text_data:
                continue

            try:
                payload = json.loads(text_data)
            except json.JSONDecodeError:
                payload = {"type": text_data}

            msg_type = str(payload.get("type", "")).lower()

            if msg_type == "audio_chunk":
                base64_data = payload.get("data")
                if not base64_data:
                    logger.warning("Received audio_chunk event without data payload")
                    continue

                try:
                    audio_bytes = base64.b64decode(base64_data, validate=True)
                except binascii.Error as exc:
                    logger.error("Failed to decode audio chunk: %s", exc)
                    continue

                chunk_count += 1
                logger.debug(
                    "Decoded audio chunk %s from websocket client (bytes=%s)",
                    chunk_count,
                    len(audio_bytes),
                )
                yield audio_bytes
                continue

            event = parse_control_message(payload)
            if event == "stop":
                # Extract recording_id for ACK correlation (native offline sync)
                recording_id = payload.get("recording_id")
                if recording_id and runtime is not None:
                    logger.debug("RecordingFinished contains recording_id: %s", recording_id)
                    runtime.set_recording_id(recording_id)

                # Capture final_attachments from RecordingFinished if present
                # (attachments added DURING recording are sent with the stop signal)
                final_attachments = payload.get("final_attachments")
                if final_attachments and runtime is not None:
                    logger.info(
                        "RecordingFinished contains %d final attachments",
                        len(final_attachments),
                    )
                    runtime.set_final_attachments(final_attachments)

                # Capture additional_text typed/pasted during recording
                additional_text = payload.get("additional_text")
                if additional_text and runtime is not None:
                    logger.info("RecordingFinished contains additional_text (%d chars)", len(additional_text))
                    runtime.set_additional_text(additional_text)
                logger.info("Received stop signal from audio websocket client")
                break
            if event == "ping":
                logger.debug("Received ping from audio websocket client")
                continue

            logger.debug("Ignoring non-audio websocket message: %s", payload)
    except WebSocketDisconnect:  # pragma: no cover - FastAPI handles disconnects
        logger.info("WebSocket disconnected during audio streaming")
    except asyncio.CancelledError:
        logger.info("websocket_audio_source cancelled")
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error in websocket_audio_source: %s", exc, exc_info=True)
    finally:
        if chunk_count:
            logger.info("Audio stream completed after %s chunks", chunk_count)
        else:
            logger.warning("Audio stream ended without receiving any chunks from client")
        return


async def queue_audio_source(audio_queue: "asyncio.Queue[bytes | None]") -> AsyncIterator[bytes | None]:
    """Yield audio chunks from an ``asyncio.Queue`` source."""

    try:
        while True:
            audio_data = await audio_queue.get()
            if audio_data is None:
                logger.info("Audio queue signalled completion")
                break
            yield audio_data
    except asyncio.CancelledError:
        logger.info("queue_audio_source cancelled")
        raise
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error reading from audio queue: %s", exc, exc_info=True)
    finally:
        return


__all__ = ["queue_audio_source", "websocket_audio_source"]
