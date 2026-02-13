"""Background task helpers for Garmin/Withings ingestion."""

from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable, Mapping, Sequence

from infrastructure.db.mysql import AsyncSessionFactory, session_scope

from .schemas.queries import GarminDataQuery
from .service import GarminProviderService

logger = logging.getLogger(__name__)

DEFAULT_SYNC_DATASETS: tuple[str, ...] = ("sleep", "summary", "body_composition")


async def run_nightly_sync(
    provider_service: GarminProviderService,
    session_factory: AsyncSessionFactory,
    customer_id: int,
    *,
    target_date: date | None = None,
    datasets: Sequence[str] | None = None,
) -> dict[str, Mapping[str, object]]:
    """Run a nightly ingestion cycle for Garmin datasets.

    The helper is designed so it can be scheduled via APScheduler, Celery, or any
    other orchestration framework that can await an async callable. Results are
    returned as a dictionary keyed by dataset name, enabling metrics/alerts to
    consume the summary without scraping logs.
    """

    run_date = target_date or date.today()
    dataset_list = tuple(datasets) if datasets else DEFAULT_SYNC_DATASETS
    summary: dict[str, Mapping[str, object]] = {}
    query = GarminDataQuery(start_date=run_date, end_date=run_date)

    async with session_scope(session_factory) as session:
        for dataset in dataset_list:
            try:
                result = await provider_service.fetch_dataset(
                    dataset,
                    query,
                    customer_id=customer_id,
                    save_to_db=True,
                    session=session,
                )
            except Exception as exc:  # pragma: no cover - scheduler logging
                logger.error(
                    "Garmin nightly sync failed",
                    extra={"dataset": dataset, "customer_id": customer_id},
                    exc_info=exc,
                )
                summary[dataset] = {"status": "error", "message": str(exc)}
                continue

            summary[dataset] = {
                "status": "ok",
                "items": len(result.items),
                "saved": result.saved,
            }

    return summary


def build_nightly_sync_job(
    provider_service: GarminProviderService,
    session_factory: AsyncSessionFactory,
    customer_id: int,
    *,
    datasets: Sequence[str] | None = None,
) -> Callable[[], Awaitable[dict[str, Mapping[str, object]]]]:
    """Return a coroutine function suitable for scheduler registration."""

    async def _job() -> dict[str, Mapping[str, object]]:
        return await run_nightly_sync(
            provider_service,
            session_factory,
            customer_id,
            datasets=datasets,
        )

    return _job


__all__ = ["run_nightly_sync", "build_nightly_sync_job", "DEFAULT_SYNC_DATASETS"]

