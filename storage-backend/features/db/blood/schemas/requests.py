"""External request models for the Blood feature HTTP surface."""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .internal import BloodTestFilterParams


class BloodTestListQueryParams(BaseModel):
    """Query parameters accepted by the blood test listing endpoint."""

    model_config = ConfigDict(extra="forbid")

    start_date: date | None = Field(
        default=None,
        description="Exclude tests recorded before this date",
    )
    end_date: date | None = Field(
        default=None,
        description="Exclude tests recorded after this date",
    )
    category: str | None = Field(
        default=None,
        description="Restrict results to a specific test category",
        max_length=255,
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description="Maximum number of records to return after filtering",
    )

    def to_filters(self) -> BloodTestFilterParams | None:
        """Convert query params into service-level filter models."""

        data = self.model_dump(exclude_none=True)
        if not data:
            return None
        return BloodTestFilterParams.model_validate(data)


class BloodLegacyRequest(BaseModel):
    """Legacy MediaModel-compatible payload for blood data requests."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(
        ..., min_length=1, description="Legacy MediaModel action identifier"
    )
    user_input: dict[str, Any] = Field(default_factory=dict)
    user_settings: dict[str, Any] = Field(default_factory=dict)
    customer_id: int | None = Field(default=None)
    session_id: str | None = Field(default=None)
    asset_input: Sequence[Any] | None = Field(default=None)

    def is_supported_action(self) -> bool:
        """Return ``True`` when the legacy action is supported by the adapter."""

        return self.action == "get_all_blood_tests"


__all__ = ["BloodTestListQueryParams", "BloodLegacyRequest"]
