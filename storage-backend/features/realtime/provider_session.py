"""Helpers for working with realtime provider sessions."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Callable, Optional

from fastapi import WebSocket

from core.exceptions import ProviderError
from core.providers.realtime.base import BaseRealtimeProvider
from features.realtime.schemas import RealtimeSessionSettings

from .errors import connection_failed_error, internal_error
from .metrics import RealtimeMetricsCollector
from .session_errors import send_realtime_error

logger = logging.getLogger(__name__)


async def resolve_provider(
    *,
    model: str,
    provider_resolver: Callable[[str], BaseRealtimeProvider],
    websocket: WebSocket,
    session_id: str,
) -> BaseRealtimeProvider | None:
    """Return the provider for ``model`` or notify the websocket on failure."""

    try:
        provider = provider_resolver(model)
    except Exception as exc:  # pragma: no cover - defensive
        error = internal_error(exc)
        await send_realtime_error(
            websocket=websocket,
            session_id=session_id,
            error=error,
            close_reason="Provider resolution failed",
        )
        return None

    logger.debug(
        "Resolved realtime provider",
        extra={"provider": provider.name, "model": model},
    )
    return provider


async def open_provider_session(
    *,
    provider: BaseRealtimeProvider,
    handshake_settings: RealtimeSessionSettings,
    websocket: WebSocket,
    session_id: str,
    metrics: Optional[RealtimeMetricsCollector],
) -> bool:
    """Open a provider session, forwarding errors to the websocket on failure."""

    try:
        await provider.open_session(settings=handshake_settings.to_provider_payload())
    except ProviderError as exc:
        error = connection_failed_error(str(exc))
        logger.error(error.to_log_message())
        await send_realtime_error(
            websocket=websocket,
            session_id=session_id,
            error=error,
            close_reason="Provider connection failed",
            metrics=metrics,
        )
        return False
    except Exception as exc:  # pragma: no cover - defensive
        error = internal_error(exc)
        logger.error(error.to_log_message(), exc_info=True)
        await send_realtime_error(
            websocket=websocket,
            session_id=session_id,
            error=error,
            close_reason="Provider initialisation error",
            metrics=metrics,
        )
        return False

    return True


async def shutdown_provider_session(
    *,
    provider: BaseRealtimeProvider,
    receiver_task: asyncio.Task,
    metrics: Optional[RealtimeMetricsCollector],
) -> None:
    """Stop event relay and close the provider session gracefully."""

    if not receiver_task.done():
        try:
            await asyncio.wait_for(receiver_task, timeout=0.5)
        except asyncio.TimeoutError:
            receiver_task.cancel()
            with suppress(asyncio.CancelledError):
                await receiver_task
    else:
        with suppress(asyncio.CancelledError):
            await receiver_task

    with suppress(Exception):
        await provider.close_session()

    if metrics:
        metrics.cleanup()


__all__ = [
    "resolve_provider",
    "open_provider_session",
    "shutdown_provider_session",
]

