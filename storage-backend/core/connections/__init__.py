"""Connection management for persistent WebSocket connections.

This module provides infrastructure for managing persistent WebSocket connections
that need server-initiated push notifications (proactive mode).
"""

from core.connections.connection_info import ConnectionInfo, get_server_id
from core.connections.proactive_registry import (
    ProactiveConnectionRegistry,
    get_proactive_registry,
)

__all__ = [
    "ConnectionInfo",
    "ProactiveConnectionRegistry",
    "get_proactive_registry",
    "get_server_id",
]
