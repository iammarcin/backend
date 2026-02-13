"""Shared utilities for chat repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable


def coerce_datetime(value: datetime | str | None) -> datetime | None:
    """Return ``value`` as a :class:`~datetime.datetime` when possible."""

    if isinstance(value, datetime) or value is None:
        return value
    return datetime.fromisoformat(value)


def normalise_tags(tags: Iterable[str] | None) -> list[str]:
    """Ensure tags are stored as a list of strings with ``None`` values removed."""

    if tags is None:
        return []
    return [str(tag) for tag in tags if tag is not None]


__all__ = ["coerce_datetime", "normalise_tags"]

