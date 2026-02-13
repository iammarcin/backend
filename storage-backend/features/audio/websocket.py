"""WebSocket endpoint exposing Deepgram speech-to-text streaming."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from core.exceptions import ServiceError
from core.observability import log_websocket_request, render_payload_preview
from core.streaming.manager import StreamingManager
from features.audio.service import STTService

logger = logging.getLogger(__name__)


async def send_to_frontend(
    queue: asyncio.Queue,
    websocket: WebSocket,
    recording_id: str | None = None,
) -> None:
    """Forward transcription events from the queue to the client."""

    try:
        while True:
            message = await queue.get()
            if message is None:
                await websocket.send_json({
                    "type": "transcription_complete",
                    "content": "",
                    "recording_id": recording_id,
                })
                break

            if isinstance(message, dict):
                await websocket.send_json(message)
            elif isinstance(message, (bytes, bytearray)):
                await websocket.send_bytes(message)
            else:
                await websocket.send_json({"type": "message", "content": str(message)})
    except WebSocketDisconnect:  # pragma: no cover - managed by FastAPI
        logger.info("Frontend disconnected while sending transcription")
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Failed to send transcription data: %s", exc, exc_info=True)


async def websocket_stt_endpoint(websocket: WebSocket) -> None:
    """Primary WebSocket endpoint for speech-to-text streaming."""

    log_websocket_request(websocket, logger=logger, label="STT websocket")

    await websocket.accept()
    logger.info("STT WebSocket connection accepted")

    service = STTService()
    manager = StreamingManager()
    completion_token = manager.create_completion_token()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    manager.add_queue(frontend_queue)

    tasks: list[asyncio.Task] = []

    try:
        settings_message: Dict[str, Any] = await websocket.receive_json()
        logger.info("Received STT configuration request")
        logger.debug("STT configuration payload: %s", render_payload_preview(settings_message))

        service.configure(settings_message)
        mode = str(settings_message.get("mode", "non-realtime"))
        # Extract recording_id for ACK correlation (native offline sync)
        recording_id = settings_message.get("recording_id")

        await websocket.send_json({"type": "websocket_ready", "content": "STT ready"})

        audio_source = service.websocket_audio_source(websocket)

        transcription_task = asyncio.create_task(
            service.transcribe_stream(audio_source=audio_source, manager=manager, mode=mode)
        )
        tasks.append(transcription_task)

        frontend_task = asyncio.create_task(
            send_to_frontend(frontend_queue, websocket, recording_id=recording_id)
        )
        tasks.append(frontend_task)

        await asyncio.gather(*tasks)
        logger.info("STT WebSocket session finished successfully")
    except WebSocketDisconnect:
        logger.info("Client disconnected from STT WebSocket")
    except ServiceError as exc:
        logger.error("STT service error: %s", exc)
        with suppress(Exception):
            await websocket.send_json({"type": "error", "content": str(exc)})
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("STT WebSocket error: %s", exc, exc_info=True)
        with suppress(Exception):
            await websocket.send_json({"type": "error", "content": f"STT error: {exc}"})
    finally:
        with suppress(Exception):
            await manager.signal_completion(token=completion_token)
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            with suppress(Exception):
                await asyncio.gather(*tasks, return_exceptions=True)

        with suppress(Exception):
            await websocket.close()
        logger.info("STT WebSocket connection closed")
