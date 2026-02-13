"""Example tests demonstrating Milestone 1 infrastructure.

These tests serve as documentation and validation that the new
pytest markers and fixtures work correctly.
"""

import pytest


# Example 1: Using pytest.mark.skipif with helper functions
@pytest.mark.skipif(
    not pytest.helpers.is_semantic_search_available(),
    reason="Semantic search not configured (OPENAI_API_KEY, semantic_search_enabled)",
)
def test_semantic_search_with_marker():
    """Test that only runs when semantic search is configured."""
    from tests.helpers import is_semantic_search_available

    # If we get here, semantic search MUST be available
    assert is_semantic_search_available()


# Example 2: Using fixture to check prerequisites
@pytest.mark.requires_semantic_search
def test_semantic_search_with_fixture(require_semantic_search):
    """Test that only runs when semantic search is configured."""
    from tests.helpers import is_semantic_search_available

    # The fixture already skipped if not available
    assert is_semantic_search_available()


# Example 3: Using marker for documentation (doesn't enforce skipping)
@pytest.mark.requires_semantic_search
def test_semantic_search_with_marker_only():
    """Test marked as requiring semantic search.

    Note: This marker is for documentation only. To actually skip
    when not available, use the fixture or skipif pattern.
    """
    # This test will run regardless of semantic search availability
    # (unless you use the fixture or skipif)
    pass


# Example 4: Testing that helpers work correctly
@pytest.mark.requires_semantic_search
@pytest.mark.requires_garmin_db
@pytest.mark.requires_sqs
def test_helper_functions():
    """Validate that environment validation helpers work."""
    from tests.helpers import (
        is_semantic_search_available,
        is_garmin_db_available,
        get_missing_prerequisites,
    )

    # These should return booleans
    assert isinstance(is_semantic_search_available(), bool)
    assert isinstance(is_garmin_db_available(), bool)

    # Missing prerequisites should return a list
    missing = get_missing_prerequisites("semantic_search")
    assert isinstance(missing, list)


# Example 5: Multiple prerequisites
@pytest.mark.requires_garmin_db
@pytest.mark.requires_sqs
def test_multiple_prerequisites(require_garmin_db, require_sqs):
    """Test that requires both Garmin DB and SQS."""
    from tests.helpers import is_garmin_db_available, is_sqs_available

    # Both must be available for test to run
    assert is_garmin_db_available()
    assert is_sqs_available()
