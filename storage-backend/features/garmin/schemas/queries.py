"""Query parameter models for Garmin data retrieval endpoints."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class SortOrder(str, Enum):
    """Supported sort directions for Garmin dataset queries."""

    ASC = "asc"
    DESC = "desc"


class QueryMode(str, Enum):
    """Special processing modes recognised by Garmin data queries."""

    STANDARD = "standard"
    CORRELATION = "correlation"


class DataSource(str, Enum):
    """Data source for Garmin queries - fetch from API or query database only."""

    GARMIN = "garmin"
    DATABASE = "database"


class GarminDataQuery(BaseModel):
    """Common query parameters accepted by Garmin GET endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    start_date: Optional[date] = Field(
        default=None,
        description="Inclusive start date (YYYY-MM-DD) for filtering calendar_date",
        validation_alias=AliasChoices("start_date", "startDate"),
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Inclusive end date (YYYY-MM-DD) for filtering calendar_date",
        validation_alias=AliasChoices("end_date", "endDate"),
    )
    target_date: Optional[date] = Field(
        default=None,
        description="Target date for VO2 max backfill (used by max-metrics endpoint to select latest value before/on this date)",
        validation_alias=AliasChoices("target_date", "targetDate"),
    )
    sort: SortOrder = Field(
        default=SortOrder.ASC,
        description="Sort order for calendar_date",
        validation_alias=AliasChoices("sort", "sort_type"),
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description="Maximum number of records to return",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of records to skip before collecting results",
    )
    mode: QueryMode = Field(
        default=QueryMode.STANDARD,
        description="Optional processing mode that enables correlation date shifting",
    )
    ignore_null_vo2max: bool = Field(
        default=False,
        description="Exclude rows where VO2 max is null (training status datasets)",
        alias="ignore_null_vo2max",
    )
    ignore_null_training_load_data: bool = Field(
        default=False,
        description="Exclude rows where training load metrics are null",
        alias="ignore_null_training_load_data",
    )
    activity_id: Optional[int] = Field(
        default=None,
        description="Filter activity datasets to a specific Garmin activity id",
        alias="activity_id",
    )
    activity_name: Optional[str] = Field(
        default=None,
        description="Optional activity name supplied by the caller for GPS persistence",
        validation_alias=AliasChoices("activity_name", "activityName"),
    )
    source: DataSource = Field(
        default=DataSource.GARMIN,
        description="Data source: 'garmin' fetches from Garmin API (default), 'database' queries database only",
        validation_alias=AliasChoices("source", "data_source"),
    )

    @property
    def is_descending(self) -> bool:
        """Return ``True`` when the requested sort order is descending."""

        return self.sort == SortOrder.DESC


__all__ = ["GarminDataQuery", "SortOrder", "QueryMode", "DataSource"]
