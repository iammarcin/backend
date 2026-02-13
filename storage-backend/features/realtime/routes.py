"""Expose realtime websocket entrypoints and health endpoints."""

from __future__ import annotations

import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket

from core.observability import log_websocket_request
from core.providers.realtime.factory import list_realtime_providers
from . import get_realtime_chat_service
from .service import RealtimeChatService

logger = logging.getLogger(__name__)

websocket_router = APIRouter(prefix="/chat", tags=["chat"])
router = APIRouter(prefix="/realtime", tags=["realtime"])


@websocket_router.websocket("/ws")
async def websocket_route(
    websocket: WebSocket,
    service: RealtimeChatService = Depends(get_realtime_chat_service),
) -> None:
    """Realtime websocket entrypoint delegating to the service layer."""

    log_websocket_request(websocket, logger=logger, label="Realtime chat websocket")
    logger.debug("Realtime websocket upgrade requested")
    await service.handle_websocket(websocket)


@router.get("/health")
async def realtime_health_check(
    realtime_service: Annotated[RealtimeChatService, Depends(get_realtime_chat_service)],
) -> dict[str, object]:
    """Health check exposing provider connectivity and session usage."""

    try:
        await realtime_service.check_provider_health()
        provider_healthy = True
        provider_error: str | None = None
    except Exception as exc:  # pragma: no cover - defensive
        provider_healthy = False
        provider_error = str(exc)

    return {
        "status": "healthy" if provider_healthy else "degraded",
        "provider": {
            "healthy": provider_healthy,
            "error": provider_error,
        },
        "sessions": {
            "active": realtime_service.active_session_count(),
            "capacity": RealtimeChatService._MAX_CONCURRENT_SESSIONS,
        },
        "timestamp": time.time(),
    }


@router.get("/health/ready")
async def realtime_readiness_check(
    realtime_service: Annotated[RealtimeChatService, Depends(get_realtime_chat_service)],
) -> dict[str, str]:
    """Readiness probe ensuring service can accept new sessions."""

    if not realtime_service.can_accept_connections():
        raise HTTPException(status_code=503, detail="Not ready to accept connections")
    return {"status": "ready"}


@router.get("/health/live")
async def realtime_liveness_check() -> dict[str, str]:
    """Liveness probe used by orchestration platforms."""

    return {"status": "alive"}


@router.get("/debug/providers")
async def realtime_provider_debug() -> dict[str, object]:
    """Expose currently registered realtime providers for debugging."""

    providers = list_realtime_providers()
    internal_providers = list_realtime_providers(include_internal=True)
    logger.info(
        "Realtime provider debug endpoint invoked",
        extra={"providers": providers},
    )
    return {
        "providers": providers,
        "registered": internal_providers,
        "count": len(internal_providers),
    }


__all__ = ["router", "websocket_router"]
