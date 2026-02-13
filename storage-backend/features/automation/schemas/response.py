"""Pydantic response schemas for automation endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .request import RequestPriority, RequestStatus, RequestType


class MilestoneResponse(BaseModel):
    """Milestone in an automation request."""

    id: str = Field(..., description="Milestone identifier (M1, M2, etc.)")
    title: str = Field(..., description="Milestone title")
    type: str = Field(..., description="Milestone type (database, config, feature, etc.)")
    status: str = Field(..., description="Milestone status")
    agent: Optional[str] = Field(None, description="Agent assigned to milestone")
    dependencies: Optional[list[str]] = Field(None, description="Dependent milestone IDs")


class AutomationRequestResponse(BaseModel):
    """Response model for a single automation request."""

    id: str = Field(..., description="Request ID")
    type: RequestType = Field(..., description="Request type")
    status: RequestStatus = Field(..., description="Current status")
    priority: RequestPriority = Field(..., description="Priority level")
    title: str = Field(..., description="Request title")
    description: str = Field(..., description="Request description")
    attachments: Optional[list[dict[str, Any]]] = Field(None, description="Attachments")
    session_id: Optional[str] = Field(None, description="Claude Code session ID")
    current_phase: Optional[str] = Field(None, description="Current processing phase")
    milestones: Optional[list[MilestoneResponse]] = Field(None, description="Milestones")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    last_update: Optional[datetime] = Field(None, description="Last update time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    plan_document: Optional[str] = Field(None, description="Generated plan")
    pr_url: Optional[str] = Field(None, description="Pull request URL")
    test_results: Optional[dict[str, Any]] = Field(None, description="Test results")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last modification timestamp")


class AutomationRequestListResponse(BaseModel):
    """Response model for listing automation requests."""

    items: list[AutomationRequestResponse] = Field(..., description="List of requests")
    total: int = Field(..., description="Total number of matching requests")
    limit: int = Field(..., description="Limit used for query")
    offset: int = Field(..., description="Offset used for query")


class AutomationQueueResponse(BaseModel):
    """Response model for SQS queue submission."""

    request_id: str = Field(..., description="Created request ID")
    queue_message_id: Optional[str] = Field(None, description="SQS message ID")
    status: str = Field(default="pending", description="Initial status")


__all__ = [
    "MilestoneResponse",
    "AutomationRequestResponse",
    "AutomationRequestListResponse",
    "AutomationQueueResponse",
]
