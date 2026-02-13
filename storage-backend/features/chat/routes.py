"""Chat routing orchestration for conversation backend.

This module wires together the chat WebSocket endpoint, determines whether a
request should use the realtime pipeline, proactive mode, or standard chat.
The heavy lifting for persistence-centric operations lives in
``history_routes.py`` to keep this file narrowly focused on composition.

WebSocket Modes:
- standard (default): Ephemeral connection for prompt-response chat
- realtime: Low-latency voice conversations (OpenAI Realtime API, Gemini Live)
- proactive: Persistent connection for server-initiated push notifications
            (used by Claude Code characters like Sherlock, Bugsy)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict

from fastapi import APIRouter, Depends, WebSocket
from fastapi.websockets import WebSocketDisconnect

from core.observability.websocket_logging import (
    log_websocket_accepted,
    log_websocket_error,
    log_websocket_rejected,
    log_websocket_upgrade_attempt,
)
from features.chat.history_routes import history_router
from features.chat.websocket import websocket_chat_endpoint
from features.chat.websocket_routes import chat_router as chat_http_router
from features.chat.services.proactive_handler import handle_proactive_websocket
from features.chat.agent_routes import router as agent_router
from features.chat.group_routes import router as group_router
from features.chat.utils.mode_detection import (
    initial_message_targets_realtime,
    should_use_realtime,
    should_use_proactive,
)
from features.realtime import RealtimeChatService, get_realtime_chat_service


logger = logging.getLogger(__name__)

router = APIRouter()
router.include_router(chat_http_router)
router.include_router(history_router)
router.include_router(group_router)
router.include_router(agent_router)


@router.websocket("/api/chat/ws")
@router.websocket("/chat/ws")
async def chat_websocket_switchboard(
    websocket: WebSocket,
    realtime_service: RealtimeChatService = Depends(get_realtime_chat_service),
) -> None:
    """Route websocket requests to the appropriate chat pipeline.

    Available at both /chat/ws and /api/chat/ws for compatibility with
    different frontend base URL configurations.

    Supported modes (via ?mode= query param):
    - standard (default): Ephemeral prompt-response chat
    - realtime: Low-latency voice conversations
    - proactive: Persistent connection for server-initiated push (Sherlock, Bugsy)
    """
    log_websocket_upgrade_attempt(websocket, endpoint=websocket.url.path)

    # Check for proactive mode first (for Claude Code characters)
    is_proactive, user_id, session_id, client_id = should_use_proactive(websocket)
    if is_proactive:
        if not user_id or not session_id:
            logger.warning(
                "Proactive mode requires user_id and session_id query params"
            )
            await websocket.close(
                code=1008,
                reason="Proactive mode requires user_id and session_id",
            )
            return

        logger.info(
            "Routing websocket to proactive handler: user=%s, session=%s, client=%s",
            user_id,
            session_id[:8] if session_id else "none",
            client_id[:12] if client_id else "none",
        )
        await websocket.accept()
        log_websocket_accepted(websocket)
        await handle_proactive_websocket(websocket, user_id, session_id, client_id)
        return

    # Check for realtime mode
    if should_use_realtime(websocket):
        logger.info("Routing websocket request to realtime chat service")
        await realtime_service.handle_websocket(websocket)
        return

    initial_message: Dict[str, object] | None = None

    try:
        await websocket.accept()
        log_websocket_accepted(websocket)
        logger.debug("WebSocket connection accepted in switchboard")

        await websocket.send_json(
            {
                "type": "websocket_ready",
                "content": "Backend ready",
                "version": "2.0",
            }
        )

        raw_initial = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        if isinstance(raw_initial, dict):
            initial_message = raw_initial
        else:
            logger.debug(
                "Initial websocket payload is not an object; defaulting to classic routing"
            )
            initial_message = None
    except asyncio.TimeoutError:
        logger.warning(
            "No initial message received within 10s after ready signal; closing websocket"
        )
        log_websocket_rejected(
            websocket,
            reason="Initial message required",
            code=1008,
        )
        await websocket.close(code=1008, reason="Initial message required")
        return
    except WebSocketDisconnect:
        logger.info("Client disconnected before initial message was received")
        return
    except json.JSONDecodeError:
        logger.warning("Invalid JSON received while routing websocket request")
        log_websocket_rejected(
            websocket,
            reason="Invalid initial payload",
            code=1003,
        )
        await websocket.close(code=1003, reason="Invalid initial payload")
        return
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("Error while routing websocket connection: %s", exc, exc_info=True)
        log_websocket_error(websocket, error=exc, context="switchboard routing")
        await websocket.close(code=1011, reason="Internal error")
        return

    request_type = None
    if initial_message:
        request_type = initial_message.get("request_type")

    if isinstance(request_type, str) and request_type.lower() == "realtime":
        logger.info("Routing websocket request to realtime chat service (payload hint)")
        await realtime_service.handle_websocket(
            websocket, initial_message=initial_message
        )
        return

    if initial_message_targets_realtime(initial_message):
        logger.info(
            "Routing websocket request to realtime chat service (model/settings hint)"
        )
        await realtime_service.handle_websocket(
            websocket, initial_message=initial_message
        )
        return

    logger.info("Routing websocket request to standard chat workflow")
    await websocket_chat_endpoint(websocket, initial_message=initial_message)


__all__ = ["router"]
