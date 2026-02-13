"""JSON serialization helpers for streaming payloads."""

from __future__ import annotations

import base64
import json
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable, Mapping
from uuid import UUID

logger = logging.getLogger(__name__)

# Maximum recursion depth for sanitization (prevents stack overflow)
_MAX_DEPTH = 20


def _sanitize_mapping(mapping: Mapping[Any, Any], visited: set[int], depth: int) -> dict[str, Any]:
    return {
        str(key): _sanitize_with_context(value, visited, depth + 1)
        for key, value in mapping.items()
    }


def _sanitize_iterable(items: Iterable[Any], visited: set[int], depth: int) -> list[Any]:
    return [_sanitize_with_context(item, visited, depth + 1) for item in items]


def _sanitize_with_context(obj: Any, visited: set[int], depth: int) -> Any:
    """Internal sanitizer with circular reference detection and depth limiting."""

    # Depth limit protection
    if depth > _MAX_DEPTH:
        logger.warning("Max sanitization depth exceeded, converting to string")
        return f"<max_depth_exceeded: {type(obj).__name__}>"

    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, (date, time)):
        return obj.isoformat()

    if isinstance(obj, timedelta):
        return obj.total_seconds()

    if isinstance(obj, UUID):
        return str(obj)

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, Enum):
        return _sanitize_with_context(obj.value, visited, depth + 1)

    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")

    # Circular reference detection for mutable objects
    obj_id = id(obj)
    if obj_id in visited:
        return f"<circular_ref: {type(obj).__name__}>"

    # Add to visited set for complex objects
    if isinstance(obj, (Mapping, list, tuple, set)) or hasattr(obj, "__dict__"):
        visited.add(obj_id)

    try:
        if isinstance(obj, Mapping):
            return _sanitize_mapping(obj, visited, depth)

        if isinstance(obj, (list, tuple, set)):
            return _sanitize_iterable(obj, visited, depth)

        if hasattr(obj, "__dict__"):
            return _sanitize_with_context(vars(obj), visited, depth + 1)

        logger.warning(
            "Sanitizing unknown type %s to string representation",
            type(obj).__name__,
        )
        return str(obj)
    finally:
        # Remove from visited after processing (allows same object in different branches)
        if obj_id in visited:
            visited.discard(obj_id)


def sanitize_for_json(obj: Any) -> Any:
    """Recursively convert objects to JSON-serializable representations.

    Handles circular references and limits recursion depth to prevent stack overflow.
    """

    return _sanitize_with_context(obj, visited=set(), depth=0)


def is_json_serializable(obj: Any) -> bool:
    """Return True if obj can be dumped to JSON."""

    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def validate_json_serializable(obj: Any, *, context: str | None = None) -> None:
    """Raise TypeError if obj cannot be dumped to JSON."""

    try:
        json.dumps(obj)
    except (TypeError, ValueError) as exc:
        ctx = f" ({context})" if context else ""
        raise TypeError(f"Object not JSON-serializable{ctx}: {exc}") from exc
