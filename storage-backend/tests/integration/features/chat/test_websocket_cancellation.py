"""Integration-style tests for WebSocket cancellation handling."""

from __future__ import annotations

import asyncio
import json
from collections import deque
import sys
import types
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Deque, Dict
from unittest.mock import AsyncMock

import pytest
from starlette.websockets import WebSocketState

if "qdrant_client" not in sys.modules:
    qdrant_module = types.ModuleType("qdrant_client")

    class _AsyncQdrantClient:  # pragma: no cover - import stub
        async def close(self) -> None:
            return

    qdrant_module.AsyncQdrantClient = _AsyncQdrantClient
    models_module = types.ModuleType("qdrant_client.models")
    for attr in (
        "Distance",
        "FieldCondition",
        "Filter",
        "MatchAny",
        "MatchValue",
        "PayloadSchemaType",
        "PointIdsList",
        "PointStruct",
        "Range",
        "VectorParams",
    ):
        setattr(models_module, attr, type(attr, (), {}))
    qdrant_module.models = models_module
    sys.modules["qdrant_client"] = qdrant_module
    sys.modules["qdrant_client.models"] = models_module

from features.chat.websocket import websocket_chat_endpoint

WebsocketDispatch = Callable[..., Awaitable[bool]]


def _build_mock_websocket() -> AsyncMock:
    websocket = AsyncMock()
    websocket.application_state = WebSocketState.CONNECTED
    websocket.client = SimpleNamespace(host="127.0.0.1", port=1234)
    websocket.url = SimpleNamespace(path="/chat/ws", query="")
    websocket.headers = {}
    websocket.subprotocols = []
    websocket.send_json = AsyncMock()
    websocket.close = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.receive = AsyncMock()
    return websocket


async def _idle_monitor_stub(*_: Any, **__: Any) -> None:
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:  # pragma: no cover - cancelled during cleanup
        raise


def _patch_dependencies(monkeypatch: pytest.MonkeyPatch, dispatch_impl: WebsocketDispatch) -> None:
    auth_mock = AsyncMock(return_value={"customer_id": 42})
    monkeypatch.setattr("features.chat.websocket.authenticate_websocket", auth_mock)
    monkeypatch.setattr("features.chat.websocket.ChatService", lambda: object())
    monkeypatch.setattr("features.chat.websocket.STTService", lambda: object())
    monkeypatch.setattr("features.chat.websocket.dispatch_workflow", dispatch_impl)
    monkeypatch.setattr("features.chat.websocket.monitor_session_idle", _idle_monitor_stub)


def _message(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "websocket.receive", "text": json.dumps(payload)}


@pytest.mark.asyncio
async def test_cancel_message_during_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _build_mock_websocket()
    messages: Deque[Dict[str, Any]] = deque(
        [
            _message({"type": "text", "prompt": "long running request"}),
            _message({"type": "cancel"}),
            {"type": "websocket.disconnect"},
        ]
    )

    async def fake_receive() -> Dict[str, Any]:
        if messages:
            return messages.popleft()
        await asyncio.sleep(0)
        return {"type": "websocket.disconnect"}

    websocket.receive.side_effect = fake_receive

    blocker = asyncio.Event()
    workflow_cancelled = asyncio.Event()

    async def slow_dispatch(**_: Any) -> bool:
        try:
            await blocker.wait()
        except asyncio.CancelledError:
            workflow_cancelled.set()
            # Simulate what the real dispatcher does on cancellation
            await websocket.send_json({
                "type": "cancelled",
                "content": "Request cancelled by user",
                "stage": "execution",
            })
            await websocket.send_json({"type": "text_not_requested", "content": ""})
            await websocket.send_json({"type": "tts_not_requested", "content": ""})
            raise
        return True

    _patch_dependencies(monkeypatch, slow_dispatch)
    await websocket_chat_endpoint(websocket, initial_message=None)

    cancelled_events = [
        call.args[0]
        for call in websocket.send_json.call_args_list
        if call.args and isinstance(call.args[0], dict)
    ]
    assert any(event.get("type") == "cancelled" for event in cancelled_events)
    assert workflow_cancelled.is_set()


@pytest.mark.asyncio
async def test_cancel_without_active_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _build_mock_websocket()
    messages: Deque[Dict[str, Any]] = deque(
        [
            _message({"type": "cancel"}),
            {"type": "websocket.disconnect"},
        ]
    )

    async def fake_receive() -> Dict[str, Any]:
        if messages:
            return messages.popleft()
        await asyncio.sleep(0)
        return {"type": "websocket.disconnect"}

    websocket.receive.side_effect = fake_receive
    dispatch_mock = AsyncMock(return_value=True)

    _patch_dependencies(monkeypatch, dispatch_mock)
    await websocket_chat_endpoint(websocket, initial_message=None)

    assert dispatch_mock.await_count == 0


@pytest.mark.asyncio
async def test_new_request_waits_for_running_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _build_mock_websocket()
    receive_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def fake_receive() -> Dict[str, Any]:
        return await receive_queue.get()

    websocket.receive.side_effect = fake_receive

    first_started = asyncio.Event()
    second_started = asyncio.Event()
    first_finish = asyncio.Event()
    second_finish = asyncio.Event()
    call_count = {"value": 0}

    async def dispatch_stub(**kwargs: Any) -> bool:
        runtime = kwargs.get("runtime")
        idx = call_count["value"]
        call_count["value"] += 1
        try:
            if idx == 0:
                first_started.set()
                await first_finish.wait()
                return True
            second_started.set()
            await second_finish.wait()
            return True
        finally:
            if runtime:
                token = runtime.manager.create_completion_token()
                await runtime.manager.signal_completion(token=token)

    _patch_dependencies(monkeypatch, dispatch_stub)
    endpoint_task = asyncio.create_task(websocket_chat_endpoint(websocket, initial_message=None))

    await receive_queue.put(_message({"type": "text", "prompt": "Request #1"}))
    await first_started.wait()

    await receive_queue.put(_message({"type": "text", "prompt": "Request #2"}))
    await asyncio.sleep(0.05)
    assert not second_started.is_set()

    first_finish.set()
    await second_started.wait()

    await receive_queue.put({"type": "websocket.disconnect"})
    second_finish.set()
    await endpoint_task

    assert call_count["value"] == 2


@pytest.mark.asyncio
async def test_disconnect_does_not_cancel_detached_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket = _build_mock_websocket()
    messages: Deque[Dict[str, Any]] = deque(
        [
            _message({"type": "text", "prompt": "long running request"}),
            {"type": "websocket.disconnect"},
        ]
    )

    async def fake_receive() -> Dict[str, Any]:
        if messages:
            return messages.popleft()
        await asyncio.sleep(0)
        return {"type": "websocket.disconnect"}

    websocket.receive.side_effect = fake_receive

    workflow_cancelled = asyncio.Event()
    workflow_completed = asyncio.Event()

    async def dispatch_stub(**kwargs: Any) -> bool:
        runtime = kwargs.get("runtime")
        if runtime:
            runtime.allow_disconnect()
        try:
            await asyncio.sleep(0.05)
            return True
        except asyncio.CancelledError:
            workflow_cancelled.set()
            raise
        finally:
            if runtime:
                token = runtime.manager.create_completion_token()
                await runtime.manager.signal_completion(token=token)
            workflow_completed.set()

    _patch_dependencies(monkeypatch, dispatch_stub)
    await websocket_chat_endpoint(websocket, initial_message=None)

    assert workflow_completed.is_set()
    assert not workflow_cancelled.is_set()
