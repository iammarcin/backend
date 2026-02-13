"""Pydantic request schemas for automation endpoints."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RequestType(str, Enum):
    """Type of automation request."""

    FEATURE = "feature"
    BUG = "bug"
    RESEARCH = "research"
    REFACTOR = "refactor"


class RequestPriority(str, Enum):
    """Priority level for automation request."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RequestStatus(str, Enum):
    """Status of automation request."""

    PENDING = "pending"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    DEPLOYING = "deploying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class AttachmentItem(BaseModel):
    """Attachment for automation request."""

    type: str = Field(..., description="Type of attachment (screenshot, log, file)")
    url: Optional[str] = Field(None, description="URL if externally hosted")
    content: Optional[str] = Field(None, description="Content if inline")
    filename: Optional[str] = Field(None, description="Original filename")


class CreateAutomationRequest(BaseModel):
    """Request payload for creating a new automation request."""

    type: RequestType = Field(..., description="Type of request")
    title: str = Field(..., min_length=3, max_length=255, description="Brief title")
    description: str = Field(..., min_length=10, description="Detailed description")
    priority: RequestPriority = Field(
        default=RequestPriority.MEDIUM, description="Priority level"
    )
    attachments: Optional[list[AttachmentItem]] = Field(
        default=None, description="Optional attachments"
    )

    model_config = {"json_schema_extra": {
        "example": {
            "type": "feature",
            "title": "Add rate limiting to public endpoints",
            "description": "Implement rate limiting using Redis for all /api/v1/public/* endpoints. Should limit to 100 requests per minute per IP.",
            "priority": "medium",
            "attachments": [
                {"type": "screenshot", "url": "https://s3.../screenshot.png"}
            ],
        }
    }}


class UpdateAutomationRequest(BaseModel):
    """Request payload for updating an automation request."""

    status: Optional[RequestStatus] = Field(None, description="New status")
    current_phase: Optional[str] = Field(None, description="Current processing phase")
    session_id: Optional[str] = Field(None, description="Claude Code session ID")
    milestones: Optional[list[dict[str, Any]]] = Field(
        None, description="Implementation milestones"
    )
    plan_document: Optional[str] = Field(None, description="Generated plan document")
    pr_url: Optional[str] = Field(None, description="Pull request URL")
    test_results: Optional[dict[str, Any]] = Field(None, description="Test execution results")
    deployment_log: Optional[str] = Field(None, description="Deployment log output")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class ListAutomationRequestsParams(BaseModel):
    """Query parameters for listing automation requests."""

    limit: int = Field(default=20, ge=1, le=100, description="Max results to return")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    status: Optional[RequestStatus] = Field(None, description="Filter by status")
    type: Optional[RequestType] = Field(None, description="Filter by type")
    priority: Optional[RequestPriority] = Field(None, description="Filter by priority")


__all__ = [
    "RequestType",
    "RequestPriority",
    "RequestStatus",
    "AttachmentItem",
    "CreateAutomationRequest",
    "UpdateAutomationRequest",
    "ListAutomationRequestsParams",
]
