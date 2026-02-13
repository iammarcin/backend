"""Realtime feature package exposing dependency helpers."""

from __future__ import annotations

from typing import Callable

from fastapi import Depends

from core.streaming.manager import StreamingManager
from features.chat.dependencies import get_chat_history_service
from features.chat.service import ChatHistoryService
from features.audio.service import STTService
from infrastructure.aws.storage import StorageService

from .service import RealtimeChatService
from .schemas import RealtimeSessionSettings
from core.providers.realtime.factory import get_realtime_provider


def _storage_service_factory() -> StorageService:
    """Factory wrapper used to defer :class:`StorageService` initialisation."""

    return StorageService()


def _stt_service_factory() -> STTService:
    """Factory wrapper returning a speech-to-text service instance."""

    return STTService()


def get_realtime_chat_service(
    chat_history_service: ChatHistoryService = Depends(get_chat_history_service),
) -> RealtimeChatService:
    """FastAPI dependency returning the realtime chat service scaffold."""

    storage_factory: Callable[[], StorageService] = _storage_service_factory
    return RealtimeChatService(
        manager_factory=StreamingManager,
        chat_history_service=chat_history_service,
        storage_service_factory=storage_factory,
        provider_resolver=get_realtime_provider,
        session_defaults=RealtimeSessionSettings(),
        stt_service_factory=_stt_service_factory,
    )


__all__ = ["RealtimeChatService", "get_realtime_chat_service"]
