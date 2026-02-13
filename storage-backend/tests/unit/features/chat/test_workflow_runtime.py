"""Unit tests for WorkflowRuntime cancellation state."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.streaming.manager import StreamingManager
from features.chat.utils.websocket_runtime import WorkflowRuntime, create_workflow_runtime


@pytest.mark.asyncio
async def test_workflow_runtime_cancellation_initial_state() -> None:
    """WorkflowRuntime starts without cancellation requested."""
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    runtime = WorkflowRuntime(manager=manager, tasks=[], frontend_queue=queue)

    assert not runtime.is_cancelled()


@pytest.mark.asyncio
async def test_workflow_runtime_cancel_sets_flag() -> None:
    """Calling cancel() flips the internal flag."""
    manager = StreamingManager()
    queue: asyncio.Queue = asyncio.Queue()
    runtime = WorkflowRuntime(manager=manager, tasks=[], frontend_queue=queue)

    runtime.cancel()

    assert runtime.is_cancelled()


@pytest.mark.asyncio
async def test_workflow_runtime_cancel_idempotent() -> None:
    """Calling cancel() multiple times is safe."""
    runtime = WorkflowRuntime(manager=StreamingManager(), tasks=[], frontend_queue=asyncio.Queue())

    runtime.cancel()
    runtime.cancel()

    assert runtime.is_cancelled()


@pytest.mark.asyncio
async def test_workflow_runtime_wait_for_cancellation() -> None:
    """wait_for_cancellation() resolves after cancel() is invoked."""
    runtime = WorkflowRuntime(manager=StreamingManager(), tasks=[], frontend_queue=asyncio.Queue())

    async def cancel_later() -> None:
        await asyncio.sleep(0.01)
        runtime.cancel()

    waiter = asyncio.create_task(runtime.wait_for_cancellation())
    cancel_task = asyncio.create_task(cancel_later())

    await asyncio.gather(waiter, cancel_task)

    assert runtime.is_cancelled()


@pytest.mark.asyncio
async def test_create_workflow_runtime_has_cancellation() -> None:
    """Factory helper wires up cancellation support automatically."""
    websocket = MagicMock()
    websocket.send_json = AsyncMock()

    runtime = await create_workflow_runtime(session_id="test", websocket=websocket)

    assert not runtime.is_cancelled()
    runtime.cancel()
    assert runtime.is_cancelled()

    for task in runtime.tasks:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_workflow_runtime_cancellation_concurrent_access() -> None:
    """Cancellation flag behaves under concurrent reads/writes."""
    runtime = WorkflowRuntime(manager=StreamingManager(), tasks=[], frontend_queue=asyncio.Queue())

    async def reader() -> None:
        for _ in range(50):
            runtime.is_cancelled()
            await asyncio.sleep(0)

    async def writer() -> None:
        for _ in range(5):
            runtime.cancel()
            await asyncio.sleep(0)

    await asyncio.gather(reader(), writer(), reader())

    assert runtime.is_cancelled()


@pytest.mark.asyncio
async def test_workflow_runtime_disconnect_cancellation_default() -> None:
    """Workflows cancel on disconnect by default."""
    runtime = WorkflowRuntime(manager=StreamingManager(), tasks=[], frontend_queue=asyncio.Queue())

    assert runtime.should_cancel_on_disconnect()


@pytest.mark.asyncio
async def test_workflow_runtime_allow_disconnect_disables_cancellation() -> None:
    """allow_disconnect() disables cancellation on disconnect."""
    runtime = WorkflowRuntime(manager=StreamingManager(), tasks=[], frontend_queue=asyncio.Queue())

    runtime.allow_disconnect()

    assert not runtime.should_cancel_on_disconnect()
