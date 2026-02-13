"""Utilities for transforming raw Withings measurement payloads.

Withings returns dense measurement objects that require decoding before they
can be stored in the database.  The helpers here keep that logic out
of the main client so it can focus on HTTP requests and token management.
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timezone
from typing import Any, Iterable, Mapping


def to_timestamp_range(start: date, end: date | None) -> tuple[int, int]:
    """Convert calendar dates into the inclusive timestamp window required by Withings."""

    start_dt = datetime.combine(start, dt_time.min, tzinfo=timezone.utc)
    end_value = end or start
    end_dt = datetime.combine(end_value, dt_time.max, tzinfo=timezone.utc)
    return int(start_dt.timestamp()), int(end_dt.timestamp())


def normalise_measure_group(group: Mapping[str, Any], *, height_cm: float | None) -> dict[str, Any]:
    """Normalise a Withings measurement group into a flat dictionary of metrics."""

    measures = group.get("measures") or []
    if not isinstance(measures, Iterable):  # pragma: no cover - defensive guard
        return {}

    values: dict[int, float] = {}
    for item in measures:
        try:
            code = int(item.get("type"))
            raw = float(item.get("value"))
            unit = int(item.get("unit", 0))
        except (TypeError, ValueError):
            continue
        values[code] = raw * (10 ** unit)

    timestamp = group.get("date")
    calendar_date: date | None = None
    if timestamp is not None:
        try:
            calendar_date = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).date()
        except (TypeError, ValueError, OSError):  # pragma: no cover - invalid payload
            calendar_date = None

    record: dict[str, Any] = {}
    if calendar_date:
        record["calendar_date"] = calendar_date

    weight = values.get(1)
    if weight is not None:
        record["weight"] = round(weight, 2)

    fat_mass = values.get(8)
    if fat_mass is not None:
        record["body_fat_mass"] = round(fat_mass, 2)

    fat_percentage = values.get(6)
    if fat_percentage is not None:
        record["body_fat_percentage"] = round(fat_percentage, 2)

    water_mass = values.get(77)
    if water_mass is not None:
        record["body_water_mass"] = round(water_mass, 2)

    bone_mass = values.get(88)
    if bone_mass is not None:
        record["bone_mass"] = round(bone_mass, 2)

    muscle_mass = values.get(76)
    if muscle_mass is not None:
        record["muscle_mass"] = round(muscle_mass, 2)

    visceral_fat = values.get(170)
    if visceral_fat is not None:
        record["visceral_fat"] = round(visceral_fat, 2)

    bmr = values.get(226)
    if bmr is not None:
        try:
            record["basal_metabolic_rate"] = int(round(bmr))
        except (TypeError, ValueError):  # pragma: no cover - invalid payload
            record["basal_metabolic_rate"] = None

    if weight and height_cm:
        try:
            height_m = float(height_cm) / 100
            if height_m > 0:
                record["bmi"] = round(weight / (height_m**2), 1)
        except (TypeError, ValueError):  # pragma: no cover - invalid height
            pass

    def _percent(mass: float | None) -> float | None:
        if weight is None or mass is None or weight == 0:
            return None
        return round(mass * 100 / weight, 2)

    water_pct = _percent(water_mass)
    if water_pct is not None:
        record["body_water_percentage"] = water_pct

    bone_pct = _percent(bone_mass)
    if bone_pct is not None:
        record["bone_mass_percentage"] = bone_pct

    muscle_pct = _percent(muscle_mass)
    if muscle_pct is not None:
        record["muscle_mass_percentage"] = muscle_pct

    return record


__all__ = ["to_timestamp_range", "normalise_measure_group"]
