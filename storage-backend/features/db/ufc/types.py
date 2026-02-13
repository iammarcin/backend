"""Typed payload definitions for the UFC feature package."""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

IsoDateTimeString = str
SubscriptionFlag = Literal["0", "1"]


class FighterRow(TypedDict, total=False):
    """Serializable representation of a fighter record."""

    id: int
    name: str
    ufcUrl: str
    fighterFullBodyImgUrl: str
    fighterHeadshotImgUrl: str
    weightClass: str
    record: str
    sherdogRecord: str
    nextFightDate: NotRequired[IsoDateTimeString | None]
    nextFightOpponent: NotRequired[str | None]
    nextFightOpponentRecord: NotRequired[str | None]
    opponentHeadshotUrl: NotRequired[str | None]
    opponentUfcUrl: NotRequired[str | None]
    tags: str
    tagsDwcs: NotRequired[str | None]
    height: NotRequired[str | None]
    weight: NotRequired[str | None]
    age: NotRequired[int | None]
    rumourNextFightDate: NotRequired[IsoDateTimeString | None]
    rumourNextFightOpponent: NotRequired[str | None]
    rumourNextFightOpponentRecord: NotRequired[str | None]
    rumourNextFightOpponentImgUrl: NotRequired[str | None]
    rumourOpponentUfcUrl: NotRequired[str | None]
    mydesc: NotRequired[str | None]
    twitter: NotRequired[str | None]
    instagram: NotRequired[str | None]
    sherdog: NotRequired[str | None]
    tapology: NotRequired[str | None]


class FighterWithSubscription(FighterRow, total=False):
    """Fighter row enriched with the caller's subscription flag."""

    subscription_status: SubscriptionFlag


class SubscriptionSummary(TypedDict):
    """Aggregated subscription information for a UFC user."""

    accountName: str
    email: str
    subscriptions: list[str]


class FighterSearchFilters(TypedDict, total=False):
    """Supported filters for fighter search operations."""

    search: str
    user_id: int


class UfcRepositories(TypedDict):
    """Container of repository instances injected into the UFC service."""

    fighters: "FighterReadRepository"
    subscriptions: "SubscriptionReadRepository"
    auth: "AuthRepository"


__all__ = [
    "FighterRow",
    "FighterWithSubscription",
    "SubscriptionSummary",
    "FighterSearchFilters",
    "UfcRepositories",
    "IsoDateTimeString",
    "SubscriptionFlag",
]
