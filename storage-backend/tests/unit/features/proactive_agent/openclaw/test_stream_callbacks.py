"""Unit tests for OpenClaw StreamCallbacks marker detection."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from features.proactive_agent.openclaw.stream_callbacks import StreamCallbacks
from features.proactive_agent.poller_stream.marker_detector import MarkerDetector


def _make_callbacks(marker_detector=None):
    """Create StreamCallbacks with mocked registry."""
    registry = AsyncMock()
    registry.push_to_user = AsyncMock()
    return StreamCallbacks(
        user_id=1,
        session_id="test-session",
        ai_character_name="sherlock",
        tts_settings=None,
        registry=registry,
        marker_detector=marker_detector,
    ), registry


# --- Marker detection tests (9) ---


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_chart_event",
    new_callable=AsyncMock,
)
@patch(
    "features.proactive_agent.dependencies.get_db_session_direct",
)
@patch(
    "features.proactive_agent.services.chart_handler.ChartHandler",
)
@patch(
    "features.proactive_agent.repositories.ProactiveAgentRepository",
)
async def test_on_tool_result_detects_chart_marker(
    mock_repo_cls, mock_chart_cls, mock_get_db, mock_handle_chart
):
    """Chart marker detected and handle_chart_event called."""
    # Set up async context manager for DB session
    mock_db = AsyncMock()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = 'Some output [SHERLOCK_CHART:v1]{"chart_type":"line","title":"Test"}[/SHERLOCK_CHART] done'

    await cb.on_tool_result("test_tool", result, is_error=False)

    mock_handle_chart.assert_called_once()
    call_data = mock_handle_chart.call_args[0][0]
    assert call_data == {"chart_data": {"chart_type": "line", "title": "Test"}}


@pytest.mark.asyncio
async def test_on_tool_result_cleans_markers_from_payload():
    """Markers are stripped from the tool_result payload sent to frontend."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = 'Before [SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[]}[/SHERLOCK_SCENE] After'

    with patch(
        "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
        new_callable=AsyncMock,
    ):
        await cb.on_tool_result("test_tool", result, is_error=False)

    # Verify the payload pushed to user has cleaned content
    registry.push_to_user.assert_called_once()
    pushed_payload = registry.push_to_user.call_args[0][1]
    tool_result = pushed_payload["data"]["tool_result"]
    assert "[SHERLOCK_SCENE:v1]" not in tool_result
    assert "Before" in tool_result
    assert "After" in tool_result


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
async def test_on_tool_result_detects_scene_marker(mock_handle_scene):
    """Scene marker detected and handle_scene_event called."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = '[SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[{"id":"c1"}]}[/SHERLOCK_SCENE]'

    await cb.on_tool_result("test_tool", result, is_error=False)

    mock_handle_scene.assert_called_once()
    call_data = mock_handle_scene.call_args[0][0]
    assert call_data == {"scene_data": {"scene_id": "s1", "components": [{"id": "c1"}]}}
    # Verify user_id and session_id passed
    assert mock_handle_scene.call_args[0][1] == 1
    assert mock_handle_scene.call_args[0][2] == "test-session"


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_component_update_event",
    new_callable=AsyncMock,
)
async def test_on_tool_result_detects_component_update_marker(mock_handle_cu):
    """Component update marker detected and handler called."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = '[SHERLOCK_COMPONENT_UPDATE:v1]{"component_id":"c1","content":"new"}[/SHERLOCK_COMPONENT_UPDATE]'

    await cb.on_tool_result("test_tool", result, is_error=False)

    mock_handle_cu.assert_called_once()
    call_data = mock_handle_cu.call_args[0][0]
    assert call_data == {"update_data": {"component_id": "c1", "content": "new"}}


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_research_event",
    new_callable=AsyncMock,
)
@patch(
    "features.proactive_agent.dependencies.get_db_session_direct",
)
@patch(
    "features.proactive_agent.services.deep_research_handler.DeepResearchHandler",
)
@patch(
    "features.proactive_agent.repositories.ProactiveAgentRepository",
)
async def test_on_tool_result_detects_research_marker(
    mock_repo_cls, mock_research_cls, mock_get_db, mock_handle_research
):
    """Research marker detected and handle_research_event called."""
    mock_db = AsyncMock()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = '[SHERLOCK_RESEARCH:v1]{"query":"test research"}[/SHERLOCK_RESEARCH]'

    await cb.on_tool_result("test_tool", result, is_error=False)

    mock_handle_research.assert_called_once()
    call_data = mock_handle_research.call_args[0][0]
    assert call_data == {"research_data": {"query": "test research"}}


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_chart_event",
    new_callable=AsyncMock,
)
@patch(
    "features.proactive_agent.dependencies.get_db_session_direct",
)
@patch(
    "features.proactive_agent.services.chart_handler.ChartHandler",
)
@patch(
    "features.proactive_agent.repositories.ProactiveAgentRepository",
)
async def test_on_tool_result_multiple_markers(
    mock_repo_cls, mock_chart_cls, mock_get_db, mock_handle_chart, mock_handle_scene
):
    """Multiple markers in one result — both handlers called, both stripped."""
    mock_db = AsyncMock()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = (
        'Start '
        '[SHERLOCK_CHART:v1]{"chart_type":"bar","title":"Sales"}[/SHERLOCK_CHART]'
        ' middle '
        '[SHERLOCK_SCENE:v1]{"scene_id":"s2","components":[]}[/SHERLOCK_SCENE]'
        ' end'
    )

    await cb.on_tool_result("test_tool", result, is_error=False)

    mock_handle_chart.assert_called_once()
    mock_handle_scene.assert_called_once()

    # Verify both markers stripped from payload
    pushed_payload = registry.push_to_user.call_args[0][1]
    tool_result = pushed_payload["data"]["tool_result"]
    assert "[SHERLOCK_CHART:v1]" not in tool_result
    assert "[SHERLOCK_SCENE:v1]" not in tool_result
    assert "Start" in tool_result
    assert "end" in tool_result


@pytest.mark.asyncio
async def test_on_tool_result_skips_markers_on_error():
    """When is_error=True, no marker detection occurs."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = '[SHERLOCK_CHART:v1]{"chart_type":"line","title":"Test"}[/SHERLOCK_CHART]'

    with patch(
        "features.proactive_agent.poller_stream.special_event_handlers.handle_chart_event",
        new_callable=AsyncMock,
    ) as mock_handle_chart:
        await cb.on_tool_result("test_tool", result, is_error=True)
        mock_handle_chart.assert_not_called()

    # Raw result passed through (markers NOT stripped)
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert "[SHERLOCK_CHART:v1]" in pushed_payload["data"]["tool_result"]


@pytest.mark.asyncio
async def test_on_tool_result_skips_markers_on_dict_result():
    """Dict results skip marker detection entirely."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = {"key": "value"}

    await cb.on_tool_result("test_tool", result, is_error=False)

    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["data"]["tool_result"] == {"key": "value"}


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
async def test_on_tool_result_no_crash_on_handler_failure(mock_handle_scene):
    """Handler failure doesn't crash on_tool_result — event still pushed."""
    mock_handle_scene.side_effect = RuntimeError("handler boom")

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = '[SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[]}[/SHERLOCK_SCENE] ok'

    # Should not raise
    await cb.on_tool_result("test_tool", result, is_error=False)

    # tool_result event still pushed to user
    registry.push_to_user.assert_called_once()
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["type"] == "tool_result"


# --- Skip-marker tests (Read tool parity) ---


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["Read", "read"])
async def test_on_tool_result_skips_markers_for_read_tool(tool_name):
    """Read tool output must not trigger marker detection (case-insensitive)."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = 'File contents [SHERLOCK_CHART:v1]{"chart_type":"line","title":"Test"}[/SHERLOCK_CHART] end'

    with patch(
        "features.proactive_agent.poller_stream.special_event_handlers.handle_chart_event",
        new_callable=AsyncMock,
    ) as mock_handle_chart:
        await cb.on_tool_result(tool_name, result, is_error=False)
        mock_handle_chart.assert_not_called()

    # Raw result passed through (markers NOT stripped)
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["data"]["tool_result"] == result
    assert "[SHERLOCK_CHART:v1]" in pushed_payload["data"]["tool_result"]


# --- Baseline tests (3) ---


@pytest.mark.asyncio
async def test_on_tool_result_pushes_event_without_markers():
    """Basic string result without markers is pushed as-is."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    result = "Simple tool output with no markers"

    await cb.on_tool_result("test_tool", result, is_error=False)

    registry.push_to_user.assert_called_once()
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["type"] == "tool_result"
    assert pushed_payload["data"]["tool_result"] == result
    assert pushed_payload["data"]["tool_name"] == "test_tool"
    assert pushed_payload["data"]["is_error"] is False


@pytest.mark.asyncio
async def test_on_text_chunk_pushes_event():
    """Text chunk pushed unchanged."""
    cb, registry = _make_callbacks(marker_detector=MarkerDetector())

    await cb.on_text_chunk("Hello world")

    registry.push_to_user.assert_called_once()
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["type"] == "text_chunk"
    assert pushed_payload["data"]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_on_tool_result_no_detection_without_marker_detector():
    """When marker_detector is None, markers pass through raw."""
    cb, registry = _make_callbacks(marker_detector=None)
    result = '[SHERLOCK_CHART:v1]{"chart_type":"line","title":"Test"}[/SHERLOCK_CHART]'

    await cb.on_tool_result("test_tool", result, is_error=False)

    # Markers NOT stripped — passed through raw
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["data"]["tool_result"] == result
    assert "[SHERLOCK_CHART:v1]" in pushed_payload["data"]["tool_result"]


# --- on_stream_end marker detection tests ---


def _mock_db_for_stream_end():
    """Set up DB mocks for on_stream_end tests (create_message + session)."""
    mock_db = AsyncMock()
    mock_message = MagicMock()
    mock_message.message_id = "msg-123"

    mock_repo = AsyncMock()
    mock_repo.create_message = AsyncMock(return_value=mock_message)

    return mock_db, mock_repo, mock_message


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_detects_scene_marker(
    mock_repo_cls, mock_get_db, mock_handle_scene
):
    """Scene marker in final_text triggers handler, DB gets cleaned text, stream_end has cleaned content."""
    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    final_text = 'Here is your overview [SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[{"id":"c1"}]}[/SHERLOCK_SCENE] enjoy!'

    await cb.on_stream_end("sess-1", "run-1", final_text)

    # Scene handler called
    mock_handle_scene.assert_called_once()
    call_data = mock_handle_scene.call_args[0][0]
    assert call_data == {"scene_data": {"scene_id": "s1", "components": [{"id": "c1"}]}}

    # DB message saved with cleaned text
    saved_content = mock_repo.create_message.call_args[1]["content"]
    assert "[SHERLOCK_SCENE:v1]" not in saved_content
    assert "Here is your overview" in saved_content
    assert "enjoy!" in saved_content

    # stream_end pushed with cleaned content
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["type"] == "stream_end"
    assert "[SHERLOCK_SCENE:v1]" not in pushed_payload["data"]["content"]
    assert "Here is your overview" in pushed_payload["data"]["content"]


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_chart_event",
    new_callable=AsyncMock,
)
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.services.chart_handler.ChartHandler")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_multiple_markers(
    mock_repo_cls, mock_chart_cls, mock_get_db, mock_handle_chart, mock_handle_scene
):
    """Multiple marker types in final_text — all detected, all stripped."""
    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    final_text = (
        'Intro '
        '[SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[]}[/SHERLOCK_SCENE]'
        ' middle '
        '[SHERLOCK_CHART:v1]{"chart_type":"pie","title":"Data"}[/SHERLOCK_CHART]'
        ' outro'
    )

    await cb.on_stream_end("sess-1", "run-1", final_text)

    mock_handle_scene.assert_called_once()
    mock_handle_chart.assert_called_once()

    # Both markers stripped from DB and stream_end
    saved_content = mock_repo.create_message.call_args[1]["content"]
    assert "[SHERLOCK_SCENE:v1]" not in saved_content
    assert "[SHERLOCK_CHART:v1]" not in saved_content
    assert "Intro" in saved_content
    assert "outro" in saved_content


@pytest.mark.asyncio
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_malformed_marker_no_crash(mock_repo_cls, mock_get_db):
    """Malformed marker JSON in final_text — no crash, text saved safely."""
    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    final_text = 'Text [SHERLOCK_CHART:v1]not valid json[/SHERLOCK_CHART] more text'

    # Should not raise
    await cb.on_stream_end("sess-1", "run-1", final_text)

    # Message still saved and stream_end still pushed
    mock_repo.create_message.assert_called_once()
    registry.push_to_user.assert_called_once()
    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["type"] == "stream_end"


@pytest.mark.asyncio
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_no_markers_passes_through(mock_repo_cls, mock_get_db):
    """final_text without markers saved and pushed as-is."""
    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    final_text = "Just a normal response with no markers."

    await cb.on_stream_end("sess-1", "run-1", final_text)

    saved_content = mock_repo.create_message.call_args[1]["content"]
    assert saved_content == final_text

    pushed_payload = registry.push_to_user.call_args[0][1]
    assert pushed_payload["data"]["content"] == final_text
    assert registry.push_to_user.call_args.kwargs["session_scoped"] is True


@pytest.mark.asyncio
@patch(
    "features.proactive_agent.poller_stream.special_event_handlers.handle_scene_event",
    new_callable=AsyncMock,
)
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_handler_failure_does_not_block(
    mock_repo_cls, mock_get_db, mock_handle_scene
):
    """Marker handler failure in stream_end doesn't block DB save or stream_end push."""
    mock_handle_scene.side_effect = RuntimeError("scene handler exploded")

    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=MarkerDetector())
    final_text = '[SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[]}[/SHERLOCK_SCENE] text'

    # Should not raise
    await cb.on_stream_end("sess-1", "run-1", final_text)

    # DB save still happened with cleaned text
    mock_repo.create_message.assert_called_once()
    # stream_end still pushed
    registry.push_to_user.assert_called_once()
    assert registry.push_to_user.call_args[0][1]["type"] == "stream_end"


@pytest.mark.asyncio
@patch("features.proactive_agent.dependencies.get_db_session_direct")
@patch("features.proactive_agent.repositories.ProactiveAgentRepository")
async def test_on_stream_end_no_detection_without_marker_detector(
    mock_repo_cls, mock_get_db
):
    """When marker_detector is None, final_text passes through raw."""
    mock_db, mock_repo, mock_message = _mock_db_for_stream_end()
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_repo_cls.return_value = mock_repo

    cb, registry = _make_callbacks(marker_detector=None)
    final_text = '[SHERLOCK_SCENE:v1]{"scene_id":"s1","components":[]}[/SHERLOCK_SCENE]'

    await cb.on_stream_end("sess-1", "run-1", final_text)

    # Raw text saved to DB (markers NOT stripped)
    saved_content = mock_repo.create_message.call_args[1]["content"]
    assert "[SHERLOCK_SCENE:v1]" in saved_content
