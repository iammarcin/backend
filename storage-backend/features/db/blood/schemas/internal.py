"""Internal response and filter models for Blood domain services."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BloodTestFilterParams(BaseModel):
    """Validate optional filters applied when listing blood tests."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = Field(
        default=None, description="Exclude tests recorded before this date"
    )
    end_date: date | None = Field(
        default=None, description="Exclude tests recorded after this date"
    )
    category: str | None = Field(
        default=None, description="Restrict results to a specific test category"
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Maximum number of records to return after filtering",
    )

    @model_validator(mode="after")
    def _validate_date_range(self) -> "BloodTestFilterParams":
        """Ensure that the end date is not earlier than the start date."""

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class BloodTestItem(BaseModel):
    """Serialised representation of a blood test entry for API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    test_definition_id: int
    test_date: date
    result_value: str | None = None
    result_unit: str | None = None
    reference_range: str | None = None
    category: str | None = None
    test_name: str | None = None
    short_explanation: str | None = None
    long_explanation: str | None = None


class BloodTestListResponse(BaseModel):
    """Envelope returned by :class:`BloodService` list operations."""

    model_config = ConfigDict(from_attributes=True)

    items: Sequence[BloodTestItem]
    total_count: int = Field(description="Number of items matching the supplied filters")
    latest_test_date: date | None = Field(
        default=None, description="Most recent test date within the filtered dataset"
    )
    filters: BloodTestFilterParams | None = Field(
        default=None, description="Filters applied when computing this response"
    )


__all__ = ["BloodTestFilterParams", "BloodTestItem", "BloodTestListResponse"]
