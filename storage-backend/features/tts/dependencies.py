"""Dependency helpers for the TTS feature."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from fastapi import WebSocket

from .service import TTSService


@lru_cache(maxsize=1)
def _tts_service_singleton() -> TTSService:
    return TTSService()


def get_tts_service() -> TTSService:
    """Return a cached instance of :class:`TTSService`."""

    return _tts_service_singleton()


async def get_current_user(websocket: WebSocket) -> Dict[str, Any]:
    """Authenticate the websocket and return the auth context."""

    from features.chat.websocket import authenticate_websocket

    return await authenticate_websocket(websocket)


__all__ = ["get_tts_service", "get_current_user"]
