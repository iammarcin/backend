"""Unit conversion and time extraction utilities for Garmin data."""

from __future__ import annotations

from typing import Any


def extract_time_hhmm(timestamp_str: str | None) -> str | None:
    """Extract HH:MM from ISO timestamp or datetime string.

    Handles formats like:
    - '2023-11-10T10:30:00'
    - '2023-11-10 10:30:00'
    - '10:30:00'
    - '10:30'
    """
    if not timestamp_str:
        return None

    try:
        # Split on 'T' or space to separate date from time
        parts = str(timestamp_str).replace("T", " ").split(" ")
        # Get the part with colons (should be time)
        for part in parts:
            if ":" in part:
                # Extract HH:MM (first 5 chars)
                time_str = part[:5]
                return time_str if len(time_str) == 5 else None
        return None
    except (IndexError, AttributeError, TypeError):
        return None


def fahrenheit_to_celsius(value: Any) -> float | None:
    """Convert Fahrenheit to Celsius."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round((numeric - 32.0) * 5.0 / 9.0, 2)


def mph_to_kph(value: Any) -> float | None:
    """Convert miles per hour to kilometers per hour."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return round(numeric * 1.60934, 1)


def extract_zone_seconds(entry: dict[str, Any]) -> dict[int, float]:
    """Extract heart rate zone seconds from activity entry.

    Returns a dictionary mapping zone numbers (1-5) to seconds spent in each zone.
    """
    from collections.abc import Iterable, Mapping

    zones = entry.get("zones")
    results: dict[int, float] = {}
    if isinstance(zones, Iterable):
        for zone in zones:
            if not isinstance(zone, Mapping):
                continue
            number = zone.get("zoneNumber")
            seconds = zone.get("secsInZone")
            if isinstance(number, int) and 1 <= number <= 5 and isinstance(seconds, (int, float)):
                results[number] = float(seconds)
    return results
