"""Integration tests to verify cleanup after workflow cancellation."""

from __future__ import annotations

import asyncio
import json
import sys
import types
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict
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
    except asyncio.CancelledError:  # pragma: no cover - cancellation path
        raise


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    dispatch_impl: WebsocketDispatch,
    idle_monitor: Callable[..., Awaitable[None]] | None = None,
) -> None:
    auth_mock = AsyncMock(return_value={"customer_id": 101})
    monkeypatch.setattr("features.chat.websocket.authenticate_websocket", auth_mock)
    monkeypatch.setattr("features.chat.websocket.ChatService", lambda: object())
    monkeypatch.setattr("features.chat.websocket.STTService", lambda: object())
    monkeypatch.setattr("features.chat.websocket.dispatch_workflow", dispatch_impl)
    monitor_impl = idle_monitor or _idle_monitor_stub
    monkeypatch.setattr("features.chat.websocket.monitor_session_idle", monitor_impl)


def _message(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": "websocket.receive", "text": json.dumps(payload)}


@pytest.mark.asyncio
async def test_cancellation_allows_new_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _build_mock_websocket()
    receive_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def fake_receive() -> Dict[str, Any]:
        return await receive_queue.get()

    websocket.receive.side_effect = fake_receive

    first_started = asyncio.Event()
    first_cancelled = asyncio.Event()
    second_started = asyncio.Event()
    call_count = {"value": 0}

    async def dispatch_stub(*, runtime=None, **_: Any) -> bool:
        """Stub that simulates real workflow behavior including signal_completion."""
        idx = call_count["value"]
        call_count["value"] += 1
        if idx == 0:
            first_started.set()
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                first_cancelled.set()
                raise
        second_started.set()
        # Real workflows always call signal_completion before returning.
        # This puts None on the queue so send_to_frontend can exit cleanly.
        if runtime and runtime.manager:
            token = runtime.manager.create_completion_token()
            await runtime.manager.signal_completion(token=token)
        return True

    _patch_dependencies(monkeypatch, dispatch_stub)
    endpoint_task = asyncio.create_task(websocket_chat_endpoint(websocket, initial_message=None))

    await receive_queue.put(_message({"type": "text", "prompt": "one"}))
    await first_started.wait()

    await receive_queue.put(_message({"type": "cancel"}))
    await first_cancelled.wait()

    await receive_queue.put(_message({"type": "text", "prompt": "two"}))
    await second_started.wait()

    await receive_queue.put({"type": "websocket.disconnect"})
    await endpoint_task

    assert call_count["value"] == 2
    assert first_cancelled.is_set()


@pytest.mark.asyncio
async def test_idle_monitor_cancelled_after_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    websocket = _build_mock_websocket()
    receive_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def fake_receive() -> Dict[str, Any]:
        return await receive_queue.get()

    websocket.receive.side_effect = fake_receive

    idle_cancelled = asyncio.Event()

    async def idle_stub(*_: Any, **__: Any) -> None:
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            idle_cancelled.set()
            raise

    async def dispatch_stub(*, runtime=None, **_: Any) -> bool:
        """Stub that simulates real workflow behavior including signal_completion."""
        await asyncio.sleep(0)
        # Real workflows always call signal_completion before returning
        if runtime and runtime.manager:
            token = runtime.manager.create_completion_token()
            await runtime.manager.signal_completion(token=token)
        return True

    _patch_dependencies(monkeypatch, dispatch_stub, idle_monitor=idle_stub)
    endpoint_task = asyncio.create_task(websocket_chat_endpoint(websocket, initial_message=None))

    await receive_queue.put(_message({"type": "text", "prompt": "cancel"}))
    await receive_queue.put(_message({"type": "cancel"}))
    await receive_queue.put({"type": "websocket.disconnect"})

    await endpoint_task
    assert idle_cancelled.is_set()
