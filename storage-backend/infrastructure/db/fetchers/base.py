"""Abstract base class for chart data fetchers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from core.pydantic_schemas import ChartData, DataQuery, Dataset, TimeRange


class BaseDataFetcher(ABC):
    """Abstract base class for data source fetchers."""

    @abstractmethod
    async def fetch(self, query: DataQuery) -> ChartData:
        """Fetch data based on query specification."""
        raise NotImplementedError

    @abstractmethod
    def get_available_metrics(self) -> List[str]:
        """Return list of metrics this fetcher can provide."""
        raise NotImplementedError

    def resolve_time_range(self, time_range: Optional[TimeRange]) -> Tuple[datetime, datetime]:
        """Convert TimeRange to absolute start/end datetimes."""
        now = datetime.utcnow()

        if time_range is None:
            # Default to last 30 days
            return now - timedelta(days=30), now

        if time_range.all_time:
            # Fetch all available data - use a very wide date range
            return datetime(2000, 1, 1), now

        if time_range.last_n_days:
            return now - timedelta(days=time_range.last_n_days), now
        if time_range.last_n_weeks:
            return now - timedelta(weeks=time_range.last_n_weeks), now
        if time_range.last_n_months:
            return now - timedelta(days=time_range.last_n_months * 30), now

        start = time_range.start or (now - timedelta(days=30))
        end = time_range.end or now
        return start, end


__all__ = [
    "BaseDataFetcher",
]
