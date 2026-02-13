"""Tests for chart event helpers."""

from importlib import util
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.pydantic_schemas import ChartData, ChartPayload, ChartType, Dataset

MODULE_PATH = (
    Path(__file__).resolve().parents[4]
    / "features"
    / "chat"
    / "services"
    / "streaming"
    / "events"
    / "chart_events.py"
)
spec = util.spec_from_file_location("chart_events_testmod", MODULE_PATH)
chart_events = util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(chart_events)

emit_chart_generation_started = chart_events.emit_chart_generation_started
emit_chart_generated = chart_events.emit_chart_generated
emit_chart_error = chart_events.emit_chart_error


@pytest.mark.asyncio
async def test_emit_chart_generation_started():
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    await emit_chart_generation_started(manager, chart_type="bar", title="Sales")

    manager.send_to_queues.assert_called_once()
    payload = manager.send_to_queues.call_args.args[0]
    assert payload["event_type"] == "chartGenerationStarted"
    assert payload["content"]["chart_type"] == "bar"
    assert payload["content"]["title"] == "Sales"


@pytest.mark.asyncio
async def test_emit_chart_generated():
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    chart_payload = ChartPayload(
        chart_type=ChartType.LINE,
        title="Steps",
        data=ChartData(
            labels=["Mon", "Tue"],
            datasets=[Dataset(label="Steps", data=[1000, 2000])],
        ),
    )

    await emit_chart_generated(manager, chart_payload)

    manager.send_to_queues.assert_called_once()
    payload = manager.send_to_queues.call_args.args[0]
    assert payload["event_type"] == "chartGenerated"
    assert payload["content"]["chart_type"] == "line"
    assert payload["content"]["title"] == "Steps"


@pytest.mark.asyncio
async def test_emit_chart_error():
    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    await emit_chart_error(
        manager,
        error_message="boom",
        chart_type="pie",
        title="Failed chart",
    )

    manager.send_to_queues.assert_called_once()
    payload = manager.send_to_queues.call_args.args[0]
    assert payload["event_type"] == "chartError"
    assert payload["content"]["error"] == "boom"
    assert payload["content"]["chart_type"] == "pie"
    assert payload["content"]["title"] == "Failed chart"
