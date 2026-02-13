"""Unit tests for chart data persistence in chat messages."""

import pytest
from features.chat.db_models import ChatMessage
from features.chat.mappers import chat_message_to_dict
from features.chat.utils.history_payloads import (
    _extract_chart_data_from_tool_results,
    build_ai_message_payload,
)
from features.chat.utils.websocket_workflow_executor import StandardWorkflowOutcome


async def test_extract_chart_data_from_tool_results_empty():
    """Test extracting chart data from empty tool results."""
    result = _extract_chart_data_from_tool_results(None)
    assert result is None

    result = _extract_chart_data_from_tool_results([])
    assert result is None


async def test_extract_chart_data_from_tool_results_no_charts():
    """Test extracting chart data when no charts are present."""
    tool_results = [
        {"result": {"success": True, "some_other_data": "value"}},
        {"result": {"success": False}},
    ]
    result = _extract_chart_data_from_tool_results(tool_results)
    assert result is None


async def test_extract_chart_data_from_tool_results_with_charts():
    """Test extracting chart data when charts are present."""
    chart_payload = {
        "chart_id": "test-123",
        "chart_type": "bar",
        "title": "Test Chart",
        "data": {"datasets": [{"label": "Test", "data": [1, 2, 3]}]},
        "options": {"colors": ["#FF0000"]},
    }

    tool_results = [
        {"result": {"success": True, "chart_payload": chart_payload}},
        {"result": {"success": True, "some_other_data": "value"}},
    ]

    result = _extract_chart_data_from_tool_results(tool_results)
    assert result is not None
    assert len(result) == 1
    assert result[0] == chart_payload


async def test_extract_chart_data_from_tool_results_multiple_charts():
    """Test extracting multiple chart payloads."""
    chart_payload1 = {
        "chart_id": "chart-1",
        "chart_type": "bar",
        "title": "Chart 1",
    }
    chart_payload2 = {
        "chart_id": "chart-2",
        "chart_type": "pie",
        "title": "Chart 2",
    }

    tool_results = [
        {"result": {"success": True, "chart_payload": chart_payload1}},
        {"result": {"success": True, "chart_payload": chart_payload2}},
    ]

    result = _extract_chart_data_from_tool_results(tool_results)
    assert result is not None
    assert len(result) == 2
    assert result[0] == chart_payload1
    assert result[1] == chart_payload2


async def test_chart_message_model_has_chart_data_field():
    """Test that ChatMessage model has chart_data field."""
    # Test that we can create a ChatMessage with chart_data
    chart_payload = {
        "chart_id": "test-123",
        "chart_type": "bar",
        "title": "Test Chart",
        "data": {"datasets": [{"label": "Test", "data": [1, 2, 3]}]},
        "options": {"colors": ["#FF0000"]},
    }

    message = ChatMessage(
        session_id=1,
        sender="AI",
        message="Here's your chart:",
        chart_data=[chart_payload],
    )

    assert message.chart_data is not None
    assert len(message.chart_data) == 1
    assert message.chart_data[0]["chart_id"] == "test-123"


async def test_chart_data_can_be_none():
    """Test that chart_data can be None."""
    message = ChatMessage(
        session_id=1,
        sender="user",
        message="Regular message",
        chart_data=None,
    )

    assert message.chart_data is None


async def test_chat_message_mapping_includes_chart_data():
    """Ensure chart payloads are serialized for clients."""
    chart_payload = {"chart_id": "chart-1", "chart_type": "pie"}
    message = ChatMessage(
        session_id="session-1",
        sender="AI",
        message="with chart",
        chart_data=[chart_payload],
    )

    serialized = chat_message_to_dict(message)

    assert "chart_data" in serialized
    assert serialized["chart_data"][0]["chart_id"] == "chart-1"


async def test_ai_message_payload_includes_chart_payloads_field():
    """Ensure chart payloads collected on workflow are persisted."""
    workflow = StandardWorkflowOutcome(
        success=True,
        result={"text_response": "Here's your chart"},
        timings={},
        prompt_for_preview=None,
        chart_payloads=[{"chart_id": "chart-123", "chart_type": "bar"}],
    )

    payload = build_ai_message_payload(
        user_input={"ai_response": {}},
        settings={"text": {}},
        workflow=workflow,
        timings={},
    )

    assert payload is not None
    assert payload.chart_data
    assert payload.chart_data[0]["chart_id"] == "chart-123"


async def test_ai_message_payload_falls_back_to_result_chart_payloads():
    """Ensure result dict chart payloads are honored for backward compatibility."""
    workflow = StandardWorkflowOutcome(
        success=True,
        result={
            "text_response": "Fallback chart",
            "chart_payloads": [{"chart_id": "chart-999", "chart_type": "line"}],
        },
        timings={},
        prompt_for_preview=None,
    )

    payload = build_ai_message_payload(
        user_input={"ai_response": {}},
        settings={"text": {}},
        workflow=workflow,
        timings={},
    )

    assert payload is not None
    assert payload.chart_data
    assert payload.chart_data[0]["chart_id"] == "chart-999"
