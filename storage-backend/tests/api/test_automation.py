"""Tests for automation request API endpoints."""

from datetime import datetime, timezone
import json
import pytest
import re
from unittest.mock import AsyncMock, MagicMock, patch

from features.automation.schemas import (
    CreateAutomationRequest,
    RequestPriority,
    RequestStatus,
    RequestType,
)

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _make_complete_request_dict(overrides: dict = None) -> dict:
    """Create a complete request dict with all required fields."""
    base = {
        "id": "req-001",
        "type": "feature",
        "status": "pending",
        "priority": "medium",
        "title": "Test Request",
        "description": "Test description",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if overrides:
        base.update(overrides)
    return base


@pytest.fixture
def mock_automation_repository():
    """Mock automation repository."""
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    repo.create.return_value = MagicMock(
        id="request-123",
        type="feature",
        status="pending",
        title="Test Feature",
        description="Test description",
        priority="medium",
        to_dict=lambda: {
            "id": "request-123",
            "type": "feature",
            "status": "pending",
            "title": "Test Feature",
            "description": "Test description",
            "priority": "medium",
        },
    )
    repo.list_requests.return_value = ([], 0)
    return repo


@pytest.fixture
def override_automation_dependencies(mock_automation_repository):
    """Override automation dependencies."""
    from features.automation.dependencies import get_automation_repository
    from main import app

    async def mock_get_automation_repository():
        yield mock_automation_repository

    app.dependency_overrides[get_automation_repository] = mock_get_automation_repository
    yield
    app.dependency_overrides.clear()


class TestCreateAutomationRequest:
    """Tests for creating automation requests."""

    @pytest.mark.asyncio
    async def test_create_feature_request_success(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test successful feature request creation."""
        mock_automation_repository.create.return_value = MagicMock(
            id="req-001",
            type="feature",
            status="pending",
            title="Add rate limiting",
            to_dict=lambda: _make_complete_request_dict({
                "id": "req-001",
                "title": "Add rate limiting",
            }),
        )

        response = await async_authenticated_client.post(
            "/api/v1/automation/requests",
            json={
                "type": "feature",
                "title": "Add rate limiting",
                "description": "Implement rate limiting for public endpoints",
                "priority": "medium",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Service generates its own UUID, so check for valid UUID format
        assert UUID_PATTERN.match(data["data"]["request_id"])
        assert data["data"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_create_bug_report(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test bug report submission."""
        response = await async_authenticated_client.post(
            "/api/v1/automation/requests",
            json={
                "type": "bug",
                "title": "WebSocket disconnection issue",
                "description": "Connection drops after 5 minutes of inactivity",
                "priority": "high",
            },
        )

        assert response.status_code == 200
        mock_automation_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_research_task(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test research task submission."""
        response = await async_authenticated_client.post(
            "/api/v1/automation/requests",
            json={
                "type": "research",
                "title": "Investigate streaming performance",
                "description": "Research why SSE streams are slow",
                "priority": "low",
            },
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_request_validation_error(
        self,
        async_authenticated_client,
        override_automation_dependencies,
    ):
        """Test validation errors."""
        response = await async_authenticated_client.post(
            "/api/v1/automation/requests",
            json={
                "type": "invalid",  # Invalid type
                "title": "Test",
                "description": "Test",
            },
        )

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_request_with_attachments(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test creating request with attachments."""
        response = await async_authenticated_client.post(
            "/api/v1/automation/requests",
            json={
                "type": "bug",
                "title": "Error with logging",
                "description": "Error logs attached",
                "priority": "high",
                "attachments": [
                    {"type": "log", "filename": "error.log", "content": "Stack trace..."},
                    {
                        "type": "screenshot",
                        "filename": "screenshot.png",
                        "url": "https://example.com/img.png",
                    },
                ],
            },
        )

        assert response.status_code == 200


class TestGetAutomationRequest:
    """Tests for retrieving automation requests."""

    @pytest.mark.asyncio
    async def test_get_request_success(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test retrieving existing request."""
        mock_automation_repository.get_by_id.return_value = MagicMock(
            id="req-001",
            type="feature",
            status="implementing",
            title="Test Feature",
            to_dict=lambda: _make_complete_request_dict({
                "id": "req-001",
                "status": "implementing",
                "title": "Test Feature",
            }),
        )

        response = await async_authenticated_client.get("/api/v1/automation/requests/req-001")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == "req-001"

    @pytest.mark.asyncio
    async def test_get_request_not_found(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test 404 for non-existent request."""
        mock_automation_repository.get_by_id.return_value = None

        response = await async_authenticated_client.get("/api/v1/automation/requests/nonexistent")

        assert response.status_code == 404


class TestUpdateAutomationRequest:
    """Tests for updating automation requests."""

    @pytest.mark.asyncio
    async def test_update_status_to_implementing(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test updating request status."""
        mock_automation_repository.update_status.return_value = MagicMock(
            id="req-001",
            status="implementing",
            current_phase="M1",
            to_dict=lambda: _make_complete_request_dict({
                "id": "req-001",
                "status": "implementing",
                "current_phase": "M1",
            }),
        )

        response = await async_authenticated_client.patch(
            "/api/v1/automation/requests/req-001/status",
            params={"status": "implementing", "phase": "M1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_update_status_to_completed(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test marking request as completed."""
        mock_automation_repository.update_status.return_value = MagicMock(
            id="req-001",
            status="completed",
            to_dict=lambda: _make_complete_request_dict({
                "id": "req-001",
                "status": "completed",
            }),
        )

        response = await async_authenticated_client.patch(
            "/api/v1/automation/requests/req-001/status",
            params={"status": "completed"},
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_status_to_failed_with_error(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test marking request as failed with error."""
        mock_automation_repository.update_status.return_value = MagicMock(
            id="req-001",
            status="failed",
            error_message="Tests failed",
            to_dict=lambda: _make_complete_request_dict({
                "id": "req-001",
                "status": "failed",
                "error_message": "Tests failed",
            }),
        )

        response = await async_authenticated_client.patch(
            "/api/v1/automation/requests/req-001/status",
            params={
                "status": "failed",
                "error": "Tests failed",
            },
        )

        assert response.status_code == 200


class TestListAutomationRequests:
    """Tests for listing automation requests."""

    @pytest.mark.asyncio
    async def test_list_requests_empty(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test listing with no requests."""
        mock_automation_repository.list_requests.return_value = ([], 0)

        response = await async_authenticated_client.get("/api/v1/automation/requests")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["items"] == []
        assert data["data"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_requests_with_results(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test listing with results."""
        requests_list = [
            MagicMock(
                id="req-001",
                type="feature",
                status="completed",
                to_dict=lambda: _make_complete_request_dict({
                    "id": "req-001",
                    "status": "completed",
                }),
            ),
            MagicMock(
                id="req-002",
                type="bug",
                status="implementing",
                to_dict=lambda: _make_complete_request_dict({
                    "id": "req-002",
                    "type": "bug",
                    "status": "implementing",
                }),
            ),
        ]
        mock_automation_repository.list_requests.return_value = (requests_list, 2)

        response = await async_authenticated_client.get("/api/v1/automation/requests")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["items"]) == 2
        assert data["data"]["total"] == 2

    @pytest.mark.asyncio
    async def test_list_requests_with_filters(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test filtering requests."""
        mock_automation_repository.list_requests.return_value = ([], 0)

        response = await async_authenticated_client.get(
            "/api/v1/automation/requests",
            params={"status": "completed", "type": "feature", "priority": "high"},
        )

        assert response.status_code == 200
        mock_automation_repository.list_requests.assert_called_once()
        call_kwargs = mock_automation_repository.list_requests.call_args[1]
        assert call_kwargs["status"] == "completed"
        assert call_kwargs["request_type"] == "feature"
        assert call_kwargs["priority"] == "high"

    @pytest.mark.asyncio
    async def test_list_requests_pagination(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test pagination."""
        mock_automation_repository.list_requests.return_value = ([], 50)

        response = await async_authenticated_client.get(
            "/api/v1/automation/requests",
            params={"limit": 10, "offset": 20},
        )

        assert response.status_code == 200
        call_kwargs = mock_automation_repository.list_requests.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 20


class TestGetPendingRequests:
    """Tests for getting pending requests."""

    @pytest.mark.asyncio
    async def test_get_pending_requests(
        self,
        async_authenticated_client,
        override_automation_dependencies,
        mock_automation_repository,
    ):
        """Test retrieving pending requests."""
        pending = [
            MagicMock(
                id="req-001",
                type="feature",
                priority="high",
                to_dict=lambda: _make_complete_request_dict({
                    "id": "req-001",
                    "priority": "high",
                }),
            ),
        ]
        mock_automation_repository.get_pending_requests.return_value = pending

        response = await async_authenticated_client.get("/api/v1/automation/pending")

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1


class TestAutomationHealth:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_authenticated_client):
        """Test automation health endpoint."""
        response = await async_authenticated_client.get("/api/v1/automation/health")

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "healthy"
        assert "version" in data["data"]
