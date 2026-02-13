"""Repository for Garmin sleep data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError
from features.db.garmin.db_models import SleepData
from features.garmin.types import GarminSleepPayload

from ._base import GarminRepository


class GarminSleepRepository(GarminRepository):
    """Persist and retrieve Garmin sleep metrics."""

    async def upsert_sleep(
        self,
        session: AsyncSession,
        payload: GarminSleepPayload,
        customer_id: int,
    ) -> SleepData:
        """Insert or update a Garmin sleep record for ``customer_id``."""

        calendar_date = payload.get("calendar_date")
        if calendar_date is None:
            raise DatabaseError("calendar_date is required for sleep upsert", operation="garmin.sleep.upsert")

        values = {**payload, "customer_id": customer_id}
        return await self._upsert(
            session,
            SleepData,
            values,
            [SleepData.customer_id == customer_id, SleepData.calendar_date == calendar_date],
            operation="garmin.sleep.upsert",
        )

    async def fetch_sleep(
        self,
        session: AsyncSession,
        customer_id: int,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        descending: bool = False,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[SleepData]:
        """Return sleep rows for ``customer_id`` in the requested range."""

        return await self._fetch(
            session,
            SleepData,
            customer_id,
            start=start,
            end=end,
            descending=descending,
            limit=limit,
            offset=offset,
            operation="garmin.sleep.fetch",
        )


__all__ = ["GarminSleepRepository"]
