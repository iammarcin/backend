"""Dependency wiring for Blood FastAPI endpoints."""

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
    require_blood_session_factory,
)

from .repositories import BloodRepositoryCollection, build_repositories
from .service import BloodService

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency, initialising it on demand."""

    global _session_dependency

    if _session_dependency is None:
        try:
            factory: AsyncSessionFactory = require_blood_session_factory()
        except ConfigurationError as exc:
            logger.error("BLOOD_DB_URL is missing; cannot create Blood session dependency")
            raise ConfigurationError(
                "BLOOD_DB_URL must be configured before accessing Blood endpoints",
                key="BLOOD_DB_URL",
            ) from exc

        logger.debug("Initialising Blood session dependency")
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_blood_session() -> AsyncIterator[AsyncSession]:
    """Yield an :class:`AsyncSession` for Blood feature operations."""

    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session


def get_blood_repositories() -> BloodRepositoryCollection:
    """Provide repository instances for Blood feature dependencies."""

    return build_repositories()


def get_blood_service(
    repositories: BloodRepositoryCollection = Depends(get_blood_repositories),
) -> BloodService:
    """Resolve a :class:`BloodService` wired with concrete repositories."""

    return BloodService(repositories=repositories)


__all__ = ["get_blood_session", "get_blood_repositories", "get_blood_service"]
