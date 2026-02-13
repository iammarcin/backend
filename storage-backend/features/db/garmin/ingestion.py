"""Async ingestion helpers for Garmin datasets.

These helpers encapsulate the logic that validates and stores incoming payloads
so that :mod:`service` can focus on wiring dependencies together.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from features.garmin.results import IngestResult
if TYPE_CHECKING:
    from features.garmin.schemas.requests import (
        ActivityGpsRequest,
        ActivityRequest,
        BodyCompositionRequest,
        DailyHealthEventsRequest,
        EnduranceScoreRequest,
        FitnessAgeRequest,
        HRVRequest,
        SleepIngestRequest,
        TrainingReadinessRequest,
        TrainingStatusRequest,
        UserSummaryRequest,
    )

logger = logging.getLogger(__name__)


class GarminIngestionMixin:
    """Provide Garmin ingestion flows for services with repository attributes."""

    _sleep_repo: Any
    _summary_repo: Any
    _training_repo: Any
    _activity_repo: Any

    async def ingest_sleep(
        self,
        session: AsyncSession,
        payload: SleepIngestRequest,
        customer_id: int,
    ) -> IngestResult:
        """Validate and persist Garmin sleep metrics."""

        internal = payload.to_internal()
        record = await self._sleep_repo.upsert_sleep(session, internal, customer_id)
        metadata = {
            "nap_segments": len(internal.get("nap_data") or []),
            "heart_rate_points": len(internal.get("sleep_heart_rate_data") or []),
        }
        logger.debug(
            "Ingested sleep data",
            extra={"customer_id": customer_id, "calendar_date": internal.get("calendar_date")},
        )
        return IngestResult.from_repository("sleep", record, metadata=metadata)

    async def ingest_user_summary(
        self,
        session: AsyncSession,
        payload: UserSummaryRequest,
        customer_id: int,
    ) -> IngestResult:
        """Store daily summary metrics for the Garmin user."""

        internal = payload.to_internal()
        record = await self._summary_repo.upsert_user_summary(session, internal, customer_id)
        metadata = {"total_steps": internal.get("total_steps")}
        return IngestResult.from_repository("user_summary", record, metadata=metadata)

    async def ingest_body_composition(
        self,
        session: AsyncSession,
        payload: BodyCompositionRequest,
        customer_id: int,
    ) -> IngestResult:
        """Persist body composition entries such as weight and body fat."""

        internal = payload.to_internal()
        record = await self._summary_repo.upsert_body_composition(session, internal, customer_id)
        metadata = {"weight": internal.get("weight")}
        return IngestResult.from_repository("body_composition", record, metadata=metadata)

    async def ingest_hrv(
        self,
        session: AsyncSession,
        payload: HRVRequest,
        customer_id: int,
    ) -> IngestResult:
        """Persist heart rate variability measurements."""

        internal = payload.to_internal()
        record = await self._summary_repo.upsert_hrv(session, internal, customer_id)
        metadata = {"weekly_avg": internal.get("hrv_weekly_avg")}
        return IngestResult.from_repository("hrv", record, metadata=metadata)

    async def ingest_training_readiness(
        self,
        session: AsyncSession,
        payload: TrainingReadinessRequest,
        customer_id: int,
    ) -> IngestResult:
        """Save training readiness scores and metadata."""

        internal = payload.to_internal()
        record = await self._training_repo.upsert_training_readiness(session, internal, customer_id)
        metadata = {"score": internal.get("training_readiness_score")}
        return IngestResult.from_repository("training_readiness", record, metadata=metadata)

    async def ingest_endurance_score(
        self,
        session: AsyncSession,
        payload: EnduranceScoreRequest,
        customer_id: int,
    ) -> IngestResult:
        """Save Garmin endurance score insights."""

        internal = payload.to_internal()
        record = await self._training_repo.upsert_endurance_score(session, internal, customer_id)
        metadata = {"score": internal.get("endurance_score")}
        return IngestResult.from_repository("endurance_score", record, metadata=metadata)

    async def ingest_training_status(
        self,
        session: AsyncSession,
        payload: TrainingStatusRequest,
        customer_id: int,
    ) -> IngestResult:
        """Persist daily training status metrics."""

        internal = payload.to_internal()
        record = await self._training_repo.upsert_training_status(session, internal, customer_id)
        metadata = {"acute_load": internal.get("daily_training_load_acute")}
        return IngestResult.from_repository("training_status", record, metadata=metadata)

    async def ingest_fitness_age(
        self,
        session: AsyncSession,
        payload: FitnessAgeRequest,
        customer_id: int,
    ) -> IngestResult:
        """Store Garmin fitness age calculations."""

        internal = payload.to_internal()
        record = await self._training_repo.upsert_fitness_age(session, internal, customer_id)
        metadata = {"fitness_age": internal.get("fitness_age")}
        return IngestResult.from_repository("fitness_age", record, metadata=metadata)

    async def ingest_activity(
        self,
        session: AsyncSession,
        payload: ActivityRequest,
        customer_id: int,
    ) -> IngestResult:
        """Upsert high-level activity summaries."""

        internal = payload.to_internal()
        record = await self._activity_repo.upsert_activity(session, internal, customer_id)
        metadata = {"distance": internal.get("activity_distance")}
        return IngestResult.from_repository("activity", record, metadata=metadata, calendar_attr="calendar_date")

    async def ingest_activity_gps(
        self,
        session: AsyncSession,
        payload: ActivityGpsRequest,
        customer_id: int,
    ) -> IngestResult:
        """Upsert high resolution GPS tracks for an activity."""

        internal = payload.to_internal()
        record = await self._activity_repo.upsert_activity_gps(session, internal, customer_id)
        metadata = {"points": len((internal.get("gps_data") or []))}
        return IngestResult.from_repository("activity_gps", record, metadata=metadata, calendar_attr="calendar_date")

    async def ingest_daily_health_events(
        self,
        session: AsyncSession,
        payload: DailyHealthEventsRequest,
        customer_id: int,
    ) -> IngestResult:
        """Persist daily health event notes (meals, stressors, etc.)."""

        internal = payload.to_internal()
        record = await self._activity_repo.upsert_daily_health_event(session, internal, customer_id)
        metadata = {"last_meal_time": internal.get("last_meal_time")}
        return IngestResult.from_repository("daily_health", record, metadata=metadata)


__all__ = ["GarminIngestionMixin"]
