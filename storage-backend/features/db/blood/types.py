"""Typed dictionaries describing Blood repository payloads."""

from __future__ import annotations

from datetime import date
from typing import TypedDict


class BloodTestRow(TypedDict):
    """Shape returned by :class:`BloodTestRepository` list operations."""

    id: int
    test_definition_id: int
    test_date: date
    result_value: str | None
    result_unit: str | None
    reference_range: str | None
    category: str | None
    test_name: str | None
    short_explanation: str | None
    long_explanation: str | None


__all__ = ["BloodTestRow"]
