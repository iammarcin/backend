"""Unit conversion and coercion helpers for activity schemas."""

from __future__ import annotations

from typing import Any


def coerce_float(value: Any) -> float | None:
    """Best-effort float conversion returning ``None`` when coercion fails."""

    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return None


def fahrenheit_to_celsius(value: Any) -> float | None:
    """Convert Fahrenheit temperature to Celsius."""
    numeric = coerce_float(value)
    if numeric is None:
        return None
    return round((numeric - 32.0) * 5.0 / 9.0, 2)


def mph_to_kph(value: Any) -> float | None:
    """Convert miles per hour to kilometers per hour."""
    numeric = coerce_float(value)
    if numeric is None:
        return None
    return round(numeric * 1.60934, 1)
