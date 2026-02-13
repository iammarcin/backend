"""Internal UFC response models consumed by the service layer."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..types import SubscriptionFlag


class FighterSummary(BaseModel):
    """Normalised fighter representation returned by repositories."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    ufcUrl: str | None = Field(default=None)
    fighterFullBodyImgUrl: str | None = Field(default=None)
    fighterHeadshotImgUrl: str | None = Field(default=None)
    weightClass: str | None = Field(default=None)
    record: str | None = Field(default=None)
    sherdogRecord: str | None = Field(default=None)
    nextFightDate: str | None = Field(default=None)
    nextFightOpponent: str | None = Field(default=None)
    nextFightOpponentRecord: str | None = Field(default=None)
    opponentHeadshotUrl: str | None = Field(default=None)
    opponentUfcUrl: str | None = Field(default=None)
    tags: str | None = Field(default=None)
    tagsDwcs: str | None = Field(default=None)
    height: str | None = Field(default=None)
    weight: str | None = Field(default=None)
    age: int | None = Field(default=None)
    rumourNextFightDate: str | None = Field(default=None)
    rumourNextFightOpponent: str | None = Field(default=None)
    rumourNextFightOpponentRecord: str | None = Field(default=None)
    rumourNextFightOpponentImgUrl: str | None = Field(default=None)
    rumourOpponentUfcUrl: str | None = Field(default=None)
    mydesc: str | None = Field(default=None)
    twitter: str | None = Field(default=None)
    instagram: str | None = Field(default=None)
    sherdog: str | None = Field(default=None)
    tapology: str | None = Field(default=None)
    subscription_status: SubscriptionFlag | None = Field(default=None)


class FighterList(BaseModel):
    """Paginated collection of fighters returned by the service layer."""

    model_config = ConfigDict(from_attributes=True)

    items: list[FighterSummary] = Field(default_factory=list)
    total: int
    page: int
    page_size: int
    has_more: bool
    search: str | None = Field(default=None)
    subscriptions_enabled: bool | None = Field(default=None)


class SubscriptionSummaryItem(BaseModel):
    """Aggregated subscription counts for a UFC customer."""

    model_config = ConfigDict(from_attributes=True)

    accountName: str
    email: str | None = Field(default=None)
    subscriptions: list[str] = Field(default_factory=list)


class SubscriptionSummaryList(BaseModel):
    """Wrapper for subscription summary collections."""

    model_config = ConfigDict(from_attributes=True)

    items: list[SubscriptionSummaryItem] = Field(default_factory=list)
    total: int


class FighterMutationResult(BaseModel):
    """Outcome of fighter creation or update operations."""

    model_config = ConfigDict(from_attributes=True)

    fighter_id: int
    status: Literal["created", "duplicate", "updated", "unchanged"]
    message: str
    changed: bool


class SubscriptionStatusResponse(BaseModel):
    """Result returned after toggling a fighter subscription."""

    model_config = ConfigDict(from_attributes=True)

    person_id: int
    fighter_id: int
    subscription_status: SubscriptionFlag
    updated_at: datetime | None = Field(default=None)
    message: str
    changed: bool


class UserProfile(BaseModel):
    """Serializable representation of a UFC user profile."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    accountName: str = Field(
        validation_alias="account_name",
        serialization_alias="accountName",
    )
    email: EmailStr
    lang: str = Field(default="en", max_length=5)
    totalGenerations: int = Field(
        default=0,
        validation_alias="total_generations",
        serialization_alias="totalGenerations",
    )
    photo: str = Field(default="default_photo.png")
    createdAt: datetime = Field(
        validation_alias="created_at",
        serialization_alias="createdAt",
    )


class AuthResult(BaseModel):
    """Payload returned when authentication succeeds."""

    model_config = ConfigDict(from_attributes=True)

    status: Literal["authenticated"]
    message: str
    token: str | None = None
    user: UserProfile


class RegistrationResult(BaseModel):
    """Payload returned after registering a new UFC user."""

    model_config = ConfigDict(from_attributes=True)

    status: Literal["registered"]
    message: str
    user_id: int
    email: EmailStr
    accountName: str


class UserExistsResult(BaseModel):
    """Boolean result describing whether a UFC user exists."""

    model_config = ConfigDict(from_attributes=True)

    email: EmailStr
    exists: bool
    message: str


class FighterQueueResult(BaseModel):
    """Result returned after queueing a fighter message."""

    model_config = ConfigDict(from_attributes=True)

    status: Literal["queued"]
    message: str
    queue_url: str
    message_id: str | None = None


__all__ = [
    "FighterSummary",
    "FighterList",
    "SubscriptionSummaryItem",
    "SubscriptionSummaryList",
    "FighterMutationResult",
    "SubscriptionStatusResponse",
    "UserProfile",
    "AuthResult",
    "RegistrationResult",
    "UserExistsResult",
    "FighterQueueResult",
]
