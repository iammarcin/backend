"""Utility helpers shared by the Garmin Connect provider codebase.

The Garmin API has a fragmented set of endpoints that require repetitive date
formatting and range calculations.  Centralising these helpers keeps the
high-level client focused on HTTP orchestration.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import logging

logger = logging.getLogger(__name__)


def to_date_string(value: date | str | None) -> str:
    """Return ``value`` serialised as ``YYYY-MM-DD``.

    Parameters
    ----------
    value:
        A :class:`datetime.date`, ISO formatted string, or ``None``.  ``None``
        values are rejected because Garmin endpoints typically require explicit
        dates.
    """

    if value is None:
        raise ValueError("date value is required for Garmin requests")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def date_range(start: date | None, end: date | None) -> Iterable[str]:
    """Yield ISO formatted dates between ``start`` and ``end`` inclusive."""

    if start is None:
        if end is None:
            raise ValueError("start date must be provided for Garmin dataset fetches")
        start = end
    if end is None:
        end = start

    cursor = start
    while cursor <= end:
        yield cursor.isoformat()
        cursor = cursor + timedelta(days=1)


def ensure_parent(path: Path) -> None:
    """Create the parent directory for ``path`` when missing."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Unable to create Garmin session directory", extra={"path": str(path)}, exc_info=exc)


__all__ = ["date_range", "ensure_parent", "to_date_string"]
