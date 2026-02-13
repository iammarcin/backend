"""WebSocket endpoint orchestrating chat workflows.

Provides the main WebSocket endpoint for chat sessions, coordinating
authentication, message reception, workflow dispatch, and lifecycle management.
Complex logic is delegated to focused helper modules for maintainability.
"""

import asyncio
import logging
from contextlib import suppress
from typing import Any, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.auth import AuthenticationError
from core.observability import log_websocket_request
from core.observability.websocket_logging import (
    log_websocket_accepted,
    log_websocket_message_received,
)
from features.audio.service import STTService
from features.chat.service import ChatService

from .utils.websocket_auth import authenticate_websocket
from .utils.websocket_control import handle_control_message
from .utils.websocket_dispatcher import dispatch_workflow
from .utils.websocket_message_parser import parse_websocket_message, is_disconnect_message
from .utils.websocket_message_receiver import receive_next_message
from .utils.websocket_request import normalise_request_type
from .utils.websocket_runtime import WorkflowRuntime, create_workflow_runtime
from .utils.websocket_runtime_helpers import cleanup_runtime, route_audio_frame_if_needed
from .utils.websocket_session import WorkflowSession
from .utils.websocket_settings_logger import log_settings_summary
from .utils.websocket_stream_buffer import get_stream_buffer_manager
from .utils.websocket_streaming import monitor_session_idle
from .utils.websocket_workflow_lifecycle import (
    cancel_workflow,
    ensure_workflow_ready,
    handle_workflow_completion,
)

logger = logging.getLogger(__name__)

# Re-export for test compatibility (tests patch this)
__all__ = ["websocket_chat_endpoint", "dispatch_workflow", "monitor_session_idle"]


SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60  # 30 minutes


async def handle_stream_resume(
    websocket: WebSocket,
    session_id: Optional[str],
    last_chunk_index: Optional[int],
) -> None:
    """Handle reconnection request for missed chunks.

    Retrieves buffered chunks after the client's last received chunk_index
    and sends them as a batch for replay.
    """
    logger.info(
        "🔄 STREAM_RESUME received: session_id=%s, last_chunk_index=%s",
        session_id[:8] if session_id else "None",
        last_chunk_index,
    )
    
    buffer_manager = get_stream_buffer_manager()
    
    # Debug: List all active buffers
    active_buffers = list(buffer_manager.buffers.keys())
    logger.info(
        "🔄 Active buffers: %s",
        [s[:8] for s in active_buffers] if active_buffers else "NONE",
    )

    if not session_id:
        await websocket.send_json({
            "type": "stream_resume_batch",
            "data": {
                "session_id": None,
                "chunks": [],
                "count": 0,
                "status": "invalid_request",
            },
        })
        return

    if not buffer_manager.has_buffer(session_id):
        # No buffer exists — stream may have completed or expired
        await websocket.send_json({
            "type": "stream_resume_batch",
            "data": {
                "session_id": session_id,
                "chunks": [],
                "count": 0,
                "status": "no_buffer",
            },
        })
        logger.info(
            "Stream resume requested but no buffer exists (session=%s)",
            session_id[:8] if session_id else "none",
        )
        return

    missed_chunks = await buffer_manager.get_missed_chunks(session_id, last_chunk_index)

    await websocket.send_json({
        "type": "stream_resume_batch",
        "data": {
            "session_id": session_id,
            "chunks": [c["data"] for c in missed_chunks],
            "count": len(missed_chunks),
            "status": "ok",
        },
    })

    logger.info(
        "Sent %d missed chunks for session %s (after chunk_index %s)",
        len(missed_chunks),
        session_id[:8] if session_id else "none",
        last_chunk_index,
    )


async def websocket_chat_endpoint(
    websocket: WebSocket, *, initial_message: Dict[str, Any] | None = None
) -> None:
    """Main WebSocket chat endpoint handling lifecycle and streaming."""

    log_websocket_request(websocket, logger=logger, label="Chat websocket")

    if websocket.application_state != WebSocketState.CONNECTED:
        await websocket.accept()
        log_websocket_accepted(websocket)
        logger.info("WebSocket connection accepted")

    service = ChatService()
    stt_service = STTService()

    idle_task: Optional[asyncio.Task] = None
    current_workflow: Optional[asyncio.Task[bool]] = None
    receive_task: Optional[asyncio.Task[Any]] = None
    current_runtime: Optional[WorkflowRuntime] = None

    try:
        auth_context = await authenticate_websocket(websocket)
        customer_id = int(auth_context.get("customer_id", 0))
        session = WorkflowSession(customer_id=customer_id)

        logger.info(
            "WebSocket authenticated for customer %s (session=%s)",
            customer_id,
            session.session_id,
        )
        log_websocket_accepted(
            websocket,
            session_id=session.session_id,
            customer_id=customer_id,
        )
        with suppress(Exception):
            await websocket.send_json(
                {
                    "type": "websocket_ready",
                    "content": "Backend ready",
                    "session_id": session.session_id,
                }
            )
        logger.debug(
            "Sent session ready signal to frontend (session=%s)", session.session_id
        )

        idle_task = asyncio.create_task(
            monitor_session_idle(
                websocket,
                session,
                timeout_seconds=SESSION_IDLE_TIMEOUT_SECONDS,
            )
        )

        pending_messages: List[Dict[str, Any]] = []
        if initial_message and isinstance(initial_message, dict):
            pending_messages.append(initial_message)

        while True:
            data: Optional[Dict[str, Any]] = None
            message: Optional[Dict[str, Any]] = None

            # Receive next message (handles pending queue, workflow coordination)
            try:
                data, message, receive_task, workflow_completed = await receive_next_message(
                    websocket=websocket,
                    pending_messages=pending_messages,
                    current_workflow=current_workflow,
                    receive_task=receive_task,
                    session_id=session.session_id,
                )

                # Handle workflow completion if it finished during receive
                if workflow_completed and current_workflow:
                    workflow_should_continue = await handle_workflow_completion(
                        current_workflow, session.session_id
                    )
                    current_workflow = None
                    await cleanup_runtime(current_runtime)
                    current_runtime = None

                    if not workflow_should_continue:
                        logger.info(
                            "Client requested session close (session=%s)",
                            session.session_id,
                        )
                        break

            except WebSocketDisconnect:
                logger.info(
                    "Client disconnected from session %s (customer=%s)",
                    session.session_id,
                    session.customer_id,
                )
                break

            # Parse message if we received one
            if message:
                if await route_audio_frame_if_needed(
                    message,
                    runtime=current_runtime,
                    session_id=session.session_id,
                ):
                    continue

                # Check for disconnect before parsing
                if is_disconnect_message(message):
                    break

                data = await parse_websocket_message(
                    message, websocket, session.session_id
                )

            # Skip if no data to process
            if data is None:
                continue

            # Log message and settings
            log_websocket_message_received(
                data,
                session_id=session.session_id,
            )

            if isinstance(data, dict) and "user_settings" in data:
                log_settings_summary(data.get("user_settings"), session.session_id)

            if not isinstance(data, dict):
                logger.debug(
                    "Ignoring non-dict payload for session %s: %s",
                    session.session_id,
                    data,
                )
                continue

            # Handle control messages (ping, cancel, close)
            message_type = str(data.get("type", "")).lower()

            # Handle stream_resume BEFORE control messages (requires async chunk retrieval)
            if message_type == "stream_resume":
                await handle_stream_resume(
                    websocket=websocket,
                    session_id=data.get("session_id"),
                    last_chunk_index=data.get("last_chunk_index"),
                )
                continue  # Skip normal message processing

            control_result = await handle_control_message(
                message_type=message_type,
                websocket=websocket,
                session=session,
            )

            if control_result == "cancel":
                if current_workflow and not current_workflow.done():
                    await cancel_workflow(current_workflow, session.session_id)
                    current_workflow = None
                    if current_runtime:
                        current_runtime.cancel()  # Mark as cancelled so cleanup_runtime cancels tasks
                    await cleanup_runtime(current_runtime)
                    current_runtime = None
                else:
                    # No active workflow, but OpenClaw might still be streaming
                    # Try to abort any active OpenClaw stream for this session
                    try:
                        from features.proactive_agent.openclaw.router import abort_openclaw_stream_by_session
                        aborted = await abort_openclaw_stream_by_session(session.session_id)
                        if aborted:
                            logger.info("OpenClaw stream aborted via cancel (session=%s)", session.session_id[:8])
                            await websocket.send_json({
                                "type": "cancelled",
                                "content": "Request cancelled",
                                "session_id": session.session_id,
                            })
                        else:
                            logger.debug(
                                "Cancel requested but no workflow or OpenClaw stream running (session=%s)",
                                session.session_id,
                            )
                    except Exception as e:
                        logger.warning("Failed to abort OpenClaw on cancel: %s", e)
                continue

            if control_result is not None:
                if control_result is False:
                    logger.info(
                        "Client requested session close (session=%s)",
                        session.session_id,
                    )
                    break
                continue

            # Touch session to reset idle timer
            session.touch()

            # Ensure no workflow is running before starting new one
            await ensure_workflow_ready(current_workflow, session.session_id)
            await cleanup_runtime(current_runtime)
            current_runtime = None

            runtime = await create_workflow_runtime(
                session_id=session.session_id,
                websocket=websocket,
            )

            # Start new workflow (inline to allow test patching of dispatch_workflow)
            request_type = normalise_request_type(data)
            if request_type in {"audio", "audio_direct"}:
                runtime.create_audio_queue()

            current_runtime = runtime
            current_workflow = asyncio.create_task(
                dispatch_workflow(
                    data=data,
                    session=session,
                    websocket=websocket,
                    service=service,
                    stt_service=stt_service,
                    runtime=runtime,
                )
            )

    except AuthenticationError:
        logger.info("WebSocket authentication failed; connection closed")
        return
    except WebSocketDisconnect:
        logger.info("Client disconnected before session setup completed")
    finally:
        session_obj = locals().get("session")
        session_id = session_obj.session_id if session_obj else "unknown"

        if idle_task:
            idle_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await idle_task

        if current_workflow and not current_workflow.done():
            if current_runtime and not current_runtime.should_cancel_on_disconnect():
                logger.info(
                    "WebSocket disconnected - allowing workflow to finish (session=%s)",
                    session_id,
                )
                with suppress(asyncio.CancelledError, Exception):
                    await current_workflow
            else:
                current_workflow.cancel()
                if current_runtime:
                    current_runtime.cancel()  # Mark as cancelled so cleanup_runtime cancels tasks
                with suppress(asyncio.CancelledError, Exception):
                    await current_workflow

        if receive_task and not receive_task.done():
            receive_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await receive_task

        await cleanup_runtime(current_runtime)

        with suppress(Exception):
            await websocket.close()

        logger.info("WebSocket connection closed for session %s", session_id)
