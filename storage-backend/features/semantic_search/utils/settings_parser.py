"""Settings parser for semantic search configuration."""

from __future__ import annotations

import logging
from typing import Any

from config.semantic_search import defaults as semantic_defaults
from features.semantic_search.utils import parsers as parser_utils

VALID_SEARCH_MODES = {
    semantic_defaults.SEARCH_MODE_HYBRID,
    semantic_defaults.SEARCH_MODE_SEMANTIC,
    semantic_defaults.SEARCH_MODE_KEYWORD,
    semantic_defaults.SEARCH_MODE_SESSION_SEMANTIC,
    semantic_defaults.SEARCH_MODE_SESSION_HYBRID,
    semantic_defaults.SEARCH_MODE_MULTI_TIER,
}

logger = logging.getLogger(__name__)


class SemanticSearchSettings:
    """Parsed and validated semantic search settings."""

    def __init__(
        self,
        enabled: bool = True,
        limit: int | None = None,
        threshold: float | None = None,
        tags: list[str] | None = None,
        date_range: tuple[str, str] | None = None,
        message_type: str | None = None,
        session_ids: list[str | int] | None = None,
        search_mode: str = "hybrid",
        top_sessions: int | None = None,
        messages_per_session: int | None = None,
        filter_fields_provided: bool = False,
    ):
        self.enabled = enabled
        self.limit = limit if limit is not None else semantic_defaults.DEFAULT_LIMIT
        self.threshold = (
            threshold if threshold is not None else semantic_defaults.DEFAULT_SCORE_THRESHOLD
        )
        self.tags = tags
        self.date_range = date_range
        self.message_type = message_type
        self.session_ids = session_ids
        self.search_mode = search_mode
        self.top_sessions = top_sessions or semantic_defaults.MULTI_TIER_TOP_SESSIONS
        self.messages_per_session = (
            messages_per_session or semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION
        )
        self.filter_fields_provided = filter_fields_provided

    @property
    def has_filters(self) -> bool:
        """Check if any filters are applied."""
        return bool(
            self.tags or self.date_range or self.message_type or self.session_ids
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/debugging."""
        return {
            "enabled": self.enabled,
            "limit": self.limit,
            "threshold": self.threshold,
            "tags": self.tags,
            "date_range": self.date_range,
            "message_type": self.message_type,
            "session_ids": self.session_ids,
            "has_filters": self.has_filters,
            "search_mode": self.search_mode,
            "top_sessions": self.top_sessions,
            "messages_per_session": self.messages_per_session,
        }


def _parse_search_mode(value: Any) -> str:
    """Validate and normalize semantic_search_mode setting."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in VALID_SEARCH_MODES:
            return normalized
        logger.warning("Unknown search mode '%s', defaulting to hybrid", value)
    return semantic_defaults.DEFAULT_SEARCH_MODE


def parse_semantic_settings(
    user_settings: dict[str, Any],
    current_session_id: str | None = None,
) -> SemanticSearchSettings | None:
    """Parse and validate semantic search settings from user settings.

    Args:
        user_settings: User settings dictionary (typically from WebSocket payload)
        current_session_id: Current session ID (for logging context)

    Returns:
        SemanticSearchSettings if semantic search is enabled, None otherwise
    """
    if not semantic_defaults.ENABLED:
        logger.debug("Semantic search disabled via application settings")
        return None

    semantic_settings = user_settings.get("semantic", {})
    if not isinstance(semantic_settings, dict):
        logger.warning("Invalid semantic settings format, disabling semantic search")
        return None

    enabled = semantic_settings.get("enabled")
    if not enabled:
        return None

    # Parse limit - fall back to defaults if missing
    limit = parser_utils._parse_limit(semantic_settings.get("limit"))
    if limit is None:
        limit = semantic_defaults.DEFAULT_LIMIT

    # Parse threshold - fall back to defaults if missing
    threshold = parser_utils._parse_threshold(semantic_settings.get("threshold"))
    if threshold is None:
        threshold = semantic_defaults.DEFAULT_SCORE_THRESHOLD

    # Parse tags - semantic section now authoritative
    tags = parser_utils._parse_tags(semantic_settings.get("tags"))

    # Parse date range - semantic section now authoritative
    date_range = parser_utils._parse_date_range(semantic_settings.get("date_range"))

    # Parse message type - semantic section now authoritative
    message_type = parser_utils._parse_message_type(semantic_settings.get("message_type"))

    # Parse session IDs filter
    session_ids = parser_utils._parse_session_ids(
        semantic_settings.get("session_ids"), current_session_id
    )

    search_mode = _parse_search_mode(semantic_settings.get("search_mode"))

    top_sessions = parser_utils._parse_limit(semantic_settings.get("top_sessions"))
    if top_sessions is None:
        top_sessions = semantic_defaults.MULTI_TIER_TOP_SESSIONS

    messages_per_session = parser_utils._parse_limit(
        semantic_settings.get("messages_per_session")
    )
    if messages_per_session is None:
        messages_per_session = semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION

    # Check if frontend provided any filter fields (for logging/diagnostics)
    # This is different from has_filters: we want to log when frontend TRIED to set filters,
    # even if they were empty/invalid and got normalized to None
    filter_fields_provided = any(
        key in semantic_settings
        for key in ("tags", "date_range", "message_type", "session_ids")
    )

    settings_obj = SemanticSearchSettings(
        enabled=True,
        limit=limit,
        threshold=threshold,
        tags=tags,
        date_range=date_range,
        message_type=message_type,
        session_ids=session_ids,
        search_mode=search_mode,
        top_sessions=top_sessions,
        messages_per_session=messages_per_session,
        filter_fields_provided=filter_fields_provided,
    )

    logger.debug(
        "Parsed semantic settings: %s",
        {k: v for k, v in settings_obj.to_dict().items() if k != "enabled"},
    )

    return settings_obj


__all__ = ["SemanticSearchSettings", "parse_semantic_settings"]
