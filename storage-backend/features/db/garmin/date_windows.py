"""Helpers for building and adjusting Garmin reporting date ranges.

The Garmin reporting APIs often return data that is offset by a day or spans a
rolling yearly window.  These functions encapsulate the small pieces of date
math necessary to align database queries with the product expectations.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence


def transform_date(provided_date: datetime | date) -> tuple[date, date]:
    """Return the Garmin metrics date range for a provided anchor date.

    The Garmin UI requests data for a 13 month window that starts on the first
    day of the month following the same month in the previous year and ends on
    the final day of the month containing ``provided_date``.
    """

    if not isinstance(provided_date, (datetime, date)):
        raise ValueError("provided_date must be a date or datetime instance")

    if isinstance(provided_date, datetime):
        provided = provided_date.date()
    else:
        provided = provided_date
    today = datetime.now(timezone.utc).date()
    if provided > today:
        raise ValueError("provided_date cannot be in the future")

    first_day_last_year_month = (provided - timedelta(days=365)).replace(day=1) + timedelta(days=31)
    first_day_last_year_month = first_day_last_year_month.replace(day=1)
    last_day_current_month = (provided.replace(day=1) + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    return first_day_last_year_month, last_day_current_month


def adjust_dates_for_special_modes(
    mode: str,
    table: str,
    start_date: str | date | None,
    end_date: str | date | None,
    next_day_tables: Sequence[str],
) -> tuple[Optional[str], Optional[str]]:
    """Adjust date boundaries for correlation modes that shift data forward."""

    start = _coerce_date(start_date)
    end = _coerce_date(end_date)

    if mode == "correlation" and table in set(next_day_tables):
        start = start + timedelta(days=1) if start else None
        end = end + timedelta(days=1) if end else None

    return (_format_date(start), _format_date(end))


def revert_dates_for_special_modes(
    mode: str,
    table: str,
    data_list: Sequence[Mapping[str, Any]],
    next_day_tables: Sequence[str],
) -> List[Dict[str, Any]]:
    """Revert shifted calendar dates back to their original day."""

    adjusted: List[Dict[str, Any]] = []
    shift_required = mode == "correlation" and table in set(next_day_tables)

    for record in data_list:
        new_record = dict(record)
        if shift_required and "calendar_date" in new_record and new_record["calendar_date"]:
            calendar_date = _coerce_date(new_record["calendar_date"])
            if calendar_date:
                new_record["calendar_date"] = _format_date(calendar_date - timedelta(days=1))
        adjusted.append(new_record)

    return adjusted


def _coerce_date(value: str | date | datetime | None) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"Date values must use YYYY-MM-DD format: {value}") from exc
    raise ValueError("Unsupported date value type")


def _format_date(value: Optional[date]) -> Optional[str]:
    return value.strftime("%Y-%m-%d") if value else None


__all__ = [
    "adjust_dates_for_special_modes",
    "revert_dates_for_special_modes",
    "transform_date",
]

