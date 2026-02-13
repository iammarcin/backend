"""FastAPI dependencies for cc4life feature."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError
from infrastructure.db.mysql import (
    AsyncSessionFactory,
    SessionDependency,
    get_session_dependency,
    require_cc4life_session_factory,
)

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency for the cc4life database."""
    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_cc4life_session_factory()
        except ConfigurationError as exc:
            logger.error("CC4LIFE_DB_URL is missing; cannot create cc4life session dependency")
            raise ConfigurationError(
                "CC4LIFE_DB_URL must be configured before accessing cc4life sessions",
                key="CC4LIFE_DB_URL",
            ) from exc

        logger.debug("Initialising cc4life session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_cc4life_session() -> AsyncIterator[AsyncSession]:
    """Yield an AsyncSession connected to the cc4life database."""
    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session


__all__ = ["get_cc4life_session"]
