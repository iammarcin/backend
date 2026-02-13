"""Dataset registry and fetch orchestration helpers for Garmin ingestion."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Awaitable, Callable, Iterable, Mapping

from core.providers.garmin import GarminConnectClient
from core.providers.withings import WithingsClient
from features.garmin.schemas.queries import GarminDataQuery
from features.garmin.schemas.requests import (
    ActivityGpsRequest,
    ActivityRequest,
    BodyCompositionRequest,
    DailyHealthEventsRequest,
    EnduranceScoreRequest,
    FitnessAgeRequest,
    GarminRequest,
    HRVRequest,
    SleepIngestRequest,
    TrainingReadinessRequest,
    TrainingStatusRequest,
    UserSummaryRequest,
)
from features.garmin.translators import (
    translate_activity,
    translate_activity_gps,
    translate_body_composition,
    translate_daily_health_events,
    translate_endurance_score,
    translate_fitness_age,
    translate_hrv,
    translate_sleep,
    translate_summary,
    translate_training_readiness,
    translate_training_load_balance,
    translate_training_status,
)
from features.garmin.translators.performance import translate_max_metrics

from features.garmin import dataset_fetchers as fetchers

logger = logging.getLogger(__name__)

Translator = Callable[[Any, GarminDataQuery], Iterable[Mapping[str, Any]]]
Fetcher = Callable[["GarminDatasetContext", "FetchWindow", GarminDataQuery], Any | Awaitable[Any]]


@dataclass(slots=True)
class FetchWindow:
    """Normalized time span and optional display name for dataset fetches."""

    start: date
    end: date
    display_name: str | None


@dataclass(slots=True)
class GarminDatasetContext:
    """Runtime dependencies required for dataset fetchers."""

    client: GarminConnectClient
    withings: WithingsClient | None = None


@dataclass(slots=True)
class DatasetConfig:
    """Runtime configuration for Garmin dataset orchestration."""

    translator: Translator
    schema: type[GarminRequest]
    ingest_method: str | None
    fetcher: Fetcher
    requires_display_name: bool = True


def build_dataset_configs() -> dict[str, DatasetConfig]:
    """Return dataset configuration mapping used by :class:`GarminProviderService`."""

    return {
        "sleep": DatasetConfig(
            translator=translate_sleep,
            schema=SleepIngestRequest,
            ingest_method="ingest_sleep",
            fetcher=fetchers.fetch_sleep,
        ),
        "summary": DatasetConfig(
            translator=translate_summary,
            schema=UserSummaryRequest,
            ingest_method="ingest_user_summary",
            fetcher=fetchers.fetch_summary,
        ),
        "body_composition": DatasetConfig(
            translator=translate_body_composition,
            schema=BodyCompositionRequest,
            ingest_method="ingest_body_composition",
            fetcher=fetchers.fetch_body_composition,
            requires_display_name=False,
        ),
        "hrv": DatasetConfig(
            translator=translate_hrv,
            schema=HRVRequest,
            ingest_method="ingest_hrv",
            fetcher=fetchers.fetch_hrv,
            requires_display_name=False,
        ),
        "training_readiness": DatasetConfig(
            translator=translate_training_readiness,
            schema=TrainingReadinessRequest,
            ingest_method="ingest_training_readiness",
            fetcher=fetchers.fetch_training_readiness,
            requires_display_name=False,
        ),
        "training_endurance": DatasetConfig(
            translator=translate_endurance_score,
            schema=EnduranceScoreRequest,
            ingest_method="ingest_endurance_score",
            fetcher=fetchers.fetch_endurance_score,
            requires_display_name=False,
        ),
        "training_status": DatasetConfig(
            translator=translate_training_status,
            schema=TrainingStatusRequest,
            ingest_method="ingest_training_status",
            fetcher=fetchers.fetch_training_status,
            requires_display_name=False,
        ),
        "training_load_balance": DatasetConfig(
            translator=translate_training_load_balance,
            schema=TrainingStatusRequest,
            ingest_method="ingest_training_status",
            fetcher=fetchers.fetch_training_load_balance,
            requires_display_name=False,
        ),
        "training_fitness_age": DatasetConfig(
            translator=translate_fitness_age,
            schema=FitnessAgeRequest,
            ingest_method="ingest_fitness_age",
            fetcher=fetchers.fetch_fitness_age,
            requires_display_name=False,
        ),
        "activity": DatasetConfig(
            translator=translate_activity,
            schema=ActivityRequest,
            ingest_method="ingest_activity",
            fetcher=fetchers.fetch_activity,
        ),
        "activity_gps": DatasetConfig(
            translator=translate_activity_gps,
            schema=ActivityGpsRequest,
            ingest_method="ingest_activity_gps",
            fetcher=fetchers.fetch_activity_gps,
        ),
        "daily_health_events": DatasetConfig(
            translator=translate_daily_health_events,
            schema=DailyHealthEventsRequest,
            ingest_method="ingest_daily_health_events",
            fetcher=fetchers.fetch_daily_health_events,
        ),
        "max_metrics": DatasetConfig(
            translator=translate_max_metrics,
            schema=TrainingStatusRequest,
            ingest_method="ingest_training_status",
            fetcher=fetchers.fetch_max_metrics,
            requires_display_name=False,
        ),
    }


async def fetch_dataset_raw(
    dataset: str,
    config: DatasetConfig,
    context: GarminDatasetContext,
    query: GarminDataQuery,
) -> Any:
    """Execute the configured fetcher and normalize awaitables."""

    window = _build_fetch_window(config, context, query)
    result = config.fetcher(context, window, query)
    if inspect.isawaitable(result):
        result = await result
    return result


def _build_fetch_window(
    config: DatasetConfig, context: GarminDatasetContext, query: GarminDataQuery
) -> FetchWindow:
    start = query.start_date or query.end_date or date.today()
    end = query.end_date or start
    display_name = context.client.display_name if config.requires_display_name else None
    return FetchWindow(start=start, end=end, display_name=display_name)


__all__ = [
    "DatasetConfig",
    "GarminDatasetContext",
    "build_dataset_configs",
    "fetch_dataset_raw",
]
