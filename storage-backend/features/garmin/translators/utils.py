"""Utility helpers shared across Garmin translator modules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Mapping, Sequence

from features.garmin.schemas.queries import GarminDataQuery


def walk_payload(payload: Any) -> Iterable[Any]:
    """Depth-first traversal that yields mapping nodes from a nested payload."""

    stack: list[Any] = [payload]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            identifier = id(current)
            if identifier in seen:
                continue
            seen.add(identifier)
            yield current
            for value in current.values():
                if isinstance(value, (Mapping, list, tuple)):
                    stack.append(value)
        elif isinstance(current, (list, tuple)):
            for item in current:
                if isinstance(item, (Mapping, list, tuple)):
                    stack.append(item)


def coerce_date_key(value: Any) -> date | None:
    """Convert supported Garmin date representations to :class:`datetime.date`."""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def iter_mappings(payload: Any) -> Iterable[Mapping[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, Mapping):
        return [payload]
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        return [item for item in payload if isinstance(item, Mapping)]
    return []


def first_mapping(payload: Any) -> Mapping[str, Any] | None:
    if isinstance(payload, Mapping):
        for value in payload.values():
            if isinstance(value, Mapping):
                return value
    return payload if isinstance(payload, Mapping) else None


def query_default_date(query: GarminDataQuery) -> date | None:
    return query.start_date or query.end_date


def extract_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        text = value.strip()
        for separator in ("T", " "):
            if separator in text:
                text = text.split(separator, 1)[0]
                break
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        text = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def deep_get(obj: Any, *keys: str) -> Any:
    current = obj
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


__all__ = [
    "walk_payload",
    "coerce_date_key",
    "iter_mappings",
    "first_mapping",
    "query_default_date",
    "extract_date",
    "parse_datetime",
    "deep_get",
]
