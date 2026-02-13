"""WebSocket message reception with workflow-aware asyncio handling.

Handles the complex logic of receiving messages while workflows are running,
managing pending message queues, and coordinating between message arrival
and workflow completion.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket

logger = logging.getLogger(__name__)


async def receive_next_message(
    websocket: WebSocket,
    pending_messages: List[Dict[str, Any]],
    current_workflow: Optional[asyncio.Task[bool]],
    receive_task: Optional[asyncio.Task[Any]],
    session_id: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[asyncio.Task[Any]], bool]:
    """Receive the next message from WebSocket with workflow coordination.

    This function handles three scenarios:
    1. Pending messages exist → return immediately from queue
    2. Workflow running → wait for either message or workflow completion
    3. No workflow → wait for message

    Args:
        websocket: The WebSocket connection
        pending_messages: Queue of messages waiting to be processed
        current_workflow: Currently running workflow task (if any)
        receive_task: Pending receive task (if any)
        session_id: Session ID for logging

    Returns:
        Tuple of (data, raw_message, new_receive_task, workflow_completed):
        - data: Parsed message data from pending queue (or None)
        - raw_message: Raw WebSocket message received (or None)
        - new_receive_task: Updated receive task reference
        - workflow_completed: True if workflow finished during this call
    """
    # Scenario 1: Pending messages exist
    if pending_messages:
        data = pending_messages.pop(0)
        return (data, None, receive_task, False)

    # Scenario 2: Workflow is running
    if current_workflow and not current_workflow.done():
        # Create receive task if needed
        if receive_task is None:
            receive_task = asyncio.create_task(websocket.receive())

        # Wait for either message or workflow completion
        done, _ = await asyncio.wait(
            {receive_task, current_workflow},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Check if workflow completed
        if current_workflow in done:
            # Workflow finished - we'll handle this in caller
            # Check if message also arrived
            if receive_task in done:
                try:
                    message = await receive_task
                    return (None, message, None, True)
                finally:
                    receive_task = None
            else:
                # Workflow done, no message yet
                return (None, None, receive_task, True)
        else:
            # Message arrived while workflow still running
            try:
                message = await receive_task
                return (None, message, None, False)
            finally:
                receive_task = None

    # Scenario 3: No workflow running
    if receive_task is None:
        receive_task = asyncio.create_task(websocket.receive())
    try:
        message = await receive_task
        return (None, message, None, False)
    finally:
        receive_task = None
