"""Repository for automation request CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from features.automation.db_models import AutomationRequest


class AutomationRepository:
    """CRUD operations for automation requests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        request_id: str,
        request_type: str,
        title: str,
        description: str,
        priority: str = "medium",
        attachments: Optional[list[dict[str, Any]]] = None,
    ) -> AutomationRequest:
        """Create a new automation request."""
        request = AutomationRequest(
            id=request_id,
            type=request_type,
            title=title,
            description=description,
            priority=priority,
            attachments=attachments,
            status="pending",
        )
        self._session.add(request)
        await self._session.flush()
        return request

    async def get_by_id(self, request_id: str) -> Optional[AutomationRequest]:
        """Retrieve automation request by ID."""
        result = await self._session.execute(
            select(AutomationRequest).where(AutomationRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        request_id: str,
        **updates: Any,
    ) -> Optional[AutomationRequest]:
        """Update an automation request with provided fields."""
        request = await self.get_by_id(request_id)
        if not request:
            return None

        # Track update timestamp
        updates["last_update"] = datetime.now(UTC)

        for field, value in updates.items():
            if hasattr(request, field) and value is not None:
                setattr(request, field, value)

        await self._session.flush()
        return request

    async def update_status(
        self,
        request_id: str,
        status: str,
        phase: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[AutomationRequest]:
        """Update request status with optional phase and error."""
        updates: dict[str, Any] = {"status": status}

        if phase:
            updates["current_phase"] = phase

        if error_message:
            updates["error_message"] = error_message

        # Set timestamps based on status
        now = datetime.now(UTC)
        if status == "implementing" and not updates.get("started_at"):
            updates["started_at"] = now
        elif status in ("completed", "failed"):
            updates["completed_at"] = now

        return await self.update(request_id, **updates)

    async def list_requests(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        request_type: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> tuple[list[AutomationRequest], int]:
        """List automation requests with filters and pagination."""
        query = select(AutomationRequest)

        if status:
            query = query.where(AutomationRequest.status == status)
        if request_type:
            query = query.where(AutomationRequest.type == request_type)
        if priority:
            query = query.where(AutomationRequest.priority == priority)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = query.order_by(AutomationRequest.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        requests = list(result.scalars().all())

        return requests, total

    async def get_pending_requests(self, limit: int = 10) -> list[AutomationRequest]:
        """Get pending requests for processing (oldest first)."""
        result = await self._session.execute(
            select(AutomationRequest)
            .where(AutomationRequest.status == "pending")
            .order_by(
                AutomationRequest.priority.desc(),
                AutomationRequest.created_at.asc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def increment_retry(self, request_id: str) -> Optional[AutomationRequest]:
        """Increment retry count for a request."""
        request = await self.get_by_id(request_id)
        if not request:
            return None

        request.retry_count = (request.retry_count or 0) + 1
        request.last_update = datetime.now(UTC)
        await self._session.flush()
        return request


__all__ = ["AutomationRepository"]
