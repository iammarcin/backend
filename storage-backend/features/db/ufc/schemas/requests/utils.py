"""Utility helpers shared across UFC request schemas."""

from __future__ import annotations


def clean_search(value: str | None) -> str | None:
    """Return a normalized search string or ``None`` when empty."""

    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


__all__ = ["clean_search"]
