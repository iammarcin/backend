"""Serialization utilities for UFC fighter data."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .types import FighterRow, FighterWithSubscription

if TYPE_CHECKING:
    from .db_models import Fighter


def format_datetime(value: datetime | str | None) -> str | None:
    """Format datetime to ISO string, passthrough strings, return None for empty."""
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def serialize_fighter(fighter: "Fighter") -> FighterRow:
    """Convert a Fighter ORM model to a serializable dict."""
    row: FighterRow = {
        "id": fighter.id,
        "name": fighter.name,
        "ufcUrl": fighter.ufc_url,
        "fighterFullBodyImgUrl": fighter.fighter_full_body_img_url,
        "fighterHeadshotImgUrl": fighter.fighter_headshot_img_url,
        "weightClass": fighter.weight_class,
        "record": fighter.record,
        "sherdogRecord": fighter.sherdog_record,
        "nextFightDate": format_datetime(fighter.next_fight_date),
        "nextFightOpponent": fighter.next_fight_opponent,
        "nextFightOpponentRecord": fighter.next_fight_opponent_record,
        "opponentHeadshotUrl": fighter.opponent_headshot_url,
        "opponentUfcUrl": fighter.opponent_ufc_url,
        "tags": fighter.tags,
        "tagsDwcs": fighter.tags_dwcs,
        "height": fighter.height,
        "weight": fighter.weight,
        "age": fighter.age,
        "rumourNextFightDate": format_datetime(fighter.rumour_next_fight_date),
        "rumourNextFightOpponent": fighter.rumour_next_fight_opponent,
        "rumourNextFightOpponentRecord": fighter.rumour_next_fight_opponent_record,
        "rumourNextFightOpponentImgUrl": fighter.rumour_next_fight_opponent_img_url,
        "rumourOpponentUfcUrl": fighter.rumour_opponent_ufc_url,
        "mydesc": fighter.description,
        "twitter": fighter.twitter,
        "instagram": fighter.instagram,
        "sherdog": fighter.sherdog,
        "tapology": fighter.tapology,
    }
    return row


def serialize_fighter_with_subscription(
    fighter: "Fighter", *, subscribed: bool
) -> FighterWithSubscription:
    """Convert a Fighter ORM model to a dict with subscription status."""
    base = dict(serialize_fighter(fighter))
    base["subscription_status"] = "1" if subscribed else "0"
    return base  # type: ignore[return-value]


__all__ = [
    "format_datetime",
    "serialize_fighter",
    "serialize_fighter_with_subscription",
]
