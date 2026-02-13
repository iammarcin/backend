"""Shared helpers and base schema for Garmin request validation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """Convert snake_case field names to camelCase for Garmin payload parity."""

    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def parse_date(value: Any) -> date:
    """Coerce Pydantic inputs into a :class:`date` instance."""

    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:  # pragma: no cover - handled by pydantic error formatting
            raise ValueError("calendar_date must use YYYY-MM-DD format") from exc
    raise TypeError("calendar_date must be a date")


def as_midnight(dt: date) -> date:
    """Return the date for use in calendar_date columns.

    Note: Despite the name, this now returns a date object to match the
    database column type. The name is kept for backward compatibility.
    """
    if isinstance(dt, datetime):
        return dt.date()
    return dt


def format_offset(offset: timedelta) -> str:
    """Format a timezone offset as ``HH:MM:SS`` string expected by downstream DB tables."""

    total_minutes = int(offset.total_seconds() // 60)
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"{hours:02d}:{minutes:02d}:00"


def normalise_iterable(value: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Convert iterables of mappings into serialisable dictionaries."""

    return [dict(item) for item in value or []]


class GarminRequest(BaseModel):
    """Base class providing the shared configuration for Garmin request payloads."""

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel, extra="ignore")


__all__ = [
    "GarminRequest",
    "as_midnight",
    "format_offset",
    "normalise_iterable",
    "parse_date",
    "to_camel",
]
