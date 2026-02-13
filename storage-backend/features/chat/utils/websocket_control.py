"""Helpers for handling control WebSocket messages before workflow execution.

The dispatcher invokes these utilities to process housekeeping frames (ping,
heartbeat, close notifications) before dedicating resources to a workflow.
"""

from fastapi import WebSocket

from .websocket_session import WorkflowSession, utcnow


async def handle_control_message(
    *, message_type: str, websocket: WebSocket, session: WorkflowSession
) -> bool | str | None:
    """Process control messages that do not require workflow orchestration."""

    if message_type == "ping":
        await websocket.send_json({"type": "pong", "timestamp": utcnow().isoformat()})
        return True

    if message_type == "heartbeat":
        return True

    if message_type == "close_session":
        await websocket.send_json(
            {
                "type": "closing",
                "reason": "client_request",
                "session_id": session.session_id,
            }
        )
        return False

    if message_type == "cancel":
        return "cancel"

    if message_type in {"audio_chunk", "audio_complete"}:
        return True

    return None
