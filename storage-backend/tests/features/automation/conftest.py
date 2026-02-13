"""Fixtures for automation feature tests."""

import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock


@pytest.fixture
def sample_automation_request():
    """Sample automation request for tests."""
    return {
        "id": "req-123",
        "type": "feature",
        "status": "pending",
        "priority": "medium",
        "title": "Add user authentication",
        "description": "Implement JWT-based authentication for API",
        "attachments": None,
        "session_id": None,
        "current_phase": None,
        "milestones": None,
        "started_at": None,
        "last_update": None,
        "completed_at": None,
        "plan_document": None,
        "pr_url": None,
        "test_results": None,
        "deployment_log": None,
        "error_message": None,
        "retry_count": 0,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }


@pytest.fixture
def sample_feature_request():
    """Sample feature request data."""
    return {
        "type": "feature",
        "title": "Implement OAuth2 authentication",
        "description": "Add OAuth2 support for third-party integrations",
        "priority": "high",
        "attachments": None,
    }


@pytest.fixture
def sample_bug_report():
    """Sample bug report data."""
    return {
        "type": "bug",
        "title": "WebSocket connection timeout",
        "description": "Connection drops after extended periods of inactivity",
        "priority": "high",
        "attachments": [
            {
                "type": "log",
                "filename": "error.log",
                "content": "WebSocket closed unexpectedly",
            }
        ],
    }


@pytest.fixture
def sample_research_task():
    """Sample research task data."""
    return {
        "type": "research",
        "title": "Investigate caching strategies",
        "description": "Research Redis vs in-memory caching",
        "priority": "low",
        "attachments": None,
    }
