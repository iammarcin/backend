"""Session bookkeeping utilities for chat WebSocket workflows.

This module provides a lightweight dataclass used across the chat WebSocket
stack to keep consistent metadata about each connected client. Centralising
the structure helps downstream helpers update activity timestamps and
track which workflow is currently running without duplicating logic.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def utcnow() -> datetime:
    """Return a timezone-aware timestamp for session bookkeeping."""

    return datetime.now(timezone.utc)


@dataclass
class WorkflowSession:
    """Track metadata for a persistent WebSocket workflow session."""

    customer_id: int
    session_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utcnow)
    last_activity: datetime = field(default_factory=utcnow)
    context: Dict[str, Any] = field(default_factory=dict)
    active_workflow: Optional[str] = None

    def touch(self) -> None:
        """Record activity on the session."""

        self.last_activity = utcnow()

    def mark_workflow(self, workflow: Optional[str]) -> None:
        """Store the workflow identifier and bump the activity timestamp."""

        self.active_workflow = workflow
        self.touch()

    def is_expired(self, timeout_seconds: int) -> bool:
        """Return ``True`` when the session exceeded the idle timeout."""

        return (utcnow() - self.last_activity).total_seconds() > timeout_seconds
