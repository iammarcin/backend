"""UFC data fetcher placeholder."""

from __future__ import annotations

from typing import List

from core.pydantic_schemas import ChartData, DataQuery, Dataset

from .base import BaseDataFetcher


class UFCDataFetcher(BaseDataFetcher):
    """Fetch UFC statistics (placeholder until schema finalized)."""

    AVAILABLE_METRICS = [
        "wins",
        "losses",
        "knockouts",
        "takedowns",
        "significant_strikes",
    ]

    def get_available_metrics(self) -> List[str]:
        return self.AVAILABLE_METRICS

    async def fetch(self, query: DataQuery) -> ChartData:
        """Temporarily return empty data until UFC schema integration exists."""
        raise NotImplementedError(
            "UFC data fetcher is not implemented yet. "
            "Configure UFC database queries before enabling this metric."
        )


__all__ = ["UFCDataFetcher"]
