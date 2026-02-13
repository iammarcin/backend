"""Dependency wiring for UFC FastAPI endpoints."""

from __future__ import annotations

import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ConfigurationError
from infrastructure.aws.queue import SqsQueueService
from infrastructure.db.mysql import (
    AsyncSessionFactory,
    SessionDependency,
    get_session_dependency,
    require_ufc_session_factory,
)

from .repositories import build_repositories
from .service import UfcService

logger = logging.getLogger(__name__)

_session_dependency: SessionDependency | None = None
_service_instance: UfcService | None = None
_queue_service: SqsQueueService | None = None


def _require_session_factory() -> AsyncSessionFactory:
    """Return the configured UFC session factory or raise a configuration error."""

    # This calls require_ufc_session_factory() which lazily creates the factory
    # using UFC_DB_URL from environment or config/database/urls.py
    return require_ufc_session_factory()


def _resolve_session_dependency() -> SessionDependency:
    """Return the cached FastAPI session dependency, initialising it on demand."""

    global _session_dependency

    if _session_dependency is None:
        logger.debug("Initialising UFC session dependency")
        factory = _require_session_factory()
        _session_dependency = get_session_dependency(factory)

    return _session_dependency


async def get_ufc_session() -> AsyncIterator[AsyncSession]:
    """Yield an :class:`AsyncSession` for UFC database operations."""

    dependency = _resolve_session_dependency()
    async for session in dependency():
        yield session

def _get_queue_service() -> SqsQueueService | None:
    """Return a cached SQS queue service if configuration is present."""

    global _queue_service

    if _queue_service is None:
        try:
            _queue_service = SqsQueueService()
        except ConfigurationError as exc:
            logger.warning("SQS queue service unavailable: %s", exc)
            _queue_service = None

    return _queue_service


def _build_service() -> UfcService:
    repositories = build_repositories()
    queue_service = _get_queue_service()
    return UfcService(repositories=repositories, queue_service=queue_service)


def get_ufc_service() -> UfcService:
    """Return a singleton UFC service for dependency injection."""

    global _service_instance

    if _service_instance is None:
        logger.debug("Creating UfcService singleton for dependency injection")
        _service_instance = _build_service()

    return _service_instance


__all__ = ["get_ufc_service", "get_ufc_session"]
