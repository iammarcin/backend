"""Dependency helpers for the chat feature."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError
from infrastructure.db.mysql import (
    AsyncSessionFactory,
    SessionDependency,
    get_session_dependency,
    require_main_session_factory,
)
from features.chat.service import ChatHistoryService

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency for the main chat database."""

    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_main_session_factory()
        except ConfigurationError as exc:
            logger.error("MAIN_DB_URL is missing; cannot create chat session dependency")
            raise ConfigurationError(
                "MAIN_DB_URL must be configured before accessing chat sessions",
                key="MAIN_DB_URL",
            ) from exc

        logger.debug("Initialising chat session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_chat_session() -> AsyncIterator[AsyncSession]:
    """Yield an :class:`AsyncSession` connected to the main chat database."""

    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session


async def get_chat_history_service(
    session: AsyncSession = Depends(get_chat_session),
) -> ChatHistoryService:
    """FastAPI dependency returning the chat history service."""

    return ChatHistoryService(session)


__all__ = ["get_chat_session", "get_chat_history_service"]
