"""High-level Garmin database service wiring ingestion and retrieval flows."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ValidationError
from infrastructure.db.mysql import AsyncSessionFactory, session_scope

from .datasets import GarminDatasetRegistry, build_default_dataset_registry
from .ingestion import GarminIngestionMixin
from .repositories import (
    GarminActivityRepository,
    GarminSleepRepository,
    GarminSummaryRepository,
    GarminTrainingRepository,
)
from .retrieval import GarminRetrievalMixin

if TYPE_CHECKING:
    from features.garmin.schemas.requests import GarminRequest

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GarminService(GarminIngestionMixin, GarminRetrievalMixin):
    """Coordinate Garmin ingestion flows across repositories."""

    def __init__(
        self,
        *,
        sleep_repo: GarminSleepRepository | None = None,
        summary_repo: GarminSummaryRepository | None = None,
        training_repo: GarminTrainingRepository | None = None,
        activity_repo: GarminActivityRepository | None = None,
        datasets: GarminDatasetRegistry | None = None,
    ) -> None:
        self._sleep_repo = sleep_repo or GarminSleepRepository()
        self._summary_repo = summary_repo or GarminSummaryRepository()
        self._training_repo = training_repo or GarminTrainingRepository()
        self._activity_repo = activity_repo or GarminActivityRepository()
        self._datasets = datasets or build_default_dataset_registry()

    async def with_session(
        self,
        session_factory: AsyncSessionFactory,
        handler: Callable[[AsyncSession], Awaitable[T]],
    ) -> T:
        """Execute ``handler`` within a managed transaction scope."""

        async with session_scope(session_factory) as session:
            return await handler(session)

    def validate(self, schema: type["GarminRequest"], payload: Mapping[str, Any]) -> "GarminRequest":
        """Validate ``payload`` against ``schema`` raising :class:`ValidationError` on failure."""

        try:
            return schema.model_validate(payload)
        except Exception as exc:  # pragma: no cover - thin wrapper for FastAPI integrations
            logger.debug("Garmin payload validation failed", exc_info=exc)
            raise ValidationError(str(exc)) from exc


__all__ = ["GarminService"]
