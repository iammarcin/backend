"""Unit tests for workflow cancellation handling."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

if "qdrant_client" not in sys.modules:
    qdrant_module = types.ModuleType("qdrant_client")
    qdrant_module.AsyncQdrantClient = type("AsyncQdrantClient", (), {})
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

from features.chat.utils.websocket_dispatcher import dispatch_workflow
from features.chat.utils.websocket_runtime import WorkflowRuntime
from features.chat.utils.websocket_session import WorkflowSession
from features.chat.utils.websocket_workflow_executor import (
    run_clarification_workflow,
    run_standard_workflow,
)


class StubManager:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.signalled: bool = False
        self._token_counter = 0

    async def send_to_queues(self, payload, queue_type: str = "all") -> None:  # pragma: no cover - interface parity
        if isinstance(payload, dict):
            self.events.append(payload)

    def create_completion_token(self) -> str:
        self._token_counter += 1
        return f"token-{self._token_counter}"

    async def signal_completion(self, *, token: str) -> None:
        self.signalled = True


@pytest.mark.asyncio
async def test_run_standard_workflow_propagates_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = StubManager()
    cancellation_seen = asyncio.Event()

    async def fake_handle_text_workflow(**_: object) -> None:
        cancellation_seen.set()
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "features.chat.utils.standard_executor.handle_text_workflow",
        fake_handle_text_workflow,
    )

    with pytest.raises(asyncio.CancelledError):
        await run_standard_workflow(
            request_type="text",
            prompt=[{"type": "text", "text": "Hi"}],
            settings={"text": {}},
            customer_id=1,
            manager=manager,
            service=MagicMock(),
            stt_service=MagicMock(),
            websocket=MagicMock(),
            completion_token="token-1",
            data={"user_input": {}},
        )

    assert cancellation_seen.is_set()
    emitted_types = [event["type"] for event in manager.events]
    assert "text_completed" not in emitted_types
    assert "tts_not_requested" not in emitted_types
    # When cancelled, the workflow executor should NOT signal completion
    # The dispatcher handles completion signaling for cancelled workflows
    assert not manager.signalled


@pytest.mark.asyncio
async def test_run_clarification_workflow_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = StubManager()

    async def fake_clarification(**_: object) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(
        "features.chat.utils.clarification_executor.handle_clarification_workflow",
        fake_clarification,
    )

    with pytest.raises(asyncio.CancelledError):
        await run_clarification_workflow(
            data={"user_input": "hello"},
            settings={},
            customer_id=7,
            manager=manager,
            service=MagicMock(),
            completion_token="token-2",
        )

    assert all(event["type"] != "text_completed" for event in manager.events)
    assert manager.signalled


@pytest.mark.asyncio
async def test_dispatch_workflow_emits_cancelled_events(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = StubManager()
    runtime = WorkflowRuntime(manager=manager, tasks=[], frontend_queue=asyncio.Queue())

    async def fake_create_runtime(**_: object) -> WorkflowRuntime:
        return runtime

    async def fake_run_standard_workflow(**_: object) -> None:
        raise asyncio.CancelledError

    enhancement_result = SimpleNamespace(
        context_added=False,
        result_count=0,
        tokens_used=0,
        enhanced_prompt=[{"type": "text", "text": "Hi"}],
        metadata=None,
    )

    monkeypatch.setattr(
        "features.chat.utils.websocket_dispatcher.create_workflow_runtime",
        fake_create_runtime,
    )
    monkeypatch.setattr(
        "features.chat.utils.dispatcher_helpers.run_standard_workflow",
        fake_run_standard_workflow,
    )
    monkeypatch.setattr(
        "features.chat.utils.dispatcher_helpers.enhance_prompt_with_semantic_context",
        AsyncMock(return_value=enhancement_result),
    )

    websocket = AsyncMock()
    session = WorkflowSession(customer_id=1)
    data = {
        "type": "text",
        "prompt": [{"type": "text", "text": "hello"}],
        "settings": {"text": {}},
    }

    # After Milestone 6 fix, dispatch_workflow returns True on cancellation
    # instead of re-raising CancelledError
    result = await dispatch_workflow(
        data=data,
        session=session,
        websocket=websocket,
        service=MagicMock(),
        stt_service=MagicMock(),
    )

    # Verify cancellation was handled gracefully
    assert result is True

    # Verify cancellation events were emitted
    emitted_types = [event["type"] for event in manager.events]
    assert "cancelled" in emitted_types
    assert "text_completed" in emitted_types
    assert "tts_not_requested" in emitted_types
    # Note: "complete" event removed - client uses dual-flag logic with text_completed + tts_*
    assert manager.signalled
