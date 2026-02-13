"""Database models for automation request tracking."""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.sql import func

from infrastructure.db.base import Base


class AutomationRequest(Base):
    """Automation request tracking record for Claude Code workflows."""

    __tablename__ = "automation_requests"

    id = Column(String(36), primary_key=True)
    type = Column(
        Enum("feature", "bug", "research", "refactor", name="automation_request_type"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(
            "pending",
            "planning",
            "implementing",
            "testing",
            "reviewing",
            "deploying",
            "completed",
            "failed",
            "blocked",
            name="automation_request_status",
        ),
        nullable=False,
        default="pending",
        index=True,
    )
    priority = Column(
        Enum("low", "medium", "high", "critical", name="automation_request_priority"),
        nullable=False,
        default="medium",
    )

    # Request content
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    attachments = Column(JSON, nullable=True)

    # Processing metadata
    session_id = Column(String(64), nullable=True)
    current_phase = Column(String(50), nullable=True)
    milestones = Column(JSON, nullable=True)

    # Tracking timestamps
    started_at = Column(DateTime(timezone=True), nullable=True)
    last_update = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Artifacts
    plan_document = Column(Text, nullable=True)
    pr_url = Column(String(255), nullable=True)
    test_results = Column(JSON, nullable=True)
    deployment_log = Column(Text, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_automation_status_type", "status", "type"),
        Index("idx_automation_priority_status", "priority", "status"),
        Index("idx_automation_created", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AutomationRequest(id='{self.id}', type='{self.type}', "
            f"status='{self.status}', title='{self.title[:30]}...')>"
        )

    def to_dict(self) -> dict:
        """Convert model to dictionary for API responses."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "attachments": self.attachments,
            "session_id": self.session_id,
            "current_phase": self.current_phase,
            "milestones": self.milestones,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "plan_document": self.plan_document,
            "pr_url": self.pr_url,
            "test_results": self.test_results,
            "deployment_log": self.deployment_log,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["AutomationRequest"]
