"""Utility helpers for sending data over the TTS websocket."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import WebSocket


async def send_error(websocket: WebSocket, message: str, *, details: Any | None = None) -> None:
    """Send a structured error payload to the websocket client."""

    payload: Dict[str, Any] = {"type": "error", "message": message}
    if details is not None:
        payload["details"] = details
    await websocket.send_json(payload)


async def forward_audio_events(
    websocket: WebSocket,
    audio_queue: "asyncio.Queue[dict[str, Any] | None]",
    *,
    provider: str,
    model: str,
    voice: str,
    audio_format: str,
) -> None:
    """Relay audio events produced by the ElevenLabs client to the browser."""

    sequence = 0
    while True:
        payload = await audio_queue.get()
        if payload is None:
            break

        event_type = payload.get("type")
        if event_type == "audio":
            chunk = payload.get("chunk")
            if not chunk:
                continue
            sequence += 1
            await websocket.send_json(
                {
                    "type": "audio_chunk",
                    "chunk": chunk,
                    "format": audio_format,
                    "sequence": sequence,
                    "provider": provider,
                    "model": model,
                    "voice": voice,
                }
            )
        elif event_type == "status":
            status = payload.get("status")
            await websocket.send_json(
                {
                    "type": "status",
                    "status": status,
                    "provider": provider,
                    "model": model,
                    "voice": voice,
                    "details": payload.get("raw"),
                }
            )
        elif event_type == "error":
            await send_error(
                websocket,
                payload.get("message", "ElevenLabs realtime error"),
                details=payload.get("details"),
            )


def extract_payload(message: Dict[str, Any]) -> Dict[str, Any]:
    """Return the nested ``payload`` key when present."""

    if "payload" in message and isinstance(message["payload"], dict):
        return message["payload"]
    return message


__all__ = ["forward_audio_events", "send_error", "extract_payload"]
