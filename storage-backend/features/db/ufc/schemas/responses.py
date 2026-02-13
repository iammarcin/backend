"""API response envelopes for UFC endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .internal import (
    AuthResult,
    FighterSummary,
    FighterMutationResult,
    FighterQueueResult,
    RegistrationResult,
    SubscriptionStatusResponse,
    SubscriptionSummaryList,
    UserExistsResult,
    UserProfile,
)


class UfcErrorDetail(BaseModel):
    """Single validation or service error entry."""

    message: str = Field(..., description="Human readable error message")
    field: str | None = Field(
        default=None,
        description="Optional field associated with the error",
    )


class UfcErrorData(BaseModel):
    """Structured container for error details."""

    errors: list[UfcErrorDetail] = Field(
        default_factory=list,
        description="Collection of error details",
    )


class UfcResponseBase(BaseModel):
    """Base API envelope shared by UFC responses."""

    code: int = Field(..., description="Application-level status code")
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Summary suitable for UI display")
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata for pagination or tracing",
    )


class FighterListData(BaseModel):
    """Data payload returned when listing fighters."""

    model_config = ConfigDict(from_attributes=True)

    fighters: list[FighterSummary] = Field(
        default_factory=list,
        description="Paginated fighter results",
    )
    total: int = Field(..., description="Total fighters matching the applied filters")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of fighters returned per page")
    has_more: bool = Field(..., description="Whether additional pages are available")
    search: str | None = Field(
        default=None,
        description="Search term used to filter fighters",
    )
    subscriptions_enabled: bool | None = Field(
        default=None,
        description="Indicates whether subscription data is included",
    )


class FighterListEnvelope(UfcResponseBase):
    """Successful response envelope for fighter listings."""

    data: FighterListData | None = Field(
        default=None,
        description="Fighter dataset returned by the service",
    )


class SubscriptionSummaryEnvelope(UfcResponseBase):
    """Successful response envelope for subscription summary listings."""

    data: SubscriptionSummaryList | None = Field(
        default=None,
        description="Subscription summary dataset",
    )


class FighterMutationEnvelope(UfcResponseBase):
    """Successful response envelope for fighter mutation workflows."""

    data: FighterMutationResult | None = Field(
        default=None,
        description="Fighter mutation result payload",
    )


class FighterQueueEnvelope(UfcResponseBase):
    """Successful response envelope for fighter queue workflows."""

    data: FighterQueueResult | None = Field(
        default=None,
        description="Queue metadata returned by the service",
    )


class SubscriptionStatusEnvelope(UfcResponseBase):
    """Successful response envelope for subscription toggle workflows."""

    data: SubscriptionStatusResponse | None = Field(
        default=None,
        description="Subscription status payload",
    )


class AuthEnvelope(UfcResponseBase):
    """Successful response envelope for authentication requests."""

    data: AuthResult | None = Field(
        default=None,
        description="Authentication payload including token and profile",
    )


class RegistrationEnvelope(UfcResponseBase):
    """Successful response envelope for registration requests."""

    data: RegistrationResult | None = Field(
        default=None,
        description="Registration payload including new user identifier",
    )


class UserExistsEnvelope(UfcResponseBase):
    """Successful response envelope for existence checks."""

    data: UserExistsResult | None = Field(
        default=None,
        description="Boolean result describing whether the user exists",
    )


class UserProfileEnvelope(UfcResponseBase):
    """Successful response envelope for profile lookups."""

    data: UserProfile | None = Field(
        default=None,
        description="User profile information",
    )


class UfcErrorResponse(UfcResponseBase):
    """Error envelope returned when operations fail."""

    data: UfcErrorData | None = Field(
        default=None,
        description="Optional structured error details",
    )


__all__ = [
    "UfcErrorDetail",
    "UfcErrorData",
    "UfcResponseBase",
    "FighterListData",
    "FighterListEnvelope",
    "SubscriptionSummaryEnvelope",
    "FighterMutationEnvelope",
    "FighterQueueEnvelope",
    "SubscriptionStatusEnvelope",
    "AuthEnvelope",
    "RegistrationEnvelope",
    "UserExistsEnvelope",
    "UserProfileEnvelope",
    "UfcErrorResponse",
]
