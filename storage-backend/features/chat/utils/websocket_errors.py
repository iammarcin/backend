"""Shared helpers for logging and emitting WebSocket error payloads.

These helpers keep the dispatcher free from repetitive error-emission snippets
while ensuring a consistent payload structure is sent to the client.
"""

from contextlib import suppress
from typing import Optional

from core.streaming.manager import StreamingManager


async def _emit_error(
    *, manager: StreamingManager, session_id: str, stage: str, message: str
) -> None:
    with suppress(Exception):
        await manager.send_to_queues(
            {"type": "error", "content": message, "stage": stage, "session_id": session_id}
        )


async def emit_validation_error(
    *, manager: StreamingManager, session_id: str, error: str
) -> None:
    """Emit a validation error to the frontend."""

    await _emit_error(manager=manager, session_id=session_id, stage="validation", message=error)


async def emit_provider_error(
    *, manager: StreamingManager, session_id: str, error: str
) -> None:
    """Emit a provider/service error to the frontend."""

    await _emit_error(manager=manager, session_id=session_id, stage="provider", message=error)


async def emit_json_error(*, manager: StreamingManager, session_id: str) -> None:
    """Emit a JSON decoding error."""

    await _emit_error(
        manager=manager,
        session_id=session_id,
        stage="validation",
        message="Invalid payload",
    )


async def emit_internal_error(
    *, manager: StreamingManager, session_id: str, message: Optional[str] = None
) -> None:
    """Emit an internal server error payload."""

    await _emit_error(
        manager=manager,
        session_id=session_id,
        stage="internal",
        message=message or "Internal server error",
    )
