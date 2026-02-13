"""Workflow lifecycle management for WebSocket chat.

Handles workflow cancellation, completion handling, and error management
for chat workflows.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def handle_workflow_completion(
    workflow: asyncio.Task[bool],
    session_id: str,
) -> bool:
    """Handle completion of a workflow task.

    Args:
        workflow: The completed workflow task
        session_id: Session ID for logging

    Returns:
        True if workflow should continue (keep connection open),
        False if connection should close
    """
    workflow_should_continue = True
    try:
        workflow_should_continue = await workflow
    except asyncio.CancelledError:
        logger.info(
            "Workflow cancelled for session %s", session_id
        )
        workflow_should_continue = True
    except Exception as exc:
        logger.error(
            "Workflow failed for session %s: %s",
            session_id,
            exc,
            exc_info=True,
        )
        workflow_should_continue = False

    return workflow_should_continue


async def cancel_workflow(
    workflow: asyncio.Task[bool],
    session_id: str,
) -> None:
    """Cancel a running workflow and wait for cleanup.

    Args:
        workflow: The workflow task to cancel
        session_id: Session ID for logging
    """
    logger.info(
        "Cancelling workflow for session %s",
        session_id,
    )
    workflow.cancel()
    try:
        await workflow
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error(
            "Error while awaiting cancelled workflow (session=%s): %s",
            session_id,
            exc,
            exc_info=True,
        )


async def ensure_workflow_ready(
    current_workflow: Optional[asyncio.Task[bool]],
    session_id: str,
) -> None:
    """Ensure no workflow is running before starting a new one.

    If a workflow is still running, wait for it to complete.

    Args:
        current_workflow: Currently running workflow (if any)
        session_id: Session ID for logging
    """
    if current_workflow and not current_workflow.done():
        logger.warning(
            "New request while workflow still running - waiting (session=%s)",
            session_id,
        )
        try:
            await current_workflow
        except Exception:  # pragma: no cover - defensive logging
            pass
