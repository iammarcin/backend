"""FastAPI dependencies for journal feature."""

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
from features.journal.repository import JournalRepository

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency for the main database."""
    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_main_session_factory()
        except ConfigurationError as exc:
            logger.error("MAIN_DB_URL is missing; cannot create journal session dependency")
            raise ConfigurationError(
                "MAIN_DB_URL must be configured before accessing journal sessions",
                key="MAIN_DB_URL",
            ) from exc

        logger.debug("Initialising journal session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_journal_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession connected to the main database."""
    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session


async def get_journal_repository(
    session: AsyncSession = Depends(get_journal_session),
) -> JournalRepository:
    """Provide JournalRepository dependency."""
    return JournalRepository(session)


__all__ = [
    "get_journal_repository",
    "get_journal_session",
]
