"""Fighter-related request models for the UFC service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .utils import clean_search


class FighterListParams(BaseModel):
    """Pagination and filtering parameters for fighter listings."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(
        default=50,
        ge=1,
        description="Maximum number of fighters to return",
    )
    search: str | None = Field(
        default=None,
        description="Optional case-insensitive search term",
        max_length=255,
    )

    @model_validator(mode="after")
    def _normalise_search(self) -> "FighterListParams":  # pragma: no cover - exercised via public methods
        self.search = clean_search(self.search)
        return self


class FighterSubscriptionParams(FighterListParams):
    """Parameters for subscription-aware fighter listings."""

    user_id: int | None = Field(
        default=None,
        ge=1,
        description="Optional user identifier to evaluate subscriptions",
    )


class FighterListQueryParams(BaseModel):
    """Query parameters accepted by the fighter listing endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    user_id: int | None = Field(
        default=None,
        ge=1,
        description="Optional user identifier to resolve subscription state",
    )
    search: str | None = Field(
        default=None,
        description="Optional case-insensitive search term",
        max_length=255,
    )
    page: int = Field(
        default=1,
        ge=1,
        description="1-indexed page number for pagination",
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=2000,
        description="Maximum number of fighters to return per page",
    )

    @model_validator(mode="after")
    def _normalise_search(self) -> "FighterListQueryParams":
        self.search = clean_search(self.search)
        return self

    def to_service_params(self) -> FighterSubscriptionParams:
        """Convert HTTP query parameters into service-level filters."""

        return FighterSubscriptionParams(
            user_id=self.user_id,
            search=self.search,
            page=self.page,
            page_size=self.page_size,
        )


class FighterSearchParams(FighterListParams):
    """Parameters for explicit fighter search endpoints."""

    search: str = Field(
        ..., description="Search term applied to name, tags, and weight class", max_length=255
    )

    @model_validator(mode="after")
    def _ensure_search_present(self) -> "FighterSearchParams":
        self.search = clean_search(self.search)
        if not self.search:
            raise ValueError("search term cannot be empty")
        return self


class CreateFighterRequest(BaseModel):
    """Payload for fighter creation requests."""

    model_config = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, extra="forbid"
    )

    name: str = Field(..., min_length=1, max_length=100)
    ufc_url: str = Field(..., alias="ufcUrl", max_length=500)
    fighter_full_body_img_url: str = Field(
        ..., alias="fighterFullBodyImgUrl", max_length=500
    )
    fighter_headshot_img_url: str = Field(
        ..., alias="fighterHeadshotImgUrl", max_length=500
    )
    weight_class: str = Field(..., alias="weightClass", max_length=50)
    record: str = Field(..., max_length=20)
    sherdog_record: str = Field(..., alias="sherdogRecord", max_length=20)
    tags: str = Field(default="[]", max_length=400)
    tags_dwcs: str | None = Field(default=None, alias="tagsDwcs", max_length=40)
    height: str | None = Field(default=None, max_length=10)
    weight: str | None = Field(default=None, max_length=10)
    age: int | None = Field(default=None, ge=0, le=120)
    next_fight_date: datetime | None = Field(default=None, alias="nextFightDate")
    next_fight_opponent: str | None = Field(
        default=None, alias="nextFightOpponent", max_length=100
    )
    next_fight_opponent_record: str | None = Field(
        default=None, alias="nextFightOpponentRecord", max_length=20
    )
    opponent_headshot_url: str | None = Field(
        default=None, alias="opponentHeadshotUrl", max_length=500
    )
    opponent_ufc_url: str | None = Field(
        default=None, alias="opponentUfcUrl", max_length=500
    )
    rumour_next_fight_date: datetime | None = Field(
        default=None, alias="rumourNextFightDate"
    )
    rumour_next_fight_opponent: str | None = Field(
        default=None, alias="rumourNextFightOpponent", max_length=100
    )
    rumour_next_fight_opponent_record: str | None = Field(
        default=None, alias="rumourNextFightOpponentRecord", max_length=20
    )
    rumour_next_fight_opponent_img_url: str | None = Field(
        default=None, alias="rumourNextFightOpponentImgUrl", max_length=500
    )
    rumour_opponent_ufc_url: str | None = Field(
        default=None, alias="rumourOpponentUfcUrl", max_length=500
    )
    description: str | None = Field(default=None, alias="mydesc")
    twitter: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=500)
    sherdog: str | None = Field(default=None, max_length=500)


class FighterQueueRequest(BaseModel):
    """Payload for queuing fighter enrichment tasks."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    full_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    dwcs_info: str | None = Field(default=None, max_length=200)
    customer_id: int | None = Field(default=None, ge=1)


def _empty_to_none(v: Any) -> Any:
    """Convert empty strings to None for optional fields."""
    if v == "" or v == "0000-00-00":
        return None
    return v


class UpdateFighterRequest(BaseModel):
    """Payload for fighter updates with optional fields."""

    model_config = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, extra="ignore"
    )

    # Basic info
    ufc_url: str | None = Field(default=None, alias="ufcUrl", max_length=500)
    fighter_full_body_img_url: str | None = Field(
        default=None, alias="fighterFullBodyImgUrl", max_length=500
    )
    fighter_headshot_img_url: str | None = Field(
        default=None, alias="fighterHeadshotImgUrl", max_length=500
    )
    weight_class: str | None = Field(default=None, alias="weightClass", max_length=50)
    height: str | None = Field(default=None, max_length=20)
    weight: str | None = Field(default=None, max_length=20)
    record: str | None = Field(default=None, max_length=20)
    sherdog_record: str | None = Field(
        default=None, alias="sherdogRecord", max_length=20
    )
    tags: str | None = Field(default=None, max_length=400)
    tags_dwcs: str | None = Field(default=None, alias="tagsDwcs", max_length=40)
    age: int | None = Field(default=None, ge=0, le=120)

    # Next fight info
    next_fight_date: datetime | None = Field(default=None, alias="nextFightDate")
    next_fight_opponent: str | None = Field(
        default=None, alias="nextFightOpponent", max_length=100
    )
    next_fight_opponent_record: str | None = Field(
        default=None, alias="nextFightOpponentRecord", max_length=20
    )
    opponent_headshot_url: str | None = Field(
        default=None, alias="opponentHeadshotUrl", max_length=500
    )
    opponent_ufc_url: str | None = Field(
        default=None, alias="opponentUfcUrl", max_length=500
    )

    # Rumour fight info
    rumour_next_fight_date: datetime | None = Field(
        default=None, alias="rumourNextFightDate"
    )
    rumour_next_fight_opponent: str | None = Field(
        default=None, alias="rumourNextFightOpponent", max_length=100
    )
    rumour_next_fight_opponent_record: str | None = Field(
        default=None, alias="rumourNextFightOpponentRecord", max_length=20
    )
    rumour_next_fight_opponent_img_url: str | None = Field(
        default=None, alias="rumourNextFightOpponentImgUrl", max_length=500
    )
    rumour_opponent_ufc_url: str | None = Field(
        default=None, alias="rumourOpponentUfcUrl", max_length=500
    )

    # Social/other
    description: str | None = Field(default=None, alias="mydesc")
    twitter: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=500)
    sherdog: str | None = Field(default=None, max_length=500)

    @model_validator(mode="before")
    @classmethod
    def _convert_empty_dates(cls, data: Any) -> Any:
        """Convert empty date strings to None before validation."""
        if isinstance(data, dict):
            for key in ["nextFightDate", "rumourNextFightDate", "next_fight_date", "rumour_next_fight_date"]:
                if key in data:
                    data[key] = _empty_to_none(data[key])
        return data

    def to_update_dict(self) -> dict[str, Any]:
        """Return a dictionary of fields explicitly set by the client."""

        return self.model_dump(exclude_unset=True)


__all__ = [
    "FighterListParams",
    "FighterSubscriptionParams",
    "FighterListQueryParams",
    "FighterSearchParams",
    "CreateFighterRequest",
    "FighterQueueRequest",
    "UpdateFighterRequest",
]
