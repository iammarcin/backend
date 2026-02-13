"""Unit tests for semantic search settings parser."""

from __future__ import annotations

import logging

import pytest

from config.semantic_search import defaults as semantic_defaults
from features.semantic_search.utils import settings_parser
from features.semantic_search.utils.parsers import (
    _parse_date_range_from_fields,
    _parse_tags_from_string,
)
from features.semantic_search.utils.settings_parser import parse_semantic_settings


def _apply_semantic_defaults(
    monkeypatch,
    *,
    enabled: bool = True,
    limit: int = 10,
    threshold: float = 0.7,
) -> None:
    """Helper to patch semantic default values for tests."""

    monkeypatch.setattr(semantic_defaults, "ENABLED", enabled)
    monkeypatch.setattr(semantic_defaults, "DEFAULT_LIMIT", limit)
    monkeypatch.setattr(semantic_defaults, "DEFAULT_SCORE_THRESHOLD", threshold)


@pytest.fixture(autouse=True)
def _reset_semantic_defaults(monkeypatch) -> None:
    """Ensure semantic defaults are reset before each test."""

    _apply_semantic_defaults(monkeypatch)


class TestSemanticSettingsParser:
    """Tests that the parser reads the new semantic.* structure."""

    def test_respects_global_flag(self, monkeypatch) -> None:
        monkeypatch.setattr(semantic_defaults, "ENABLED", False)

        user_settings = {"semantic": {"enabled": True}}

        result = settings_parser.parse_semantic_settings(user_settings)

        assert result is None

    def test_disabled_via_semantic_structure(self) -> None:
        user_settings = {"semantic": {"enabled": False}}

        result = parse_semantic_settings(user_settings)

        assert result is None

    def test_missing_semantic_section_returns_none(self) -> None:
        result = parse_semantic_settings({})

        assert result is None

    def test_invalid_semantic_section_returns_none(self) -> None:
        result = parse_semantic_settings({"semantic": "invalid"})

        assert result is None

    def test_parse_complete_new_structure(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "search_mode": "hybrid",
                "limit": 5,
                "threshold": 0.2,
                "tags": ["work", "project"],
                "date_range": {
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
                "message_type": "user",
                "session_ids": [123, 456],
                "top_sessions": 3,
                "messages_per_session": 5,
            }
        }

        settings = parse_semantic_settings(user_settings, current_session_id="789")

        assert settings is not None
        assert settings.enabled is True
        assert settings.search_mode == "hybrid"
        assert settings.limit == 5
        assert settings.threshold == 0.2
        assert settings.tags == ["work", "project"]
        assert settings.date_range == ("2024-01-01", "2024-12-31")
        assert settings.message_type == "user"
        assert settings.session_ids == [123, 456]
        assert settings.top_sessions == 3
        assert settings.messages_per_session == 5
        assert settings.has_filters is True

    def test_defaults_when_optional_fields_missing(self) -> None:
        user_settings = {"semantic": {"enabled": True}}

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.limit == semantic_defaults.DEFAULT_LIMIT
        assert settings.threshold == semantic_defaults.DEFAULT_SCORE_THRESHOLD
        assert settings.search_mode == semantic_defaults.DEFAULT_SEARCH_MODE
        assert settings.tags is None
        assert settings.date_range is None
        assert settings.message_type is None
        assert settings.session_ids is None
        assert settings.top_sessions == semantic_defaults.MULTI_TIER_TOP_SESSIONS
        assert (
            settings.messages_per_session
            == semantic_defaults.MULTI_TIER_MESSAGES_PER_SESSION
        )
        assert settings.has_filters is False

    def test_invalid_search_mode_falls_back_to_hybrid(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "search_mode": "unknown",
            }
        }

        with caplog.at_level(logging.WARNING):
            settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.search_mode == semantic_defaults.DEFAULT_SEARCH_MODE
        assert "Unknown search mode" in caplog.text

    def test_custom_search_mode(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "search_mode": semantic_defaults.SEARCH_MODE_SESSION_SEMANTIC,
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.search_mode == semantic_defaults.SEARCH_MODE_SESSION_SEMANTIC

    def test_snake_case_multitier_settings(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "search_mode": semantic_defaults.SEARCH_MODE_MULTI_TIER,
                "top_sessions": 7,
                "messages_per_session": 9,
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.top_sessions == 7
        assert settings.messages_per_session == 9

    def test_invalid_limit_falls_back_to_default(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "limit": "invalid",
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.limit == semantic_defaults.DEFAULT_LIMIT

    def test_invalid_threshold_falls_back_to_default(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "threshold": "invalid",
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.threshold == semantic_defaults.DEFAULT_SCORE_THRESHOLD

    def test_invalid_tags_list_returns_none(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "tags": ["", 123, None],
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.tags is None

    def test_session_ids_filter_parses_values(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "session_ids": ["abc", 123, "", None],
            }
        }

        settings = parse_semantic_settings(user_settings, current_session_id="abc")

        assert settings is not None
        assert settings.session_ids == ["abc", 123]

    def test_message_type_validation(self) -> None:
        user_settings = {
            "semantic": {
                "enabled": True,
                "message_type": "both",
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.message_type is None

    def test_empty_date_range_returns_none(self) -> None:
        """Test that empty start/end dates are treated as no filter."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "date_range": {
                    "start": "",
                    "end": "",
                },
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.date_range is None
        assert settings.has_filters is False
        # But frontend DID provide filter fields (even though they're empty)
        assert settings.filter_fields_provided is True

    def test_empty_start_date_returns_none(self) -> None:
        """Test that empty start date is treated as no filter."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "date_range": {
                    "start": "",
                    "end": "2024-12-31",
                },
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.date_range is None

    def test_empty_end_date_returns_none(self) -> None:
        """Test that empty end date is treated as no filter."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "date_range": {
                    "start": "2024-01-01",
                    "end": "",
                },
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.date_range is None

    def test_whitespace_only_date_range_returns_none(self) -> None:
        """Test that whitespace-only dates are treated as empty."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "date_range": {
                    "start": "   ",
                    "end": "  ",
                },
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.date_range is None
        assert settings.filter_fields_provided is True

    def test_no_filter_fields_provided(self) -> None:
        """Test that filter_fields_provided is False when no filter fields sent."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "limit": 5,
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.filter_fields_provided is False
        assert settings.has_filters is False

    def test_filter_fields_provided_with_valid_filters(self) -> None:
        """Test that filter_fields_provided is True when filters are sent."""
        user_settings = {
            "semantic": {
                "enabled": True,
                "tags": ["work"],
                "limit": 5,
            }
        }

        settings = parse_semantic_settings(user_settings)

        assert settings is not None
        assert settings.filter_fields_provided is True
        assert settings.has_filters is True


# ============================================================================
# Tests for _parse_tags_from_string()
# ============================================================================


class TestParseTagsFromString:
    """Tests for comma-separated tags parsing."""

    def test_normal_tags(self) -> None:
        """Test parsing normal comma-separated tags."""
        assert _parse_tags_from_string("tag1,tag2,tag3") == ["tag1", "tag2", "tag3"]

    def test_with_whitespace(self) -> None:
        """Test parsing tags with whitespace (should be trimmed)."""
        assert _parse_tags_from_string("tag1, tag2 , tag3") == ["tag1", "tag2", "tag3"]
        assert _parse_tags_from_string(" tag1,tag2,tag3 ") == ["tag1", "tag2", "tag3"]

    def test_single_tag(self) -> None:
        """Test parsing single tag."""
        assert _parse_tags_from_string("single") == ["single"]

    def test_empty_string(self) -> None:
        """Test parsing empty string returns None."""
        assert _parse_tags_from_string("") is None
        assert _parse_tags_from_string("   ") is None

    def test_trailing_comma(self) -> None:
        """Test parsing tags with trailing comma."""
        assert _parse_tags_from_string("tag1,tag2,") == ["tag1", "tag2"]

    def test_only_commas(self) -> None:
        """Test parsing string with only commas."""
        assert _parse_tags_from_string(",,,") is None

    def test_invalid_type(self) -> None:
        """Test parsing non-string returns None with warning."""
        assert _parse_tags_from_string(123) is None
        assert _parse_tags_from_string(["tag1", "tag2"]) is None
        assert _parse_tags_from_string(None) is None


# ============================================================================
# Tests for _parse_date_range_from_fields()
# ============================================================================


class TestParseDateRangeFromFields:
    """Tests for separate date fields parsing."""

    def test_valid_dates(self) -> None:
        """Test parsing valid date range returns RFC 3339 format."""
        result = _parse_date_range_from_fields("2025-01-01", "2025-12-31")
        assert result == ("2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z")

    def test_with_whitespace(self) -> None:
        """Test parsing dates with whitespace (should be trimmed)."""
        result = _parse_date_range_from_fields(" 2025-01-01 ", " 2025-12-31 ")
        assert result == ("2025-01-01T00:00:00Z", "2025-12-31T23:59:59Z")

    def test_both_empty(self) -> None:
        """Test parsing when both fields are empty."""
        assert _parse_date_range_from_fields("", "") is None

    def test_one_empty(self) -> None:
        """Test parsing when one field is empty (should return None)."""
        assert _parse_date_range_from_fields("2025-01-01", "") is None
        assert _parse_date_range_from_fields("", "2025-12-31") is None

    def test_none_values(self) -> None:
        """Test parsing when fields are None."""
        assert _parse_date_range_from_fields(None, None) is None
        assert _parse_date_range_from_fields("2025-01-01", None) is None
        assert _parse_date_range_from_fields(None, "2025-12-31") is None

    def test_invalid_format(self) -> None:
        """Test parsing dates with invalid format."""
        assert _parse_date_range_from_fields("2025/01/01", "2025-12-31") is None
        assert _parse_date_range_from_fields("2025-01-01", "12-31-2025") is None
        assert _parse_date_range_from_fields("01-01-2025", "2025-12-31") is None
        assert _parse_date_range_from_fields("not-a-date", "2025-12-31") is None

    def test_invalid_type(self) -> None:
        """Test parsing non-string types."""
        assert _parse_date_range_from_fields(123, 456) is None
        assert _parse_date_range_from_fields(["2025-01-01"], ["2025-12-31"]) is None


# ============================================================================
# Tests for Logging
# ============================================================================


class TestLogging:
    """Tests for logging behavior."""

    def test_parse_tags_logs_warning_on_invalid_type(self, caplog) -> None:
        """Test that invalid tag type logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = _parse_tags_from_string(123)

        assert result is None
        assert "Invalid tags format" in caplog.text

    def test_parse_date_range_logs_warning_on_invalid_format(self, caplog) -> None:
        """Test that invalid date format logs a warning."""
        with caplog.at_level(logging.WARNING):
            result = _parse_date_range_from_fields("invalid", "2025-12-31")

        assert result is None
        assert "Invalid date" in caplog.text
