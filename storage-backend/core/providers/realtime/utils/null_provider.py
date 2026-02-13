"""Utility helpers and placeholder implementations for realtime providers."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Mapping

from ..base import BaseRealtimeProvider, RealtimeEvent, RealtimeEventType

logger = logging.getLogger(__name__)


class NullRealtimeProvider(BaseRealtimeProvider):
    """Fallback provider used while concrete integrations are under development."""

    name = "null"

    async def open_session(self, *, settings: Mapping[str, object]) -> None:
        logger.info("Initialising null realtime provider with settings: %s", settings)

    async def close_session(self) -> None:
        logger.info("Closing null realtime provider session")

    async def send_user_event(self, payload: Mapping[str, object]) -> None:
        logger.debug("Null provider received user payload: %s", payload)

    async def receive_events(self) -> AsyncIterator[RealtimeEvent]:
        logger.debug("Null provider yielding no realtime events")
        if False:  # pragma: no cover - never executed, keeps generator type
            yield RealtimeEvent(RealtimeEventType.CONTROL, {})

    async def set_input_audio_queue(self, queue: asyncio.Queue[bytes | None]) -> None:
        logger.debug("Null provider received audio queue with size=%s", queue.qsize())


__all__ = ["NullRealtimeProvider"]
