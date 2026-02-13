"""Helpers for relaying provider events back to websocket clients."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from fastapi import WebSocket

from core.exceptions import ProviderError
from core.providers.realtime.base import BaseRealtimeProvider, RealtimeEvent
from features.realtime.state import RealtimeTurnState
from .context import RealtimeTurnContext
from .errors import provider_failure_error
from .metrics import RealtimeMetricsCollector

logger = logging.getLogger(__name__)


async def relay_provider_events(
    *,
    provider: BaseRealtimeProvider,
    websocket: WebSocket,
    session_id: str,
    turn_state: RealtimeTurnState,
    turn_context: RealtimeTurnContext,
    handle_event: Callable[[RealtimeEvent], Awaitable[bool]],
    cancel_event: asyncio.Event,
    metrics: RealtimeMetricsCollector | None = None,
) -> None:
    """Stream provider events to the client and persist completed turns."""

    try:
        async for event in provider.receive_events():
            if cancel_event.is_set():
                logger.info(
                    "Cancellation detected, skipping provider event (session=%s)",
                    session_id,
                )
                turn_context.reset()
                turn_state.mark_cancelled()
                cancel_event.clear()
                turn_state.reset()
                continue

            if metrics:
                metrics.record_provider_event(event.type.value, provider.name)

            should_close = await handle_event(event)
            if should_close:
                logger.info(
                    "Received close signal, exiting provider event loop",
                    extra={"session_id": session_id},
                )
                if not cancel_event.is_set():
                    cancel_event.set()
                break
    except ProviderError as exc:
        error = provider_failure_error(str(exc))
        logger.error(error.to_log_message())
        turn_state.mark_error()
        await websocket.send_json(
            {**error.to_client_payload(), "session_id": session_id}
        )
        if metrics:
            metrics.record_error(error.code.value)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected realtime provider failure: %s", exc)
        turn_state.mark_error()
        await websocket.send_json(
            {
                "type": "realtime.error",
                "session_id": session_id,
                "message": "Realtime provider failure",
            }
        )
        if metrics:
            metrics.record_error("internal_error")
    finally:
        logger.info(
            "Provider event loop exited, awaiting session cleanup",
            extra={"session_id": session_id},
        )
        logger.debug(
            "Provider event relay completed (session=%s)",
            session_id,
        )


__all__ = ["relay_provider_events"]
