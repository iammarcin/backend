"""Unit tests for standard workflow completion handling."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.streaming.manager import StreamingManager
from features.chat.utils.standard_executor import _handle_workflow_completion


@pytest.mark.asyncio
async def test_openclaw_result_skips_history_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenClaw workflows should not persist via standard history path."""
    persist_mock = AsyncMock()
    monkeypatch.setattr(
        "features.chat.utils.history_persistence_core.persist_workflow_result",
        persist_mock,
    )

    websocket = MagicMock()
    workflow_session = MagicMock()
    manager = StreamingManager()

    await _handle_workflow_completion(
        result={"openclaw": True, "success": True},
        workflow_session=workflow_session,
        websocket=websocket,
        data={"request_type": "audio", "user_input": {"prompt": []}},
        settings={},
        customer_id=1,
        manager=manager,
        timings={"start_time": 0.0},
        preview_payload=[],
        request_type="audio",
    )

    assert persist_mock.await_count == 0
