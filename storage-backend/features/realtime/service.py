"""Realtime chat service orchestrating websocket conversations."""

from __future__ import annotations

import asyncio
import logging
from typing import Callable, Mapping

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.providers.realtime.base import BaseRealtimeProvider
from core.streaming.manager import StreamingManager
from features.audio.service import STTService
from features.chat.service import ChatHistoryService
from features.realtime.schemas import RealtimeSessionSettings
from infrastructure.aws.storage import StorageService

from .finalise import SessionTracker
from .session_controller import RealtimeSessionController
from .utils import extract_customer_id, generate_session_id

logger = logging.getLogger(__name__)


class RealtimeChatService:
    """Coordinate realtime chat websocket sessions across providers."""

    _MAX_CONCURRENT_SESSIONS = 100

    def __init__(
        self,
        *,
        manager_factory: Callable[[], StreamingManager],
        chat_history_service: ChatHistoryService,
        storage_service_factory: Callable[[], StorageService],
        provider_resolver: Callable[[str], BaseRealtimeProvider],
        session_defaults: RealtimeSessionSettings,
        stt_service_factory: Callable[[], STTService] | None = None,
    ) -> None:
        self._manager_factory = manager_factory
        self._provider_resolver = provider_resolver
        self._session_defaults = session_defaults
        self._chat_history_service = chat_history_service
        self._storage_service_factory = storage_service_factory
        self._stt_service_factory = (
            stt_service_factory or self._default_stt_service_factory
        )
        self._active_sessions: dict[str, str] = {}
        self._open_connections: set[str] = set()

    async def handle_websocket(
        self,
        websocket: WebSocket,
        *,
        initial_message: Mapping[str, object] | None = None,
    ) -> None:
        """Accept a websocket connection and broker realtime traffic."""

        state = getattr(websocket, "application_state", WebSocketState.CONNECTING)
        if state != WebSocketState.CONNECTED:
            accept = getattr(websocket, "accept", None)
            if callable(accept):
                await accept()
        customer_id = extract_customer_id(websocket)
        session_id = generate_session_id()
        logger.info(
            "Realtime websocket initialised",
            extra={"customer_id": customer_id, "session_id": session_id},
        )

        manager = self._manager_factory()
        logger.debug(
            "Initialising StreamingManager for realtime session",
            extra={"manager_id": id(manager), "session_id": session_id},
        )
        manager.reset()
        self._open_connections.add(session_id)

        controller = RealtimeSessionController(
            manager=manager,
            chat_history_service=self._chat_history_service,
            storage_service_factory=self._storage_service_factory,
            stt_service_factory=self._stt_service_factory,
            provider_resolver=self._provider_resolver,
            session_defaults=self._session_defaults,
        )

        session_tracker = self._get_session_tracker(session_id)

        try:
            await controller.run(
                websocket=websocket,
                session_id=session_id,
                customer_id=customer_id,
                initial_message=initial_message,
                session_tracker=session_tracker,
            )
        finally:
            self._active_sessions.pop(session_id, None)
            self._open_connections.discard(session_id)

    def _get_session_tracker(self, websocket_session_id: str) -> SessionTracker:
        """Return a session tracker tied to ``websocket_session_id``."""

        def get_session_id() -> str | None:
            return self._active_sessions.get(websocket_session_id)

        def set_session_id(db_session_id: str) -> None:
            if db_session_id:
                self._active_sessions[websocket_session_id] = db_session_id
            else:
                self._active_sessions.pop(websocket_session_id, None)

        return SessionTracker(get_session_id, set_session_id)

    @staticmethod
    def _default_stt_service_factory() -> STTService:
        """Return a fresh :class:`STTService` instance."""

        return STTService()

    async def check_provider_health(self) -> None:
        """Verify realtime provider dependencies are reachable."""

        provider = self._resolve_provider(self._session_defaults.model)
        health_check = getattr(provider, "check_health", None)
        if callable(health_check):
            result = health_check()
            if asyncio.iscoroutine(result):
                await result

    def can_accept_connections(self) -> bool:
        """Return ``True`` if the service can accept more websocket sessions."""

        return len(self._open_connections) < self._MAX_CONCURRENT_SESSIONS

    def active_session_count(self) -> int:
        """Return the number of websocket sessions currently tracked."""

        return len(self._open_connections)

    def _resolve_provider(self, model: str) -> BaseRealtimeProvider:
        provider = self._provider_resolver(model)
        logger.debug(
            "Resolved realtime provider",
            extra={"provider": provider.name, "model": model},
        )
        return provider


__all__ = ["RealtimeChatService"]
