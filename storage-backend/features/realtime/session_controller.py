"""Session controller orchestrating realtime websocket lifecycles."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Mapping

from fastapi import WebSocket

from core.providers.realtime.base import BaseRealtimeProvider, RealtimeEvent
from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatHistoryService
from features.realtime.schemas import RealtimeSessionSettings
from .event_factory import RealtimeEventFactory
from infrastructure.aws.storage import StorageService

from .client import forward_client_messages
from .events import handle_provider_event
from .finalise import SessionTracker, TurnFinaliser
from .metrics import RealtimeMetricsCollector
from .provider import relay_provider_events
from .provider_session import open_provider_session, resolve_provider
from .session_closer import SessionClosureManager
from .session_startup import initialise_session
from .test_mode import run_test_mode
from .utils import parse_client_payload

logger = logging.getLogger(__name__)


class RealtimeSessionController:
    """Encapsulate the realtime session workflow for a websocket connection."""

    def __init__(
        self,
        *,
        manager: StreamingManager,
        chat_history_service: ChatHistoryService,
        storage_service_factory: Callable[[], StorageService],
        stt_service_factory: Callable[[], STTService],
        provider_resolver: Callable[[str], BaseRealtimeProvider],
        session_defaults: RealtimeSessionSettings,
    ) -> None:
        self._manager = manager
        self._chat_history_service = chat_history_service
        self._storage_service_factory = storage_service_factory
        self._stt_service_factory = stt_service_factory
        self._provider_resolver = provider_resolver
        self._session_defaults = session_defaults
        self._closure = SessionClosureManager()

    async def run(
        self,
        *,
        websocket: WebSocket,
        session_id: str,
        customer_id: int,
        initial_message: Mapping[str, object] | None,
        session_tracker: SessionTracker,
    ) -> None:
        """Execute the realtime session lifecycle until completion or error."""

        startup = initialise_session(
            session_id=session_id,
            customer_id=customer_id,
            session_defaults=self._session_defaults,
            initial_message=initial_message,
        )

        self._closure.prepare(
            websocket=websocket,
            session_id=session_id,
            tracker=session_tracker,
            settings=startup.handshake.settings,
            turn_state=startup.turn_state,
            turn_context=startup.turn_context,
        )

        await websocket.send_json(startup.handshake.model_dump(by_alias=True))

        if startup.provided_session_id:
            session_tracker.set_session_id(startup.provided_session_id)

        event_factory = RealtimeEventFactory(session_id=session_id)

        turn_finaliser = TurnFinaliser(
            chat_history_service=self._chat_history_service,
            storage_service_factory=self._storage_service_factory,
            streaming_manager=self._manager,
            stt_service_factory=self._stt_service_factory,
            session_tracker=session_tracker,
            event_factory=event_factory,
        )

        metrics: RealtimeMetricsCollector | None = None

        async def dispatch_event(event: RealtimeEvent) -> bool:
            should_close = await handle_provider_event(
                event=event,
                websocket=websocket,
                session_id=session_id,
                customer_id=customer_id,
                settings=startup.handshake.settings,
                turn_state=startup.turn_state,
                turn_context=startup.turn_context,
                streaming_manager=self._manager,
                turn_finaliser=turn_finaliser,
                event_factory=event_factory,
                metrics=metrics,
                force_close=False,
            )

            close_signalled = False
            if should_close:
                close_signalled = await self._closure.request_close(
                    force=False, reason="turn_completed"
                )
            else:
                close_signalled = await self._closure.close_if_pending()

            if close_signalled:
                logger.info(
                    "Received close signal, exiting provider event loop",
                    extra={"session_id": session_id},
                )

            return close_signalled or self._closure.is_closed()

        if startup.handshake.settings.return_test_data:
            await run_test_mode(
                websocket=websocket,
                session_id=session_id,
                customer_id=customer_id,
                turn_state=startup.turn_state,
                turn_context=startup.turn_context,
                settings=startup.handshake.settings,
                parse_payload=parse_client_payload,
                handle_event=dispatch_event,
            )
            return

        provider = await resolve_provider(
            model=startup.handshake.settings.model,
            provider_resolver=self._provider_resolver,
            websocket=websocket,
            session_id=session_id,
        )
        if provider is None:
            return

        metrics = RealtimeMetricsCollector(session_id=session_id, customer_id=customer_id)
        input_audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        await provider.set_input_audio_queue(input_audio_queue)

        session_opened = await open_provider_session(
            provider=provider,
            handshake_settings=startup.handshake.settings,
            websocket=websocket,
            session_id=session_id,
            metrics=metrics,
        )
        if not session_opened:
            return

        cancel_event = asyncio.Event()
        receiver_task = asyncio.create_task(
            relay_provider_events(
                provider=provider,
                websocket=websocket,
                session_id=session_id,
                turn_state=startup.turn_state,
                turn_context=startup.turn_context,
                handle_event=dispatch_event,
                cancel_event=cancel_event,
                metrics=metrics,
            )
        )
        self._closure.attach_provider(
            provider=provider,
            receiver_task=receiver_task,
            cancel_event=cancel_event,
            metrics=metrics,
        )

        try:
            await forward_client_messages(
                websocket=websocket,
                provider=provider,
                session_id=session_id,
                turn_state=startup.turn_state,
                parse_payload=parse_client_payload,
                input_audio_queue=input_audio_queue,
                cancel_event=cancel_event,
                initial_payload=startup.initial_payload,
                metrics=metrics,
                request_session_close=self.request_session_close,
            )
        finally:
            logger.info(
                "Starting realtime session cleanup (session=%s)",
                session_id,
                extra={"session_id": session_id},
            )
            cleanup_start = time.time()
            try:
                await self._closure.ensure_closed()
            except Exception as cleanup_exc:  # pragma: no cover - defensive logging
                cleanup_duration_ms = (time.time() - cleanup_start) * 1000
                logger.error(
                    "Realtime session cleanup failed after %.2fms (session=%s): %s",
                    cleanup_duration_ms,
                    session_id,
                    cleanup_exc,
                    extra={
                        "session_id": session_id,
                        "cleanup_duration_ms": cleanup_duration_ms,
                        "exception_type": type(cleanup_exc).__name__,
                    },
                    exc_info=True,
                )
            else:
                cleanup_duration_ms = (time.time() - cleanup_start) * 1000
                logger.info(
                    "Realtime session cleanup completed in %.2fms (session=%s)",
                    cleanup_duration_ms,
                    session_id,
                    extra={
                        "session_id": session_id,
                        "cleanup_duration_ms": cleanup_duration_ms,
                    },
                )

    async def request_session_close(
        self, force: bool = False, reason: str | None = None
    ) -> bool:
        return await self._closure.request_close(force=force, reason=reason)


__all__ = ["RealtimeSessionController"]
