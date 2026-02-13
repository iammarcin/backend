"""Proactive WebSocket handler for Claude Code characters (Sherlock, Bugsy).

Integrates with the unified /chat/ws endpoint, adding:
- Connection registry for server-initiated push
- Ping/pong keepalive for mobile networks
- Sync mechanism for missed messages on reconnect

Connection Flow:
1. Client connects: /chat/ws?mode=proactive&user_id=X&session_id=Y
2. Server registers in ProactiveConnectionRegistry
3. Server sends 'connected' event with ping_interval
4. Client can send messages (handled by existing proactive_agent REST API)
5. Server pushes responses when ready (streaming or notification)
6. On reconnect: client sends sync request, server delivers missed msgs
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from core.connections import get_proactive_registry, get_server_id
from features.chat.utils.proactive_message_handlers import (
    handle_send_message,
    handle_sync_request,
)

logger = logging.getLogger(__name__)

PING_INTERVAL_SECONDS = 30


async def handle_incoming_messages(
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    stop_event: asyncio.Event,
) -> None:
    """Handle incoming messages from client (sync requests, pong responses, send)."""
    registry = get_proactive_registry()

    try:
        while not stop_event.is_set():
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=PING_INTERVAL_SECONDS + 5,
                )
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break

            msg_type = message.get("type", "")

            if msg_type == "pong":
                await registry.update_last_ping(user_id, websocket)

            elif msg_type == "sync":
                await handle_sync_request(websocket, user_id, session_id, message)

            elif msg_type == "send_message":
                await handle_send_message(websocket, user_id, session_id, message)

            elif msg_type == "cancel":
                # Cancel any active OpenClaw stream for this session
                try:
                    from features.proactive_agent.openclaw.router import abort_openclaw_stream_by_session
                    aborted = await abort_openclaw_stream_by_session(session_id)
                    if aborted:
                        logger.info("OpenClaw stream aborted via cancel (user=%s, session=%s)", user_id, session_id[:8])
                        await websocket.send_json({
                            "type": "cancelled",
                            "content": "Request cancelled",
                            "session_id": session_id,
                        })
                    else:
                        logger.debug("Cancel requested but no active OpenClaw stream (user=%s, session=%s)", user_id, session_id[:8])
                except Exception as e:
                    logger.error("Failed to abort OpenClaw stream on cancel: %s", e)

            else:
                logger.debug("Unknown message type from user %s: %s", user_id, msg_type)

    except WebSocketDisconnect:
        logger.info("Client disconnected (user %s)", user_id)
    except RuntimeError as exc:
        if "not connected" in str(exc).lower():
            logger.debug(
                "WebSocket closed during receive (user %s) - likely replaced",
                user_id,
            )
        else:
            logger.error("Runtime error handling incoming messages: %s", exc)
    except Exception as exc:
        logger.error("Error handling incoming messages: %s", exc, exc_info=True)


async def send_keepalive_pings(
    websocket: WebSocket,
    user_id: int,
    stop_event: asyncio.Event,
) -> None:
    """Send periodic ping messages to keep connection alive."""
    try:
        while not stop_event.is_set():
            await asyncio.sleep(PING_INTERVAL_SECONDS)
            if stop_event.is_set():
                break

            try:
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                })
            except Exception as exc:
                logger.warning("Failed to send ping to user %s: %s", user_id, exc)
                break

    except asyncio.CancelledError:
        pass


async def handle_proactive_websocket(
    websocket: WebSocket,
    user_id: int,
    session_id: str,
    client_id: str | None = None,
) -> None:
    """Handle proactive mode WebSocket connection.

    This is called from the unified /chat/ws endpoint when mode=proactive.

    Args:
        websocket: FastAPI WebSocket connection (already accepted)
        user_id: Authenticated user ID
        session_id: Proactive agent session ID
        client_id: Client identifier (e.g., "kotlin-xxx" or "react-xxx") for
                   distinguishing multiple clients on the same session.
                   Only replaces connections with the same client_id.
    """
    registry = get_proactive_registry()
    stop_event = asyncio.Event()
    tasks: list[asyncio.Task] = []

    # DEBUG: Full session ID logging
    logger.info(
        "[SESSION DEBUG] WS CONNECT: user=%s, full_session_id=%s, client=%s",
        user_id,
        session_id,
        client_id[:12] if client_id else "none",
    )
    logger.info(
        "Proactive WebSocket accepted: user=%s, session=%s, client=%s",
        user_id,
        session_id[:8] if session_id else "none",
        client_id[:12] if client_id else "none",
    )

    try:
        await registry.register(user_id, session_id, websocket, client_id)

        await websocket.send_json({
            "type": "connected",
            "user_id": user_id,
            "session_id": session_id,
            "server_id": get_server_id(),
            "server_time": datetime.utcnow().isoformat() + "Z",
            "ping_interval": PING_INTERVAL_SECONDS,
        })

        ping_task = asyncio.create_task(
            send_keepalive_pings(websocket, user_id, stop_event)
        )
        tasks.append(ping_task)

        receive_task = asyncio.create_task(
            handle_incoming_messages(websocket, user_id, session_id, stop_event)
        )
        tasks.append(receive_task)

        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for task in done:
            if task.exception():
                logger.error("Task failed: %s", task.exception())

    except WebSocketDisconnect:
        logger.info("Proactive WebSocket disconnected: user=%s", user_id)
    except Exception as exc:
        logger.error(
            "Proactive WebSocket error for user %s: %s", user_id, exc, exc_info=True
        )
        with suppress(Exception):
            await websocket.send_json({
                "type": "error",
                "error": str(exc),
            })
    finally:
        stop_event.set()
        await registry.unregister(user_id, websocket)

        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            with suppress(Exception):
                await asyncio.gather(*tasks, return_exceptions=True)

        with suppress(Exception):
            await websocket.close()

        logger.info("Proactive WebSocket closed: user=%s", user_id)


__all__ = ["handle_proactive_websocket", "PING_INTERVAL_SECONDS"]
