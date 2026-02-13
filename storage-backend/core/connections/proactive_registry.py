"""In-memory registry for active proactive WebSocket connections.

Tracks which users have active WebSocket connections for push notifications.
When an agent notification arrives, we check this registry to push in real-time.

Supports multiple connections per user (e.g., React and Kotlin clients simultaneously).

This registry is used by the unified /chat/ws?mode=proactive endpoint.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from .connection_info import ConnectionInfo, get_server_id

logger = logging.getLogger(__name__)


class ProactiveConnectionRegistry:
    """Thread-safe registry of active proactive WebSocket connections.

    Design decisions:
    - Multiple connections per user supported (React + Kotlin can connect simultaneously)
    - Notifications pushed to ALL connected clients for a user
    - Optimized for lookup by user_id (primary use case: push on notification)
    """

    def __init__(self) -> None:
        self._connections: Dict[int, List[ConnectionInfo]] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        user_id: int,
        session_id: str,
        websocket: WebSocket,
        client_id: str | None = None,
    ) -> Optional[WebSocket]:
        """Register a new WebSocket connection for a user.

        Multiple connections per user are supported (e.g., React + Kotlin).
        When client_id is provided, only replaces connections with the SAME
        session_id AND client_id (handles app restarts while allowing multiple
        clients to connect to the same session).

        When client_id is None (legacy), replaces all connections for the session.
        Returns None.
        """
        async with self._lock:
            if user_id not in self._connections:
                self._connections[user_id] = []

            # Close and remove old connections for the SAME session+client
            # This handles app restarts where old WebSocket lingers
            if client_id:
                # New behavior: only replace connections from same client
                old_conns = [
                    conn
                    for conn in self._connections[user_id]
                    if conn.session_id == session_id and conn.client_id == client_id
                ]
            else:
                # Legacy behavior (no client_id): replace all for this session
                old_conns = [
                    conn
                    for conn in self._connections[user_id]
                    if conn.session_id == session_id
                ]

            for old_conn in old_conns:
                logger.info(
                    "Replacing old connection for user=%s session=%s client=%s",
                    user_id,
                    session_id[:8] if session_id else "none",
                    (old_conn.client_id or "none")[:12],
                )
                try:
                    await old_conn.websocket.close(
                        code=1000, reason="Replaced by new connection"
                    )
                except Exception:
                    pass  # Already closed

            # Remove closed connections
            if client_id:
                self._connections[user_id] = [
                    conn
                    for conn in self._connections[user_id]
                    if not (conn.session_id == session_id and conn.client_id == client_id)
                ]
            else:
                self._connections[user_id] = [
                    conn
                    for conn in self._connections[user_id]
                    if conn.session_id != session_id
                ]

            new_conn = ConnectionInfo(
                websocket=websocket,
                user_id=user_id,
                session_id=session_id,
                client_id=client_id,
            )
            self._connections[user_id].append(new_conn)

            conn_count = len(self._connections[user_id])
            logger.info(
                "Registered proactive connection: user=%s, session=%s, client=%s (total: %d)",
                user_id,
                session_id[:8] if session_id else "none",
                (client_id or "none")[:12],
                conn_count,
            )
            return None

    async def unregister(
        self, user_id: int, websocket: Optional[WebSocket] = None
    ) -> bool:
        """Remove a user's WebSocket connection.

        Args:
            user_id: The user ID to unregister
            websocket: The specific websocket to unregister. If None, removes all.

        Returns True if a connection was removed.
        """
        async with self._lock:
            if user_id not in self._connections:
                return False

            if websocket is None:
                del self._connections[user_id]
                logger.info("Unregistered all proactive connections for user %s", user_id)
                return True

            original_count = len(self._connections[user_id])
            self._connections[user_id] = [
                conn
                for conn in self._connections[user_id]
                if conn.websocket is not websocket
            ]
            removed = len(self._connections[user_id]) < original_count

            if not self._connections[user_id]:
                del self._connections[user_id]
                logger.info("Unregistered last proactive connection for user %s", user_id)
            elif removed:
                logger.info(
                    "Unregistered proactive connection for user %s (remaining: %d)",
                    user_id,
                    len(self._connections[user_id]),
                )

            return removed

    async def get_connection(self, user_id: int) -> Optional[ConnectionInfo]:
        """Get first connection info for a user (for backwards compatibility)."""
        conns = self._connections.get(user_id, [])
        return conns[0] if conns else None

    async def get_connections(self, user_id: int) -> List[ConnectionInfo]:
        """Get all connections for a user."""
        return self._connections.get(user_id, [])

    async def get_websocket(self, user_id: int) -> Optional[WebSocket]:
        """Get first WebSocket for a user if connected (for backwards compatibility)."""
        conns = self._connections.get(user_id, [])
        return conns[0].websocket if conns else None

    async def get_websockets(self, user_id: int) -> List[WebSocket]:
        """Get all WebSockets for a user."""
        conns = self._connections.get(user_id, [])
        return [conn.websocket for conn in conns]

    async def push_to_user(
        self, user_id: int, message: Dict[str, Any], session_scoped: bool = True
    ) -> bool:
        """Push a message to ALL of a user's WebSockets.

        Args:
            user_id: Target user ID
            message: Message dict to push
            session_scoped: If True (default), only push to connections matching
                the message's session_id. If False, push to ALL user connections
                regardless of session (used for cross-session notifications).

        Returns True if message was sent to at least one connection.
        """
        conns = self._connections.get(user_id, [])
        if not conns:
            return False

        if session_scoped:
            target_session_id = message.get("session_id") or message.get("data", {}).get(
                "session_id"
            )
            if target_session_id:
                conns = [
                    conn for conn in conns if conn.session_id == target_session_id
                ]
                if not conns:
                    # No log: this is expected when streaming to a session with no
                    # WebSocket connected (session scoping is working as designed).
                    # Check register/unregister logs for connection state debugging.
                    return False

        success_count = 0
        failed_websockets = []

        event_type = message.get("type", "unknown")

        for conn in conns:
            try:
                await conn.websocket.send_json(message)
                success_count += 1
                # Log stream_end specifically to debug completion signal issues
                if event_type == "stream_end":
                    logger.info(
                        "Pushed stream_end to user %s (session=%s, client=%s)",
                        user_id,
                        conn.session_id[:8] if conn.session_id else "none",
                        conn.client_id[:12] if conn.client_id else "none",
                    )
            except Exception as exc:
                logger.warning("Failed to push to user %s connection: %s", user_id, exc)
                failed_websockets.append(conn.websocket)

        for ws in failed_websockets:
            await self.unregister(user_id, ws)

        return success_count > 0

    async def update_last_ping(
        self, user_id: int, websocket: Optional[WebSocket] = None
    ) -> None:
        """Update the last ping timestamp for keepalive tracking."""
        conns = self._connections.get(user_id, [])
        for conn in conns:
            if websocket is None or conn.websocket is websocket:
                conn.last_ping = datetime.now(UTC)

    @property
    def active_count(self) -> int:
        """Total number of active connections (across all users)."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def active_user_count(self) -> int:
        """Number of users with active connections."""
        return len(self._connections)

    def get_all_user_ids(self) -> list[int]:
        """Get list of all connected user IDs."""
        return list(self._connections.keys())


# Global singleton instance
_registry: Optional[ProactiveConnectionRegistry] = None


def get_proactive_registry() -> ProactiveConnectionRegistry:
    """Get the global proactive connection registry singleton."""
    global _registry
    if _registry is None:
        _registry = ProactiveConnectionRegistry()
        logger.info("Proactive connection registry initialized")
    return _registry


__all__ = [
    "ConnectionInfo",
    "ProactiveConnectionRegistry",
    "get_proactive_registry",
    "get_server_id",
]
