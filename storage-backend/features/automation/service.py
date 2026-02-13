"""Business logic service for automation requests."""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import uuid4

from core.exceptions import NotFoundError, ServiceError
from features.automation.repositories.automation_repository import AutomationRepository
from features.automation.schemas import (
    CreateAutomationRequest,
    RequestStatus,
    UpdateAutomationRequest,
)
from infrastructure.aws.queue import SqsQueueService

logger = logging.getLogger(__name__)


class AutomationService:
    """Service for managing automation requests."""

    def __init__(
        self,
        repository: AutomationRepository,
        queue_service: Optional[SqsQueueService] = None,
    ) -> None:
        self._repository = repository
        self._queue_service = queue_service

    async def create_request(
        self,
        request: CreateAutomationRequest,
    ) -> dict[str, Any]:
        """Create a new automation request and optionally queue for processing."""
        request_id = str(uuid4())

        # Create database record
        db_request = await self._repository.create(
            request_id=request_id,
            request_type=request.type.value,
            title=request.title,
            description=request.description,
            priority=request.priority.value,
            attachments=[a.model_dump() for a in request.attachments]
            if request.attachments
            else None,
        )

        result = {
            "request_id": request_id,
            "status": "pending",
            "queue_message_id": None,
        }

        # Queue for processing if queue service available
        if self._queue_service:
            try:
                queue_result = await self._queue_service.enqueue_timestamped_payload(
                    {
                        "request_id": request_id,
                        "type": request.type.value,
                        "priority": request.priority.value,
                    }
                )
                result["queue_message_id"] = queue_result.message_id
                logger.info(
                    "Automation request queued",
                    extra={"request_id": request_id, "message_id": queue_result.message_id},
                )
            except ServiceError as exc:
                logger.warning(
                    "Failed to queue automation request, will process manually",
                    extra={"request_id": request_id, "error": str(exc)},
                )

        logger.info(
            "Automation request created",
            extra={"request_id": request_id, "type": request.type.value},
        )

        return result

    async def get_request(self, request_id: str) -> dict[str, Any]:
        """Get automation request by ID."""
        request = await self._repository.get_by_id(request_id)
        if not request:
            raise NotFoundError(f"Automation request {request_id} not found")
        return request.to_dict()

    async def update_request(
        self,
        request_id: str,
        update: UpdateAutomationRequest,
    ) -> dict[str, Any]:
        """Update an automation request."""
        update_data = update.model_dump(exclude_none=True)

        # Convert enum to string if present
        if "status" in update_data and isinstance(update_data["status"], RequestStatus):
            update_data["status"] = update_data["status"].value

        request = await self._repository.update(request_id, **update_data)
        if not request:
            raise NotFoundError(f"Automation request {request_id} not found")

        logger.info(
            "Automation request updated",
            extra={"request_id": request_id, "updates": list(update_data.keys())},
        )

        return request.to_dict()

    async def update_status(
        self,
        request_id: str,
        status: str,
        phase: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update request status with optional phase and error."""
        request = await self._repository.update_status(
            request_id=request_id,
            status=status,
            phase=phase,
            error_message=error_message,
        )
        if not request:
            raise NotFoundError(f"Automation request {request_id} not found")

        logger.info(
            "Automation request status updated",
            extra={"request_id": request_id, "status": status, "phase": phase},
        )

        return request.to_dict()

    async def list_requests(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        request_type: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> dict[str, Any]:
        """List automation requests with filters."""
        requests, total = await self._repository.list_requests(
            limit=limit,
            offset=offset,
            status=status,
            request_type=request_type,
            priority=priority,
        )

        return {
            "items": [r.to_dict() for r in requests],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_pending_requests(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get pending requests ready for processing."""
        requests = await self._repository.get_pending_requests(limit=limit)
        return [r.to_dict() for r in requests]


__all__ = ["AutomationService"]
