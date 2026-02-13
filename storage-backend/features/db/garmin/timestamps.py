"""Timezone-aware conversions for Garmin timestamp payloads.

Garmin reports combine millisecond epoch timestamps with local-device values.
These helpers produce consistent HH:MM strings that can be rendered in the
dashboard without repeating the conversion logic at each call site.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def get_local_offset(gmt_ts: int | None, local_ts: int | None) -> timedelta:
    """Compute the offset between a GMT timestamp and the device local time."""

    if gmt_ts is None or local_ts is None:
        return timedelta(0)

    gmt_dt = datetime.fromtimestamp(gmt_ts / 1000, tz=timezone.utc)
    local_dt = datetime.fromtimestamp(local_ts / 1000, tz=timezone.utc)
    return local_dt - gmt_dt


def convert_timestamp(
    timestamp: int | str | None,
    offset: timedelta,
    *,
    is_iso_string: bool = False,
) -> Optional[str]:
    """Convert GMT timestamps into local HH:MM strings respecting offsets.

    Parameters
    ----------
    timestamp:
        Millisecond epoch value or ISO timestamp string delivered by Garmin.
    offset:
        ``timedelta`` representing the device's local offset relative to GMT.
    is_iso_string:
        Set to ``True`` when ``timestamp`` is a string (e.g. ``"2024-07-18T06:00"``).
    """

    if timestamp is None:
        return None

    if is_iso_string:
        if not isinstance(timestamp, str):
            raise ValueError("ISO timestamps must be provided as strings")
        dt = _parse_iso_datetime(timestamp)
    else:
        dt = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc)

    local_dt = dt + offset
    return local_dt.strftime("%H:%M")


def convert_timestamp_to_hhmm(timestamp: int | None) -> Optional[str]:
    """Return a HH:MM representation of an epoch millisecond timestamp."""

    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc).strftime("%H:%M")


def _parse_iso_datetime(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO timestamp: {value}") from exc


__all__ = [
    "convert_timestamp",
    "convert_timestamp_to_hhmm",
    "get_local_offset",
]

