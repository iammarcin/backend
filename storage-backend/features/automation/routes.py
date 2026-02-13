"""HTTP routes for automation request operations."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.exceptions import NotFoundError
from core.pydantic_schemas import ApiResponse, ok as api_ok
from features.automation.dependencies import get_automation_repository
from features.automation.repositories.automation_repository import AutomationRepository
from features.automation.schemas import (
    AutomationQueueResponse,
    AutomationRequestListResponse,
    AutomationRequestResponse,
    CreateAutomationRequest,
    RequestPriority,
    RequestStatus,
    RequestType,
    UpdateAutomationRequest,
)
from features.automation.service import AutomationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/automation", tags=["automation"])


def _get_service(repository: AutomationRepository) -> AutomationService:
    """Create service with optional SQS queue."""
    # Try to create queue service, but don't fail if not configured
    queue_service = None
    try:
        from config.aws import AWS_SQS_AUTOMATION_QUEUE_URL
        if AWS_SQS_AUTOMATION_QUEUE_URL:
            from infrastructure.aws.queue import SqsQueueService
            queue_service = SqsQueueService(queue_url=AWS_SQS_AUTOMATION_QUEUE_URL)
    except Exception as exc:
        logger.debug(f"SQS queue not configured for automation: {exc}")

    return AutomationService(repository=repository, queue_service=queue_service)


@router.post("/requests", response_model=ApiResponse[AutomationQueueResponse])
async def create_automation_request(
    request: CreateAutomationRequest,
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """
    Submit a new automation request (feature, bug, research, or refactor).

    The request is stored in the database and optionally queued for processing
    by Claude Code on the development server.
    """
    service = _get_service(repository)
    result = await service.create_request(request)
    return api_ok("Automation request created", data=result)


@router.get("/requests/{request_id}", response_model=ApiResponse[AutomationRequestResponse])
async def get_automation_request(
    request_id: str,
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """Get details of a specific automation request."""
    service = _get_service(repository)
    try:
        result = await service.get_request(request_id)
        return api_ok("Automation request retrieved", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/requests/{request_id}", response_model=ApiResponse[AutomationRequestResponse])
async def update_automation_request(
    request_id: str,
    update: UpdateAutomationRequest,
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """
    Update an automation request.

    Typically called by Claude Code hooks to update status, milestones, or artifacts.
    """
    service = _get_service(repository)
    try:
        result = await service.update_request(request_id, update)
        return api_ok("Automation request updated", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/requests/{request_id}/status",
    response_model=ApiResponse[AutomationRequestResponse],
)
async def update_request_status(
    request_id: str,
    status_value: RequestStatus = Query(..., alias="status", description="New status"),
    phase: Optional[str] = Query(None, description="Current processing phase"),
    error: Optional[str] = Query(None, description="Error message if failed"),
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """
    Update request status (convenience endpoint for CLI scripts).

    Example: PATCH /requests/abc123/status?status=implementing&phase=M1
    """
    service = _get_service(repository)
    try:
        result = await service.update_status(
            request_id=request_id,
            status=status_value.value,
            phase=phase,
            error_message=error,
        )
        return api_ok("Status updated", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/requests", response_model=ApiResponse[AutomationRequestListResponse])
async def list_automation_requests(
    limit: int = Query(default=20, ge=1, le=100, description="Max results"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    status_filter: Optional[RequestStatus] = Query(
        None, alias="status", description="Filter by status"
    ),
    type_filter: Optional[RequestType] = Query(
        None, alias="type", description="Filter by type"
    ),
    priority_filter: Optional[RequestPriority] = Query(
        None, alias="priority", description="Filter by priority"
    ),
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """List automation requests with optional filters and pagination."""
    service = _get_service(repository)
    result = await service.list_requests(
        limit=limit,
        offset=offset,
        status=status_filter.value if status_filter else None,
        request_type=type_filter.value if type_filter else None,
        priority=priority_filter.value if priority_filter else None,
    )
    return api_ok("Automation requests retrieved", data=result)


@router.get("/pending", response_model=ApiResponse[list[AutomationRequestResponse]])
async def get_pending_requests(
    limit: int = Query(default=10, ge=1, le=50, description="Max results"),
    repository: AutomationRepository = Depends(get_automation_repository),
) -> dict:
    """
    Get pending requests ready for processing.

    Returns requests ordered by priority (highest first) and creation time (oldest first).
    Used by the polling script on the development server.
    """
    service = _get_service(repository)
    result = await service.get_pending_requests(limit=limit)
    return api_ok("Pending requests retrieved", data=result)


@router.get("/health")
async def automation_health() -> dict:
    """Health check for automation endpoints."""
    return api_ok(
        "Automation API healthy",
        data={
            "status": "healthy",
            "version": "1.0.0",
        },
    )


__all__ = ["router"]
