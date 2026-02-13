"""HTTP and WebSocket routes for proactive agent operations.

M4 Cleanup Note: Legacy HTTP streaming endpoints (/stream, /thinking, /chart,
/deep-research, /session/{id}/claude-session) have been removed. The Python
poller now uses WebSocket streaming via /ws/poller-stream, and marker handling
is done internally by the backend.

Heartbeat Cleanup Note: /heartbeat/invoke endpoint has been removed. Heartbeat
now streams via SDK daemon + WebSocket (same pattern as poller) to avoid
Docker container → host networking issues.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from config.proactive_agent import (
    API_VERSION,
    DEFAULT_CHARACTER_NAME,
    INTERNAL_API_KEY,
)
from core.exceptions import NotFoundError
from core.pydantic_schemas import ApiResponse, ok as api_ok
from features.proactive_agent.dependencies import get_proactive_agent_repository
from features.proactive_agent.poller_stream import poller_stream_router
from features.proactive_agent.repositories import ProactiveAgentRepository
from features.proactive_agent.schemas import (
    AgentNotificationRequest,
    MessageListResponse,
)
from features.proactive_agent.schemas.response import SessionResponse
from features.proactive_agent.service import ProactiveAgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/proactive-agent", tags=["proactive-agent"])

# Include poller stream WebSocket router
router.include_router(poller_stream_router, prefix="/ws")


def _get_service(repository: ProactiveAgentRepository) -> ProactiveAgentService:
    """Create service with optional SQS queue."""
    queue_service = None
    try:
        from config.aws import AWS_SQS_PROACTIVE_AGENT_QUEUE_URL

        if AWS_SQS_PROACTIVE_AGENT_QUEUE_URL:
            from infrastructure.aws.queue import SqsQueueService

            queue_service = SqsQueueService(queue_url=AWS_SQS_PROACTIVE_AGENT_QUEUE_URL)
    except Exception as exc:
        logger.debug(f"SQS queue not configured for proactive agent: {exc}")

    return ProactiveAgentService(repository=repository, queue_service=queue_service)


def _verify_internal_api_key(x_internal_api_key: Optional[str] = Header(None)) -> None:
    """Verify internal API key for server-to-server endpoints."""
    if x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal API key",
        )


@router.get("/messages/{session_id}", response_model=ApiResponse[MessageListResponse])
async def get_messages(
    session_id: str,
    user_id: int = Query(..., description="User ID"),  # TODO: Replace with JWT auth
    since: Optional[datetime] = Query(None, description="Get messages after this timestamp"),
    limit: int = Query(default=50, ge=1, le=100, description="Max messages to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    repository: ProactiveAgentRepository = Depends(get_proactive_agent_repository),
) -> dict:
    """Get messages from a proactive agent session."""
    service = _get_service(repository)
    try:
        result = await service.get_messages(
            session_id=session_id,
            user_id=user_id,
            since=since,
            limit=limit,
            offset=offset,
        )
        return api_ok("Messages retrieved", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/messages/{session_id}/poll", response_model=ApiResponse[list[dict]])
async def poll_new_messages(
    session_id: str,
    user_id: int = Query(..., description="User ID"),
    since: Optional[datetime] = Query(None, description="Get messages after this timestamp"),
    repository: ProactiveAgentRepository = Depends(get_proactive_agent_repository),
) -> dict:
    """
    Poll for new agent messages (lightweight endpoint for mobile polling).

    Returns only new messages from the agent since the given timestamp.
    """
    service = _get_service(repository)
    try:
        messages = await service.get_new_messages(
            session_id=session_id,
            user_id=user_id,
            since=since,
        )
        return api_ok("New messages retrieved", data=messages)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/session", response_model=ApiResponse[SessionResponse])
async def get_or_create_session(
    user_id: int = Query(..., description="User ID"),
    session_id: Optional[str] = Query(None, description="Existing session ID"),
    ai_character_name: str = Query(default=DEFAULT_CHARACTER_NAME, description="AI character name (sherlock, bugsy)"),
    repository: ProactiveAgentRepository = Depends(get_proactive_agent_repository),
) -> dict:
    """Get or create a proactive agent session for a user."""
    service = _get_service(repository)
    result = await service.get_session(
        user_id=user_id,
        session_id=session_id,
        ai_character_name=ai_character_name,
    )
    return api_ok("Session retrieved", data=result)


@router.post("/notifications", response_model=ApiResponse[dict])
async def receive_agent_notification(
    request: AgentNotificationRequest,
    _: None = Depends(_verify_internal_api_key),
    repository: ProactiveAgentRepository = Depends(get_proactive_agent_repository),
) -> dict:
    """
    Receive a notification/message from the agent (server-to-server).

    Called by the heartbeat script when the agent has an observation to share.
    Requires internal API key authentication.
    """
    service = _get_service(repository)
    try:
        result = await service.receive_agent_notification(request)
        return api_ok("Notification stored", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/health")
async def proactive_agent_health() -> dict:
    """Health check for proactive agent endpoints."""
    from core.connections import get_proactive_registry, get_server_id

    registry = get_proactive_registry()
    return api_ok(
        "Proactive agent API healthy",
        data={
            "status": "healthy",
            "character": DEFAULT_CHARACTER_NAME,
            "version": API_VERSION,
            "active_ws_connections": registry.active_count,
            "server_id": get_server_id(),
        },
    )


__all__ = ["router"]
