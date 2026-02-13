"""Repositories for Garmin daily summary style tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from features.db.garmin.db_models import BodyComposition, HRVData, UserSummary
from features.garmin.types import (
    GarminBodyCompositionPayload,
    GarminHRVPayload,
    GarminUserSummaryPayload,
)

from ._base import GarminRepository


class GarminSummaryRepository(GarminRepository):
    """Handle idempotent writes for Garmin summary tables."""

    async def upsert_user_summary(
        self,
        session: AsyncSession,
        payload: GarminUserSummaryPayload,
        customer_id: int,
    ) -> UserSummary:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for user summary upsert",
                operation="garmin.summary.user",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            UserSummary,
            values,
            [UserSummary.customer_id == customer_id, UserSummary.calendar_date == calendar_date],
            operation="garmin.summary.user",
        )

    async def upsert_body_composition(
        self,
        session: AsyncSession,
        payload: GarminBodyCompositionPayload,
        customer_id: int,
    ) -> BodyComposition:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for body composition upsert",
                operation="garmin.summary.body",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            BodyComposition,
            values,
            [BodyComposition.customer_id == customer_id, BodyComposition.calendar_date == calendar_date],
            operation="garmin.summary.body",
        )

    async def upsert_hrv(
        self,
        session: AsyncSession,
        payload: GarminHRVPayload,
        customer_id: int,
    ) -> HRVData:
        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError(
                "calendar_date is required for HRV upsert",
                operation="garmin.summary.hrv",
            )

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            HRVData,
            values,
            [HRVData.customer_id == customer_id, HRVData.calendar_date == calendar_date],
            operation="garmin.summary.hrv",
        )

    async def fetch_user_summary(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[UserSummary]:
        return await self._fetch(
            session,
            UserSummary,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.summary.user.fetch",
        )

    async def fetch_body_composition(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[BodyComposition]:
        return await self._fetch(
            session,
            BodyComposition,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.summary.body.fetch",
        )

    async def fetch_hrv(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[HRVData]:
        return await self._fetch(
            session,
            HRVData,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.summary.hrv.fetch",
        )


__all__ = ["GarminSummaryRepository"]
