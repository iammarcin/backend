"""FastAPI dependencies for proactive agent feature."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
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
from features.proactive_agent.repositories import ProactiveAgentRepository

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency for the main database."""
    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_main_session_factory()
        except ConfigurationError as exc:
            logger.error("MAIN_DB_URL is missing; cannot create proactive agent session dependency")
            raise ConfigurationError(
                "MAIN_DB_URL must be configured before accessing proactive agent sessions",
                key="MAIN_DB_URL",
            ) from exc

        logger.debug("Initialising proactive agent session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_proactive_agent_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession connected to the main database."""
    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session


async def get_proactive_agent_repository(
    session: AsyncSession = Depends(get_proactive_agent_session),
) -> ProactiveAgentRepository:
    """Provide ProactiveAgentRepository dependency."""
    return ProactiveAgentRepository(session)


@asynccontextmanager
async def get_db_session_direct() -> AsyncIterator[AsyncSession]:
    """Context manager for direct DB session access outside FastAPI DI.

    Use this when you need a session in WebSocket handlers or background tasks
    where FastAPI dependency injection is not available.

    Usage:
        async with get_db_session_direct() as db:
            repository = ProactiveAgentRepository(db)
            messages = await repository.get_new_agent_messages(...)
    """
    try:
        factory: AsyncSessionFactory = require_main_session_factory()
    except ConfigurationError as exc:
        logger.error("MAIN_DB_URL not configured for direct session access")
        raise

    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


__all__ = [
    "get_proactive_agent_repository",
    "get_proactive_agent_session",
    "get_db_session_direct",
]
