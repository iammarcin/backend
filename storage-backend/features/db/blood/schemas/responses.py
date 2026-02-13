"""Response envelope models for the Blood feature HTTP endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .internal import BloodTestListResponse


class BloodErrorDetail(BaseModel):
    """Single error detail returned when a request fails."""

    message: str = Field(..., description="Human readable description of the error")
    field: str | None = Field(
        default=None,
        description="Optional field associated with the error",
    )


class BloodErrorData(BaseModel):
    """Collection of structured error details."""

    errors: list[BloodErrorDetail] = Field(
        default_factory=list,
        description="List of error entries",
    )


class BloodResponseBase(BaseModel):
    """Base envelope mirroring the shared API response contract."""

    code: int = Field(..., description="Application-level status code")
    success: bool = Field(..., description="Whether the request succeeded")
    message: str = Field(..., description="Summary suitable for UI display")
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata such as pagination details",
    )


class BloodTestListEnvelope(BloodResponseBase):
    """Successful response envelope for the blood test listing endpoint."""

    data: BloodTestListResponse | None = Field(
        default=None,
        description="Blood test dataset returned by the service",
    )


class BloodErrorResponse(BloodResponseBase):
    """Error envelope returned by Blood endpoints."""

    data: BloodErrorData | None = Field(
        default=None,
        description="Structured validation or error details",
    )


__all__ = [
    "BloodErrorDetail",
    "BloodErrorData",
    "BloodResponseBase",
    "BloodTestListEnvelope",
    "BloodErrorResponse",
]
