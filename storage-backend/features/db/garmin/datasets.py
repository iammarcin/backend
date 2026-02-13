"""Dataset metadata helpers for Garmin database integrations.

This module centralises the dataset configuration that was previously in
``service.py``.  Splitting it out keeps the service focused on orchestration
while providing a single place for dataset lookups and metadata queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration details required to retrieve a Garmin dataset."""

    table: str
    repo_attr: str
    fetch_method: str
    label: str
    success_message: str
    shift_next_day: bool = False
    extra_params: Sequence[str] = ()


class GarminDatasetRegistry:
    """Registry wrapping dataset metadata and common lookups."""

    def __init__(
        self,
        *,
        datasets: Mapping[str, DatasetConfig],
        next_day_tables: Sequence[str],
        default_analysis_keys: Sequence[str],
    ) -> None:
        self._datasets = dict(datasets)
        self._next_day_tables = tuple(next_day_tables)
        self._default_analysis_keys = tuple(default_analysis_keys)

    @property
    def next_day_tables(self) -> Sequence[str]:
        """Tables whose timestamps are shifted by Garmin to the next day."""

        return self._next_day_tables

    @property
    def default_analysis_keys(self) -> Sequence[str]:
        """Dataset identifiers shown in the combined analysis view."""

        return self._default_analysis_keys

    def keys(self) -> Sequence[str]:
        """Return the dataset identifiers known to the registry."""

        return tuple(self._datasets.keys())

    def require(self, dataset: str) -> DatasetConfig:
        """Return ``dataset`` configuration or raise a :class:`ValueError`."""

        try:
            return self._datasets[dataset]
        except KeyError as exc:  # pragma: no cover - defensive guard
            raise ValueError(f"Unknown Garmin dataset '{dataset}'") from exc

    def label(self, dataset: str) -> str:
        """Return a human-readable label for ``dataset``."""

        return self.require(dataset).label

    def success_message(self, dataset: str) -> str:
        """Return the success log message for ``dataset`` retrieval."""

        return self.require(dataset).success_message

    def table(self, dataset: str) -> str:
        """Return the backing table name for ``dataset``."""

        return self.require(dataset).table


def build_default_dataset_registry() -> GarminDatasetRegistry:
    """Return the registry used by the public :class:`GarminService`."""

    next_day_tables: Sequence[str] = ("get_hrv_data", "get_sleep_data")
    datasets: Mapping[str, DatasetConfig] = {
        "sleep": DatasetConfig(
            table="get_sleep_data",
            repo_attr="_sleep_repo",
            fetch_method="fetch_sleep",
            label="sleep",
            success_message="Retrieved Garmin sleep data",
            shift_next_day=True,
        ),
        "summary": DatasetConfig(
            table="get_user_summary",
            repo_attr="_summary_repo",
            fetch_method="fetch_user_summary",
            label="daily summary",
            success_message="Retrieved Garmin daily summary data",
        ),
        "body_composition": DatasetConfig(
            table="get_body_composition",
            repo_attr="_summary_repo",
            fetch_method="fetch_body_composition",
            label="body composition",
            success_message="Retrieved Garmin body composition data",
        ),
        "hrv": DatasetConfig(
            table="get_hrv_data",
            repo_attr="_summary_repo",
            fetch_method="fetch_hrv",
            label="HRV",
            success_message="Retrieved Garmin HRV data",
            shift_next_day=True,
        ),
        "training_readiness": DatasetConfig(
            table="get_training_readiness",
            repo_attr="_training_repo",
            fetch_method="fetch_training_readiness",
            label="training readiness",
            success_message="Retrieved Garmin training readiness data",
        ),
        "training_endurance": DatasetConfig(
            table="get_endurance_score",
            repo_attr="_training_repo",
            fetch_method="fetch_endurance_score",
            label="endurance score",
            success_message="Retrieved Garmin endurance score data",
        ),
        "training_status": DatasetConfig(
            table="get_training_status",
            repo_attr="_training_repo",
            fetch_method="fetch_training_status",
            label="training status",
            success_message="Retrieved Garmin training status data",
            extra_params=("ignore_null_vo2max", "ignore_null_training_load_data"),
        ),
        "training_load_balance": DatasetConfig(
            table="get_training_status",
            repo_attr="_training_repo",
            fetch_method="fetch_training_status",
            label="training load balance",
            success_message="Retrieved Garmin training load balance data",
        ),
        "training_fitness_age": DatasetConfig(
            table="get_fitness_age",
            repo_attr="_training_repo",
            fetch_method="fetch_fitness_age",
            label="fitness age",
            success_message="Retrieved Garmin fitness age data",
        ),
        "activity": DatasetConfig(
            table="get_activities",
            repo_attr="_activity_repo",
            fetch_method="fetch_activity",
            label="activity",
            success_message="Retrieved Garmin activity data",
            extra_params=("activity_id",),
        ),
        "activity_gps": DatasetConfig(
            table="get_activity_gps_data",
            repo_attr="_activity_repo",
            fetch_method="fetch_activity_gps",
            label="activity GPS",
            success_message="Retrieved Garmin activity GPS data",
            extra_params=("activity_id",),
        ),
        "daily_health_events": DatasetConfig(
            table="daily_health_events",
            repo_attr="_activity_repo",
            fetch_method="fetch_daily_health_events",
            label="daily health events",
            success_message="Retrieved Garmin daily health events",
        ),
        "max_metrics": DatasetConfig(
            table="get_training_status",
            repo_attr="_training_repo",
            fetch_method="fetch_training_status",
            label="VO2 max metrics",
            success_message="Retrieved Garmin VO2 max metrics",
        ),
    }
    default_analysis_keys: Sequence[str] = (
        "summary",
        "body_composition",
        "sleep",
        "hrv",
        "training_readiness",
        "training_endurance",
        "training_status",
        "activity",
    )
    return GarminDatasetRegistry(
        datasets=datasets,
        next_day_tables=next_day_tables,
        default_analysis_keys=default_analysis_keys,
    )


__all__ = [
    "DatasetConfig",
    "GarminDatasetRegistry",
    "build_default_dataset_registry",
]
