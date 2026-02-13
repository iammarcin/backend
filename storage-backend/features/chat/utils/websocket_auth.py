"""Authentication helpers for chat WebSocket connections."""

from __future__ import annotations

import logging

from fastapi import WebSocket

from core.auth import AuthContext, AuthenticationError, authenticate_bearer_token

logger = logging.getLogger(__name__)

UNAUTHORIZED_CLOSE_CODE = 4401


async def authenticate_websocket(websocket: WebSocket) -> AuthContext:
    """Validate the websocket bearer token and return its auth context."""

    scope = getattr(websocket, "scope", {})
    client = scope.get("client")
    path = scope.get("path", websocket.url.path if websocket.url else "/chat/ws")

    authorization = websocket.headers.get("authorization")
    token = websocket.query_params.get("token")

    try:
        context = authenticate_bearer_token(
            authorization=authorization,
            query_token=token,
        )
    except AuthenticationError as exc:
        logger.warning(
            "WebSocket authentication failed (path=%s, client=%s, reason=%s)",
            path,
            client,
            exc.reason,
        )
        await websocket.close(code=UNAUTHORIZED_CLOSE_CODE, reason="Unauthorized")
        raise

    return context
