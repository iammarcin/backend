"""Dataset retrieval helpers for the Garmin database service."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any, Iterable, Sequence

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from features.garmin.schemas.queries import GarminDataQuery, QueryMode

from .datasets import DatasetConfig, GarminDatasetRegistry
from .utils import adjust_dates_for_special_modes, optimize_health_data, revert_dates_for_special_modes

logger = logging.getLogger(__name__)


class GarminRetrievalMixin:
    """Provide dataset metadata helpers and retrieval workflows."""

    _datasets: GarminDatasetRegistry

    def dataset_label(self, dataset: str) -> str:
        """Return a human readable label for ``dataset``."""

        return self._datasets.label(dataset)

    def dataset_success_message(self, dataset: str) -> str:
        """Return the success message associated with ``dataset`` retrieval."""

        return self._datasets.success_message(dataset)

    def dataset_table(self, dataset: str) -> str:
        """Return the underlying table name for ``dataset``."""

        return self._datasets.table(dataset)

    def available_datasets(self) -> Sequence[str]:
        """Return the dataset identifiers supported by this service."""

        return self._datasets.keys()

    def default_analysis_datasets(self) -> Sequence[str]:
        """Datasets included in the analysis overview helper."""

        return self._datasets.default_analysis_keys

    async def fetch_dataset(
        self,
        session: AsyncSession,
        dataset: str,
        query: GarminDataQuery,
        customer_id: int,
    ) -> list[dict[str, Any]]:
        """Return serialisable rows for ``dataset`` respecting ``query`` filters."""

        config = self._datasets.require(dataset)
        start, end = self._resolve_bounds(config, query)
        mode_value = _normalise_mode(query.mode)

        logger.info(
            "Fetching Garmin dataset: %s",
            config.label,
            extra={"customer_id": customer_id, "dataset": dataset},
        )

        repository = getattr(self, config.repo_attr)
        fetcher = getattr(repository, config.fetch_method)

        extra_kwargs = {name: getattr(query, name) for name in config.extra_params}
        records = await fetcher(
            session,
            customer_id,
            start=start,
            end=end,
            descending=query.is_descending,
            limit=query.limit,
            offset=query.offset,
            **extra_kwargs,
        )

        serialised = [_serialise_record(record) for record in records]
        adjusted = revert_dates_for_special_modes(
            mode_value,
            config.table,
            serialised,
            self._datasets.next_day_tables,
        )

        return adjusted

    async def fetch_analysis(
        self,
        session: AsyncSession,
        query: GarminDataQuery,
        customer_id: int,
        datasets: Sequence[str] | None = None,
        *,
        include_optimized: bool = False,
    ) -> dict[str, Any]:
        """Return a mapping of dataset names for analysis dashboards."""

        keys: Iterable[str] = datasets or self._datasets.default_analysis_keys
        raw: dict[str, list[dict[str, Any]]] = {}

        for key in keys:
            config = self._datasets.require(key)
            raw[config.table] = await self.fetch_dataset(session, key, query, customer_id)

        payload: dict[str, Any] = {"datasets": raw}
        if include_optimized:
            payload["optimized"] = optimize_health_data(raw)

        return payload

    def _resolve_bounds(
        self,
        config: DatasetConfig,
        query: GarminDataQuery,
    ) -> tuple[datetime | None, datetime | None]:
        mode_value = _normalise_mode(query.mode)
        start_adjusted, end_adjusted = adjust_dates_for_special_modes(
            mode_value,
            config.table,
            query.start_date,
            query.end_date,
            self._datasets.next_day_tables,
        )
        return (
            _to_datetime(start_adjusted, is_end=False),
            _to_datetime(end_adjusted, is_end=True),
        )


def _serialise_record(record: Any) -> dict[str, Any]:
    """Serialise SQLAlchemy models or raw mappings returned from repositories."""

    payload: dict[str, Any] = {}
    columns = getattr(record, "__table__", None)
    if columns is not None:
        for column in columns.columns:  # type: ignore[attr-defined]
            payload[column.name] = jsonable_encoder(getattr(record, column.name))
        return payload

    encoded = jsonable_encoder(record)
    if isinstance(encoded, dict):
        return encoded

    raise TypeError(
        "Unsupported Garmin record type for serialisation: "
        f"{type(record)!r}"
    )


def _to_datetime(value: str | date | None, *, is_end: bool) -> datetime | None:
    """Convert ``value`` to a datetime boundary for filtering queries."""

    if value is None:
        return None
    if isinstance(value, str):
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    else:
        parsed = value
    boundary = time.max if is_end else time.min
    return datetime.combine(parsed, boundary)


def _normalise_mode(mode: QueryMode | str | None) -> str:
    """Return a normalised representation of the query mode."""

    if isinstance(mode, QueryMode):
        return mode.value
    if mode is None:
        return QueryMode.STANDARD.value
    return str(mode)


__all__ = ["GarminRetrievalMixin"]
