"""Unit tests for Qdrant filter builder."""

from __future__ import annotations

import pytest

from core.providers.semantic.qdrant_filters import build_filter
from core.providers.semantic.schemas import SearchRequest


class TestBuildFilterBasics:
    """Tests for basic filter building."""

    def test_filter_includes_customer_id(self) -> None:
        """Test that customer_id is always included in filter."""
        request = SearchRequest(query="test", customer_id=42)
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        assert len(filter_obj.must) == 1
        assert filter_obj.must[0].key == "customer_id"

    def test_filter_with_tags(self) -> None:
        """Test that tags filter is added when provided."""
        request = SearchRequest(query="test", customer_id=1, tags=["work", "project"])
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        # Should have: customer_id + tags
        assert len(filter_obj.must) == 2

        tag_condition = [c for c in filter_obj.must if c.key == "tags"][0]
        assert hasattr(tag_condition.match, "any")

    def test_filter_with_message_type_user(self) -> None:
        """Test that message_type filter is added for 'user'."""
        request = SearchRequest(query="test", customer_id=1, message_type="user")
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        msg_type_condition = [c for c in filter_obj.must if c.key == "message_type"]
        assert len(msg_type_condition) == 1

    def test_filter_ignores_message_type_both(self) -> None:
        """Test that message_type='both' is treated as no filter."""
        request = SearchRequest(query="test", customer_id=1, message_type="both")
        filter_obj = build_filter(request)

        # Only customer_id condition
        assert filter_obj.must is not None
        msg_type_conditions = [c for c in filter_obj.must if c.key == "message_type"]
        assert len(msg_type_conditions) == 0


class TestDateRangeFiltering:
    """Tests for date range filter handling."""

    def test_date_range_with_valid_dates(self) -> None:
        """Test that valid date range creates Range condition."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            date_range=("1704067200", "1735689599"),  # unix timestamps
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        date_conditions = [c for c in filter_obj.must if c.key == "timestamp"]
        assert len(date_conditions) == 1
        assert date_conditions[0].range is not None

    def test_date_range_with_empty_strings_ignored(self) -> None:
        """Test that empty string date range is ignored."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            date_range=("", ""),
        )
        filter_obj = build_filter(request)

        # Should only have customer_id condition, no date range
        assert filter_obj.must is not None
        date_conditions = [c for c in filter_obj.must if c.key == "timestamp"]
        assert len(date_conditions) == 0

    def test_date_range_with_empty_start_ignored(self) -> None:
        """Test that empty start date is ignored."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            date_range=("", "1735689599"),
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        date_conditions = [c for c in filter_obj.must if c.key == "timestamp"]
        assert len(date_conditions) == 0

    def test_date_range_with_empty_end_ignored(self) -> None:
        """Test that empty end date is ignored."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            date_range=("1704067200", ""),
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        date_conditions = [c for c in filter_obj.must if c.key == "timestamp"]
        assert len(date_conditions) == 0

    def test_date_range_none_not_processed(self) -> None:
        """Test that None date_range is not processed."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            date_range=None,
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        date_conditions = [c for c in filter_obj.must if c.key == "timestamp"]
        assert len(date_conditions) == 0


class TestSessionIdFiltering:
    """Tests for session ID filter handling."""

    def test_session_ids_with_integers(self) -> None:
        """Test that integer session IDs are filtered properly."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            session_ids=[123, 456],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        session_conditions = [c for c in filter_obj.must if c.key == "session_id"]
        assert len(session_conditions) == 1

    def test_session_ids_with_strings(self) -> None:
        """Test that string session IDs are filtered properly."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            session_ids=["abc", "def"],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        session_conditions = [c for c in filter_obj.must if c.key == "session_id"]
        assert len(session_conditions) == 1

    def test_session_ids_mixed_types(self) -> None:
        """Test that mixed integer and string session IDs work."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            session_ids=[123, "abc", 456, "def"],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        session_conditions = [c for c in filter_obj.must if c.key == "session_id"]
        assert len(session_conditions) == 1

    def test_session_ids_empty_list(self) -> None:
        """Test that empty session IDs list doesn't add filter."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            session_ids=[],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        session_conditions = [c for c in filter_obj.must if c.key == "session_id"]
        assert len(session_conditions) == 0

    def test_session_ids_none(self) -> None:
        """Test that None session_ids doesn't add filter."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            session_ids=None,
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        session_conditions = [c for c in filter_obj.must if c.key == "session_id"]
        assert len(session_conditions) == 0


class TestComplexFilters:
    """Tests for complex filter combinations."""

    def test_all_filters_combined(self) -> None:
        """Test filter building with all filters enabled."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            tags=["work", "ai"],
            date_range=("1704067200", "1735689599"),  # unix timestamps
            message_type="user",
            session_ids=[100, 200],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        # Should have: customer_id + tags + date_range + message_type + session_ids
        assert len(filter_obj.must) == 5

    def test_multiple_filters_with_empty_date_range(self) -> None:
        """Test that empty date_range doesn't block other filters."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            tags=["work"],
            date_range=("", ""),
            message_type="user",
            session_ids=[100],
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        # Should have: customer_id + tags + message_type + session_ids (no date_range)
        assert len(filter_obj.must) == 4
        keys = [c.key for c in filter_obj.must]
        assert "timestamp" not in keys

    def test_none_tags_ignored(self) -> None:
        """Test that None tags are ignored."""
        request = SearchRequest(
            query="test",
            customer_id=1,
            tags=None,
        )
        filter_obj = build_filter(request)

        assert filter_obj.must is not None
        # Only customer_id
        assert len(filter_obj.must) == 1
