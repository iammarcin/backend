"""FastAPI websocket endpoint orchestrating realtime TTS streaming."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from typing import Any, Dict, Optional, Callable

from fastapi import APIRouter, Depends, WebSocket
from fastapi.websockets import WebSocketDisconnect, WebSocketState
from pydantic import ValidationError as PydanticValidationError

from core.observability import log_websocket_request, render_payload_preview
from features.tts.dependencies import get_current_user
from features.tts.schemas.requests import TTSUserSettings

from config.tts.utils import resolve_realtime_settings
from .events import extract_payload, forward_audio_events, send_error
import features.tts.websocket as websocket_module

logger = logging.getLogger(__name__)

websocket_router = APIRouter(prefix="/tts", tags=["TTS"])


@websocket_router.websocket("/ws")
async def tts_websocket_endpoint(
    websocket: WebSocket,
    auth_context: Dict[str, Any] = Depends(get_current_user),
) -> None:
    """Handle websocket requests for ElevenLabs realtime text-to-speech."""

    log_websocket_request(websocket, logger=logger, label="TTS websocket")

    await websocket.accept()
    await websocket.send_json({"type": "websocket_ready", "message": "tts websocket ready"})

    try:
        init_message = await websocket.receive_json()
    except WebSocketDisconnect:
        logger.debug("Client disconnected before sending init message")
        return
    logger.debug("Received TTS websocket init payload: %s", render_payload_preview(init_message))

    if init_message.get("type") != "init":
        await send_error(websocket, "Expected init message as the first payload")
        with suppress(Exception):
            await websocket.close(code=1002)
        return

    payload = extract_payload(init_message)
    logger.debug("Normalised TTS websocket init payload: %s", render_payload_preview(payload))
    customer_id = int(
        payload.get("customer_id")
        or auth_context.get("customer_id", 1)
    )
    session_id = payload.get("session_id")

    try:
        settings_payload = payload.get("user_settings") or {}
        user_settings = TTSUserSettings.model_validate(settings_payload)
    except PydanticValidationError as exc:
        await send_error(websocket, "Invalid user settings", details=exc.errors())
        with suppress(Exception):
            await websocket.close(code=1003)
        return
    except Exception as exc:  # pragma: no cover - defensive
        await send_error(websocket, "Failed to parse settings", details=str(exc))
        with suppress(Exception):
            await websocket.close(code=1011)
        return

    realtime_settings = resolve_realtime_settings(user_settings)

    await websocket.send_json(
        {
            "type": "status",
            "status": "initialised",
            "provider": "elevenlabs",
            "model": realtime_settings.model,
            "voice": realtime_settings.voice,
            "format": realtime_settings.audio_format,
            "session_id": session_id,
            "customer_id": customer_id,
        }
    )

    text_queue: asyncio.Queue[str | None] = asyncio.Queue()
    audio_queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    stop_event = asyncio.Event()
    timings: Dict[str, float] = {}

    client_factory: Callable[[Any], Any] = getattr(
        websocket_module,
        "ElevenLabsRealtimeClient",
    )
    client = client_factory(realtime_settings)
    audio_forwarder = asyncio.create_task(
        forward_audio_events(
            websocket,
            audio_queue,
            provider="elevenlabs",
            model=realtime_settings.model,
            voice=realtime_settings.voice,
            audio_format=realtime_settings.audio_format,
        )
    )
    client_task = asyncio.create_task(
        client.run(text_queue, audio_queue, timings, stop_event)
    )

    initial_text = payload.get("text")
    if isinstance(initial_text, str) and initial_text.strip():
        await text_queue.put(initial_text)

    try:
        while True:
            message = await websocket.receive_json()
            logger.debug(
                "Received TTS websocket payload (session=%s): %s",
                session_id or "<unknown>",
                render_payload_preview(message),
            )
            msg_type = message.get("type")

            if msg_type == "send_text":
                text = message.get("text")
                if not isinstance(text, str) or not text.strip():
                    await send_error(websocket, "send_text payload must include non-empty text")
                    continue
                await text_queue.put(text)
            elif msg_type == "stop":
                stop_event.set()
                await text_queue.put(None)
                break
            else:
                await send_error(websocket, f"Unsupported message type: {msg_type}")
    except WebSocketDisconnect:
        logger.info("TTS websocket disconnected (customer=%s, session=%s)", customer_id, session_id)
        stop_event.set()
        await text_queue.put(None)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unhandled error in TTS websocket loop")
        stop_event.set()
        await text_queue.put(None)
        await send_error(websocket, "Internal server error", details=str(exc))

    results = await asyncio.gather(client_task, return_exceptions=True)
    if results and isinstance(results[0], Exception):
        logger.error("ElevenLabs realtime client failed: %s", results[0])
        await send_error(websocket, "ElevenLabs realtime client failed", details=str(results[0]))

    await audio_queue.put(None)
    await audio_forwarder

    if "tts_completed_time" not in timings:
        timings["tts_completed_time"] = time.time()

    total_duration: Optional[float] = None
    start_time = timings.get("tts_request_sent_time")
    completed_time = timings.get("tts_completed_time")
    if start_time and completed_time:
        total_duration = completed_time - start_time

    telemetry = {
        "tts_request_sent_time": start_time,
        "tts_first_response_time": timings.get("tts_first_response_time"),
        "tts_completed_time": completed_time,
        "total_duration": total_duration,
    }

    if websocket.application_state == WebSocketState.CONNECTED:
        await websocket.send_json(
            {
                "type": "status",
                "status": "completed",
                "provider": "elevenlabs",
                "model": realtime_settings.model,
                "voice": realtime_settings.voice,
                "format": realtime_settings.audio_format,
                "timings": {k: v for k, v in telemetry.items() if v is not None},
            }
        )
        with suppress(Exception):
            await websocket.close(code=1000)


__all__ = ["tts_websocket_endpoint", "websocket_router"]
