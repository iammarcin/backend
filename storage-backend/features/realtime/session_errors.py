"""Utilities for sending structured realtime errors to websocket clients."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import WebSocket

from .errors import RealtimeError
from .metrics import RealtimeMetricsCollector

logger = logging.getLogger(__name__)


async def send_realtime_error(
    *,
    websocket: WebSocket,
    session_id: str,
    error: RealtimeError,
    close_reason: str,
    close_code: int = 1011,
    metrics: Optional[RealtimeMetricsCollector] = None,
) -> None:
    """Send an error payload to the websocket and close the connection."""

    logger.error(error.to_log_message())
    await websocket.send_json(error.to_client_payload())
    if metrics:
        metrics.record_error(error.code.value)
        metrics.cleanup()
    await websocket.close(code=close_code, reason=close_reason)


__all__ = ["send_realtime_error"]

