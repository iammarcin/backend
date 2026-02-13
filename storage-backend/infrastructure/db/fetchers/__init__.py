"""Data fetcher registry for chart generation."""

from __future__ import annotations

from typing import Dict, Type

from core.pydantic_schemas import DataSource

from .base import BaseDataFetcher
from .blood import BloodDataFetcher
from .garmin import GarminDataFetcher
from .ufc import UFCDataFetcher

FETCHER_REGISTRY: Dict[DataSource, Type[BaseDataFetcher]] = {
    DataSource.GARMIN: GarminDataFetcher,
    DataSource.BLOOD: BloodDataFetcher,
    DataSource.UFC: UFCDataFetcher,
}


def get_data_fetcher(source: DataSource) -> BaseDataFetcher:
    """Return the fetcher for the given data source."""

    fetcher_cls = FETCHER_REGISTRY.get(source)
    if fetcher_cls is None:
        raise ValueError(f"No data fetcher registered for source '{source.value}'")

    return fetcher_cls()


__all__ = [
    "BaseDataFetcher",
    "BloodDataFetcher",
    "GarminDataFetcher",
    "UFCDataFetcher",
    "get_data_fetcher",
    "FETCHER_REGISTRY",
]
