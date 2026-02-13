"""Tests for automation service business logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from core.exceptions import NotFoundError
from features.automation.schemas import (
    CreateAutomationRequest,
    RequestPriority,
    RequestStatus,
    RequestType,
    UpdateAutomationRequest,
)
from features.automation.service import AutomationService
from features.automation.db_models import AutomationRequest


@pytest.fixture
def mock_repository():
    """Mock automation repository."""
    return AsyncMock()


@pytest.fixture
def mock_queue_service():
    """Mock SQS queue service."""
    service = AsyncMock()
    service.enqueue_timestamped_payload.return_value = MagicMock(message_id="msg-123")
    return service


@pytest.fixture
def automation_service(mock_repository, mock_queue_service):
    """Create automation service with mocks."""
    return AutomationService(repository=mock_repository, queue_service=mock_queue_service)


@pytest.fixture
def automation_service_no_queue(mock_repository):
    """Create automation service without queue service."""
    return AutomationService(repository=mock_repository, queue_service=None)


class TestCreateAutomationRequest:
    """Tests for creating automation requests."""

    @pytest.mark.asyncio
    async def test_create_feature_request_success(
        self,
        automation_service,
        mock_repository,
        mock_queue_service,
    ):
        """Test successful feature request creation."""
        mock_repository.create.return_value = MagicMock(
            id="req-123",
            type="feature",
            status="pending",
            title="Test Feature",
            to_dict=lambda: {"id": "req-123", "type": "feature", "status": "pending"},
        )

        request = CreateAutomationRequest(
            type=RequestType.FEATURE,
            title="Test Feature",
            description="Test feature description",
            priority=RequestPriority.MEDIUM,
        )

        result = await automation_service.create_request(request)

        assert result["request_id"] is not None
        assert result["status"] == "pending"
        mock_repository.create.assert_called_once()
        mock_queue_service.enqueue_timestamped_payload.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bug_report(
        self,
        automation_service,
        mock_repository,
        mock_queue_service,
    ):
        """Test bug report creation."""
        mock_repository.create.return_value = MagicMock(
            id="bug-123",
            type="bug",
            to_dict=lambda: {"id": "bug-123", "type": "bug"},
        )

        request = CreateAutomationRequest(
            type=RequestType.BUG,
            title="WebSocket error",
            description="Connection drops unexpectedly",
            priority=RequestPriority.HIGH,
        )

        result = await automation_service.create_request(request)

        assert result["request_id"] is not None
        call_args = mock_queue_service.enqueue_timestamped_payload.call_args
        assert call_args[0][0]["type"] == "bug"

    @pytest.mark.asyncio
    async def test_create_research_task(
        self,
        automation_service,
        mock_repository,
    ):
        """Test research task creation."""
        mock_repository.create.return_value = MagicMock(
            id="research-123",
            type="research",
            to_dict=lambda: {"id": "research-123", "type": "research"},
        )

        request = CreateAutomationRequest(
            type=RequestType.RESEARCH,
            title="Investigate caching",
            description="Research caching strategies",
            priority=RequestPriority.LOW,
        )

        result = await automation_service.create_request(request)

        assert result["request_id"] is not None

    @pytest.mark.asyncio
    async def test_create_request_without_queue_service(
        self,
        automation_service_no_queue,
        mock_repository,
    ):
        """Test creation when queue service is not available."""
        mock_repository.create.return_value = MagicMock(
            id="req-123",
            to_dict=lambda: {"id": "req-123"},
        )

        request = CreateAutomationRequest(
            type=RequestType.FEATURE,
            title="Test",
            description="Test description",
        )

        result = await automation_service_no_queue.create_request(request)

        # Still works, just no queue message
        assert result["request_id"] is not None
        assert result["queue_message_id"] is None


class TestGetAutomationRequest:
    """Tests for retrieving automation requests."""

    @pytest.mark.asyncio
    async def test_get_request_success(self, automation_service, mock_repository):
        """Test retrieving existing request."""
        mock_repository.get_by_id.return_value = MagicMock(
            id="req-123",
            type="feature",
            status="pending",
            to_dict=lambda: {"id": "req-123", "type": "feature", "status": "pending"},
        )

        result = await automation_service.get_request("req-123")

        assert result["id"] == "req-123"
        mock_repository.get_by_id.assert_called_once_with("req-123")

    @pytest.mark.asyncio
    async def test_get_request_not_found(self, automation_service, mock_repository):
        """Test 404 when request not found."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await automation_service.get_request("nonexistent")


class TestUpdateAutomationRequest:
    """Tests for updating automation requests."""

    @pytest.mark.asyncio
    async def test_update_request_status(
        self,
        automation_service,
        mock_repository,
    ):
        """Test updating request status."""
        mock_repository.update.return_value = MagicMock(
            id="req-123",
            status="implementing",
            to_dict=lambda: {"id": "req-123", "status": "implementing"},
        )

        update = UpdateAutomationRequest(status=RequestStatus.IMPLEMENTING)
        result = await automation_service.update_request("req-123", update)

        assert result["status"] == "implementing"
        mock_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_with_phase(
        self,
        automation_service,
        mock_repository,
    ):
        """Test updating status with phase info."""
        mock_repository.update_status.return_value = MagicMock(
            id="req-123",
            status="implementing",
            current_phase="M1",
            to_dict=lambda: {
                "id": "req-123",
                "status": "implementing",
                "current_phase": "M1",
            },
        )

        result = await automation_service.update_status(
            "req-123",
            status="implementing",
            phase="M1",
        )

        assert result["current_phase"] == "M1"

    @pytest.mark.asyncio
    async def test_update_request_not_found(
        self,
        automation_service,
        mock_repository,
    ):
        """Test error when updating non-existent request."""
        mock_repository.update.return_value = None

        update = UpdateAutomationRequest(status=RequestStatus.COMPLETED)

        with pytest.raises(NotFoundError):
            await automation_service.update_request("nonexistent", update)


class TestListAutomationRequests:
    """Tests for listing automation requests."""

    @pytest.mark.asyncio
    async def test_list_requests_empty(
        self,
        automation_service,
        mock_repository,
    ):
        """Test listing with no requests."""
        mock_repository.list_requests.return_value = ([], 0)

        result = await automation_service.list_requests()

        assert result["items"] == []
        assert result["total"] == 0
        assert result["limit"] == 20
        assert result["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_requests_with_results(
        self,
        automation_service,
        mock_repository,
    ):
        """Test listing with requests."""
        requests_list = [
            MagicMock(
                id="req-001",
                to_dict=lambda: {"id": "req-001"},
            ),
            MagicMock(
                id="req-002",
                to_dict=lambda: {"id": "req-002"},
            ),
        ]
        mock_repository.list_requests.return_value = (requests_list, 2)

        result = await automation_service.list_requests(limit=10)

        assert len(result["items"]) == 2
        assert result["total"] == 2
        assert result["limit"] == 10

    @pytest.mark.asyncio
    async def test_list_requests_with_status_filter(
        self,
        automation_service,
        mock_repository,
    ):
        """Test filtering by status."""
        mock_repository.list_requests.return_value = ([], 0)

        await automation_service.list_requests(status="completed")

        call_kwargs = mock_repository.list_requests.call_args[1]
        assert call_kwargs["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_requests_with_type_filter(
        self,
        automation_service,
        mock_repository,
    ):
        """Test filtering by type."""
        mock_repository.list_requests.return_value = ([], 0)

        await automation_service.list_requests(request_type="feature")

        call_kwargs = mock_repository.list_requests.call_args[1]
        assert call_kwargs["request_type"] == "feature"

    @pytest.mark.asyncio
    async def test_list_requests_with_priority_filter(
        self,
        automation_service,
        mock_repository,
    ):
        """Test filtering by priority."""
        mock_repository.list_requests.return_value = ([], 0)

        await automation_service.list_requests(priority="high")

        call_kwargs = mock_repository.list_requests.call_args[1]
        assert call_kwargs["priority"] == "high"

    @pytest.mark.asyncio
    async def test_list_requests_pagination(
        self,
        automation_service,
        mock_repository,
    ):
        """Test pagination."""
        mock_repository.list_requests.return_value = ([], 100)

        result = await automation_service.list_requests(limit=10, offset=20)

        call_kwargs = mock_repository.list_requests.call_args[1]
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 20
        assert result["offset"] == 20


class TestGetPendingRequests:
    """Tests for getting pending requests."""

    @pytest.mark.asyncio
    async def test_get_pending_requests(
        self,
        automation_service,
        mock_repository,
    ):
        """Test retrieving pending requests."""
        pending = [
            MagicMock(
                id="req-001",
                type="feature",
                priority="high",
                to_dict=lambda: {"id": "req-001", "type": "feature"},
            ),
            MagicMock(
                id="req-002",
                type="bug",
                priority="high",
                to_dict=lambda: {"id": "req-002", "type": "bug"},
            ),
        ]
        mock_repository.get_pending_requests.return_value = pending

        result = await automation_service.get_pending_requests(limit=10)

        assert len(result) == 2
        mock_repository.get_pending_requests.assert_called_once_with(limit=10)

    @pytest.mark.asyncio
    async def test_get_pending_requests_empty(
        self,
        automation_service,
        mock_repository,
    ):
        """Test when no pending requests."""
        mock_repository.get_pending_requests.return_value = []

        result = await automation_service.get_pending_requests()

        assert result == []
