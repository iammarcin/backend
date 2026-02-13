"""Helper functions for parsing semantic search settings."""

import logging
import re
from typing import Any

from config.semantic_search import defaults as semantic_defaults

logger = logging.getLogger(__name__)


def _parse_tags(tags_value: Any) -> list[str] | None:
    """Parse and validate tags filter coming from semantic settings."""
    if not tags_value:
        return None

    if isinstance(tags_value, list):
        parsed_tags = [
            tag.strip()
            for tag in tags_value
            if isinstance(tag, str) and tag.strip()
        ]
        return parsed_tags or None

    logger.warning("Invalid tags format: %s, ignoring", type(tags_value).__name__)
    return None


def _parse_tags_from_string(tags_value: Any) -> list[str] | None:
    """Parse comma-separated tags string.

    Args:
        tags_value: Comma-separated string like "tag1,tag2,tag3"

    Returns:
        List of trimmed tags, or None if empty/invalid

    Examples:
        "tag1,tag2,tag3" -> ["tag1", "tag2", "tag3"]
        "tag1, tag2 , tag3" -> ["tag1", "tag2", "tag3"]  # strips whitespace
        "" -> None
        "single" -> ["single"]
    """
    if not tags_value:
        return None

    if not isinstance(tags_value, str):
        logger.warning("Invalid tags format: %s, expected string", type(tags_value).__name__)
        return None

    # Split by comma and strip whitespace
    parsed_tags = [
        tag.strip()
        for tag in tags_value.split(",")
        if tag.strip()  # Filter out empty strings
    ]

    return parsed_tags or None


def _parse_date_range(date_range_value: Any) -> tuple[str, str] | None:
    """Parse and validate date range filter from semantic settings.

    Both start and end must be non-empty strings to be included.
    Returns None if either date is missing or empty.
    """
    if not date_range_value:
        return None

    if not isinstance(date_range_value, dict):
        logger.warning(
            "Invalid dateRange format: %s, ignoring", type(date_range_value).__name__
        )
        return None

    start = date_range_value.get("start")
    end = date_range_value.get("end")

    if not isinstance(start, str) or not isinstance(end, str):
        logger.warning("Invalid date range values, ignoring")
        return None

    # Both dates must be non-empty strings
    start = start.strip()
    end = end.strip()

    if not start or not end:
        logger.debug("Empty date range values, ignoring")
        return None

    return (start, end)


def _parse_date_range_from_fields(
    date_start: Any,
    date_end: Any
) -> tuple[str, str] | None:
    """Parse date range from separate start and end fields and convert to RFC 3339 format.

    Args:
        date_start: Start date string (YYYY-MM-DD)
        date_end: End date string (YYYY-MM-DD)

    Returns:
        Tuple of (start_datetime, end_datetime) in RFC 3339 format, or None if either is missing/invalid

    Examples:
        ("2025-01-01", "2025-12-31") -> ("2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z")
        ("", "") -> None
        ("2025-01-01", "") -> None  # Both required
        (None, None) -> None
    """
    # Both fields must be present and non-empty
    if not date_start or not date_end:
        return None

    if not isinstance(date_start, str) or not isinstance(date_end, str):
        logger.warning(
            "Invalid date range format: start=%s, end=%s",
            type(date_start).__name__,
            type(date_end).__name__
        )
        return None

    # Strip whitespace
    date_start = date_start.strip()
    date_end = date_end.strip()

    if not date_start or not date_end:
        return None

    # Validate YYYY-MM-DD format
    date_pattern = r'^\d{4}-\d{2}-\d{2}$'

    if not re.match(date_pattern, date_start):
        logger.warning("Invalid date_start format: %s (expected YYYY-MM-DD)", date_start)
        return None

    if not re.match(date_pattern, date_end):
        logger.warning("Invalid date_end format: %s (expected YYYY-MM-DD)", date_end)
        return None

    # Convert to RFC 3339 format for Qdrant DatetimeRange
    # Start of day: 00:00:00Z
    # End of day: 23:59:59Z
    start_rfc3339 = f"{date_start}T00:00:00Z"
    end_rfc3339 = f"{date_end}T23:59:59Z"

    return (start_rfc3339, end_rfc3339)


def _parse_message_type(message_type_value: Any) -> str | None:
    """Parse and validate message type filter."""
    if not message_type_value:
        return None

    if not isinstance(message_type_value, str):
        logger.warning(
            "Invalid messageType format: %s, ignoring",
            type(message_type_value).__name__,
        )
        return None

    normalized = message_type_value.lower().strip()

    # Allow "user", "assistant", or "both" (both = no filter)
    if normalized == "both":
        return None

    if normalized not in {"user", "assistant"}:
        logger.warning('Invalid messageType: %s (expected "user" or "assistant")', message_type_value)
        return None

    return normalized


def _parse_session_ids(
    session_ids_value: Any, current_session_id: str | None
) -> list[str | int] | None:
    """Parse and validate session IDs filter."""
    if not session_ids_value:
        return None

    if not isinstance(session_ids_value, list):
        logger.warning(
            "Invalid sessionIds format: %s, ignoring",
            type(session_ids_value).__name__,
        )
        return None

    normalized_ids: list[str | int] = []
    for value in session_ids_value:
        if isinstance(value, int):
            normalized_ids.append(value)
        elif isinstance(value, str) and value.strip():
            normalized_ids.append(value.strip())
        else:
            logger.warning("Invalid session ID value: %s, ignoring", value)

    if not normalized_ids:
        return None

    if current_session_id:
        logger.debug(
            "Semantic search filtering by session IDs (current=%s, filters=%s)",
            current_session_id,
            len(normalized_ids),
        )

    return normalized_ids


def _parse_limit(limit_value: Any) -> int | None:
    """Parse and validate limit parameter, returning None when not provided."""
    if limit_value is None or limit_value == "":
        return None

    if isinstance(limit_value, int) and limit_value > 0:
        return limit_value

    logger.warning("Invalid limit value: %s, ignoring", limit_value)
    return None


def _parse_threshold(threshold_value: Any) -> float | None:
    """Parse and validate threshold parameter, returning None when not provided."""
    if threshold_value is None or threshold_value == "":
        return None

    if isinstance(threshold_value, (int, float)):
        return float(threshold_value)

    logger.warning("Invalid threshold value: %s, ignoring", threshold_value)
    return None


__all__ = [
    "_parse_tags",
    "_parse_tags_from_string",
    "_parse_date_range",
    "_parse_date_range_from_fields",
    "_parse_message_type",
    "_parse_session_ids",
    "_parse_limit",
    "_parse_threshold",
]
