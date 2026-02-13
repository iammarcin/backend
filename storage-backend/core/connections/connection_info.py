"""Connection info dataclass for proactive WebSocket connections.

Tracks metadata about active WebSocket connections for push notifications.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import WebSocket

# Stable per-process identifier for debugging multi-instance deployments
_SERVER_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


@dataclass
class ConnectionInfo:
    """Metadata about an active WebSocket connection."""

    websocket: WebSocket
    user_id: int
    session_id: str
    client_id: str | None = None  # e.g., "kotlin-xxx" or "react-xxx"
    connected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_ping: datetime = field(default_factory=lambda: datetime.now(UTC))


def get_server_id() -> str:
    """Stable per-process identifier for debugging."""
    return _SERVER_ID


__all__ = ["ConnectionInfo", "get_server_id"]
