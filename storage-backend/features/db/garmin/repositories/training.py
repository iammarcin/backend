"""Repositories for Garmin training metrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from features.db.garmin.db_models import (
    EnduranceScore,
    FitnessAge,
    TrainingReadiness,
    TrainingStatus,
)
from features.garmin.types import (
    GarminEnduranceScorePayload,
    GarminFitnessAgePayload,
    GarminTrainingReadinessPayload,
    GarminTrainingStatusPayload,
)

from ._base import GarminRepository


class GarminTrainingRepository(GarminRepository):
    """Handle writes for Garmin training readiness, endurance, and status tables."""

    async def upsert_training_readiness(
        self,
        session: AsyncSession,
        payload: GarminTrainingReadinessPayload,
        customer_id: int,
    ) -> TrainingReadiness:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for training readiness upsert",
                operation="garmin.training.readiness",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            TrainingReadiness,
            values,
            [TrainingReadiness.customer_id == customer_id, TrainingReadiness.calendar_date == calendar_date],
            operation="garmin.training.readiness",
        )

    async def upsert_endurance_score(
        self,
        session: AsyncSession,
        payload: GarminEnduranceScorePayload,
        customer_id: int,
    ) -> EnduranceScore:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for endurance score upsert",
                operation="garmin.training.endurance",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            EnduranceScore,
            values,
            [EnduranceScore.customer_id == customer_id, EnduranceScore.calendar_date == calendar_date],
            operation="garmin.training.endurance",
        )

    async def upsert_training_status(
        self,
        session: AsyncSession,
        payload: GarminTrainingStatusPayload,
        customer_id: int,
    ) -> TrainingStatus:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for training status upsert",
                operation="garmin.training.status",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            TrainingStatus,
            values,
            [TrainingStatus.customer_id == customer_id, TrainingStatus.calendar_date == calendar_date],
            operation="garmin.training.status",
        )

    async def upsert_fitness_age(
        self,
        session: AsyncSession,
        payload: GarminFitnessAgePayload,
        customer_id: int,
    ) -> FitnessAge:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for fitness age upsert",
                operation="garmin.training.fitness_age",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            FitnessAge,
            values,
            [FitnessAge.customer_id == customer_id, FitnessAge.calendar_date == calendar_date],
            operation="garmin.training.fitness_age",
        )

    async def fetch_training_readiness(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TrainingReadiness]:
        return await self._fetch(
            session,
            TrainingReadiness,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.training.readiness.fetch",
        )

    async def fetch_endurance_score(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[EnduranceScore]:
        return await self._fetch(
            session,
            EnduranceScore,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.training.endurance.fetch",
        )

    async def fetch_training_status(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
        ignore_null_vo2max: bool = False,
        ignore_null_training_load_data: bool = False,
    ) -> list[TrainingStatus]:
        filters = []
        if ignore_null_vo2max:
            filters.append(TrainingStatus.vo2_max_precise_value.is_not(None))
        if ignore_null_training_load_data:
            filters.append(TrainingStatus.monthly_load_anaerobic.is_not(None))

        return await self._fetch(
            session,
            TrainingStatus,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            extra_filters=filters,
            operation="garmin.training.status.fetch",
        )

    async def fetch_fitness_age(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[FitnessAge]:
        return await self._fetch(
            session,
            FitnessAge,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.training.fitness_age.fetch",
        )


__all__ = ["GarminTrainingRepository"]
