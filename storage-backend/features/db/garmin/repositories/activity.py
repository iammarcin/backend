"""Repositories for Garmin activity data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from features.db.garmin.db_models import (
    ActivityData,
    ActivityGPSData,
    DailyHealthEvents,
)
from features.garmin.types import (
    GarminActivityGpsPayload,
    GarminActivityPayload,
    GarminDailyHealthEventsPayload,
)

from ._base import GarminRepository


class GarminActivityRepository(GarminRepository):
    """Manage Garmin activity tables and related payloads."""

    async def upsert_activity(
        self,
        session: AsyncSession,
        payload: GarminActivityPayload,
        customer_id: int,
    ) -> ActivityData:
        activity_id = payload.get("activity_id")
        if activity_id is None:
            raise DatabaseError("activity_id is required for activity upsert", operation="garmin.activity")

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            ActivityData,
            values,
            [ActivityData.activity_id == activity_id],
            operation="garmin.activity",
        )

    async def upsert_activity_gps(
        self,
        session: AsyncSession,
        payload: GarminActivityGpsPayload,
        customer_id: int,
    ) -> ActivityGPSData:
        activity_id = payload.get("activity_id")
        if activity_id is None:
            raise DatabaseError("activity_id is required for activity GPS upsert", operation="garmin.activity_gps")

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            ActivityGPSData,
            values,
            [ActivityGPSData.activity_id == activity_id],
            operation="garmin.activity_gps",
        )

    async def upsert_daily_health_event(
        self,
        session: AsyncSession,
        payload: GarminDailyHealthEventsPayload,
        customer_id: int,
    ) -> DailyHealthEvents:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for daily health events upsert",
                operation="garmin.daily_health",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            DailyHealthEvents,
            values,
            [DailyHealthEvents.customer_id == customer_id, DailyHealthEvents.calendar_date == calendar_date],
            operation="garmin.daily_health",
        )

    async def fetch_activity(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
        activity_id: int | None = None,
    ) -> list[ActivityData]:
        filters = []
        if activity_id is not None:
            filters.append(ActivityData.activity_id == activity_id)

        return await self._fetch(
            session,
            ActivityData,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            extra_filters=filters,
            operation="garmin.activity.fetch",
        )

    async def fetch_activity_gps(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
        activity_id: int | None = None,
    ) -> list[ActivityGPSData]:
        filters = []
        if activity_id is not None:
            filters.append(ActivityGPSData.activity_id == activity_id)

        return await self._fetch(
            session,
            ActivityGPSData,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            extra_filters=filters,
            operation="garmin.activity_gps.fetch",
        )

    async def fetch_daily_health_events(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DailyHealthEvents]:
        return await self._fetch(
            session,
            DailyHealthEvents,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.daily_health.fetch",
        )


__all__ = ["GarminActivityRepository"]
