"""Integration tests for poller stream WebSocket pipeline.

Tests verify the complete flow from WebSocket connection through
event emission, following M2.5 specification.
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from features.proactive_agent.poller_stream.websocket_handler import router
from tests.fixtures.ndjson_samples import (
    CHART_RESPONSE,
    MULTI_TOOL_RESPONSE,
    SIMPLE_TEXT_RESPONSE,
    SPLIT_THINKING_RESPONSE,
    THINKING_RESPONSE,
    TOOL_USE_RESPONSE,
)

TEST_API_KEY = "test-integration-key"


@pytest.fixture
def mock_db_session():
    """Create a mock DB session context manager."""
    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_get_db_session_direct():
        yield mock_session

    return mock_get_db_session_direct


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    repo = AsyncMock()
    repo.update_session_claude_id = AsyncMock()
    repo.create_message = AsyncMock()
    return repo


@pytest.fixture
def mock_chart_handler():
    """Create mock chart handler."""
    handler = AsyncMock()
    handler.generate_chart = AsyncMock()
    return handler


@pytest.fixture
def mock_research_handler():
    """Create mock research handler."""
    handler = AsyncMock()
    handler.execute_research = AsyncMock()
    return handler


@pytest.fixture(autouse=True)
def patch_fresh_db(mock_db_session, mock_repository):
    """Patch fresh DB sessions used by EventEmitter methods.

    EventEmitter's _update_session_id, finalize, and _handle_stream_end_with_fresh_db
    use lazy imports to get fresh DB connections. These must be patched at the
    source module to avoid hitting the real database in tests.
    """
    with patch(
        "features.proactive_agent.dependencies.get_db_session_direct",
        mock_db_session,
    ), patch(
        "features.proactive_agent.repositories.ProactiveAgentRepository",
        return_value=mock_repository,
    ), patch(
        "features.proactive_agent.poller_stream.event_emitter.should_trigger_session_naming",
        new_callable=AsyncMock,
        return_value=False,
    ):
        yield


@pytest.fixture
def app():
    """Create test app with poller stream router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create TestClient."""
    return TestClient(app)


@pytest.fixture
def valid_init():
    """Valid init message."""
    return {
        "type": "init",
        "user_id": 1,
        "session_id": "integration-test-session",
        "ai_character_name": "sherlock",
        "source": "text",
    }


class TestSimpleTextResponseFlow:
    """Integration tests for simple text responses."""

    def test_complete_text_flow(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Complete flow: connect -> init -> text chunks -> complete."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ) as mock_start:
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ) as mock_end:
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.handle_text_chunk"
                                    ) as mock_text:
                                        with client.websocket_connect(
                                            "/poller-stream",
                                            headers={"X-Internal-Api-Key": TEST_API_KEY},
                                        ) as ws:
                                            # Send init
                                            ws.send_json(valid_init)

                                            # Send NDJSON lines
                                            for line in SIMPLE_TEXT_RESPONSE:
                                                ws.send_text(line)

                                            # Send complete
                                            ws.send_json({"type": "complete", "exit_code": 0})

        # Verify stream lifecycle
        mock_start.assert_called_once()
        mock_end.assert_called_once()

        # Verify text chunks received
        assert mock_text.call_count >= 1

    def test_session_id_extracted_and_saved(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Claude session ID from NDJSON is saved to repository."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with client.websocket_connect(
                                        "/poller-stream",
                                        headers={"X-Internal-Api-Key": TEST_API_KEY},
                                    ) as ws:
                                        ws.send_json(valid_init)
                                        for line in SIMPLE_TEXT_RESPONSE:
                                            ws.send_text(line)
                                        ws.send_json({"type": "complete", "exit_code": 0})

        # Verify session ID was saved
        mock_repository.update_session_claude_id.assert_called_with(
            session_id="integration-test-session",
            claude_session_id="claude-session-1",
        )


class TestThinkingDetectionFlow:
    """Integration tests for thinking tag detection."""

    def test_thinking_chunks_emitted(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Thinking tags produce thinking_chunk events."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.handle_thinking_chunk"
                                    ) as mock_thinking:
                                        with patch(
                                            "features.proactive_agent.poller_stream.event_emitter.handle_text_chunk"
                                        ) as mock_text:
                                            with client.websocket_connect(
                                                "/poller-stream",
                                                headers={"X-Internal-Api-Key": TEST_API_KEY},
                                            ) as ws:
                                                ws.send_json(valid_init)
                                                for line in THINKING_RESPONSE:
                                                    ws.send_text(line)
                                                ws.send_json({"type": "complete", "exit_code": 0})

        # Verify both thinking and text chunks
        assert mock_thinking.call_count >= 1
        assert mock_text.call_count >= 1

    def test_split_thinking_tags_handled(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Thinking tags split across chunks are handled correctly."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.handle_thinking_chunk"
                                    ) as mock_thinking:
                                        with patch(
                                            "features.proactive_agent.poller_stream.event_emitter.handle_text_chunk"
                                        ) as mock_text:
                                            with client.websocket_connect(
                                                "/poller-stream",
                                                headers={"X-Internal-Api-Key": TEST_API_KEY},
                                            ) as ws:
                                                ws.send_json(valid_init)
                                                for line in SPLIT_THINKING_RESPONSE:
                                                    ws.send_text(line)
                                                ws.send_json({"type": "complete", "exit_code": 0})

        # Verify thinking was detected despite split tags
        assert mock_thinking.call_count >= 1
        assert mock_text.call_count >= 1


class TestToolUseFlow:
    """Integration tests for tool use handling."""

    def test_tool_start_and_result_emitted(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Tool use produces tool_start and tool_result events."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.handle_tool_start"
                                    ) as mock_tool_start:
                                        with patch(
                                            "features.proactive_agent.poller_stream.event_emitter.handle_tool_result"
                                        ) as mock_tool_result:
                                            with client.websocket_connect(
                                                "/poller-stream",
                                                headers={"X-Internal-Api-Key": TEST_API_KEY},
                                            ) as ws:
                                                ws.send_json(valid_init)
                                                for line in TOOL_USE_RESPONSE:
                                                    ws.send_text(line)
                                                ws.send_json({"type": "complete", "exit_code": 0})

        # Verify tool events
        mock_tool_start.assert_called_once()
        mock_tool_result.assert_called_once()

        # Verify tool name
        start_kwargs = mock_tool_start.call_args.kwargs
        assert start_kwargs["tool_name"] == "Bash"
        assert start_kwargs["tool_input"] == {"command": "date"}

    def test_multiple_tools_handled(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Multiple sequential tool uses are tracked correctly."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.handle_tool_start"
                                    ) as mock_tool_start:
                                        with patch(
                                            "features.proactive_agent.poller_stream.event_emitter.handle_tool_result"
                                        ) as mock_tool_result:
                                            with client.websocket_connect(
                                                "/poller-stream",
                                                headers={"X-Internal-Api-Key": TEST_API_KEY},
                                            ) as ws:
                                                ws.send_json(valid_init)
                                                for line in MULTI_TOOL_RESPONSE:
                                                    ws.send_text(line)
                                                ws.send_json({"type": "complete", "exit_code": 0})

        # Verify both tools tracked
        assert mock_tool_start.call_count == 2
        assert mock_tool_result.call_count == 2


class TestChartDetectionFlow:
    """Integration tests for chart marker detection."""

    def test_chart_marker_triggers_handler(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Chart marker in tool result triggers chart handler."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with client.websocket_connect(
                                        "/poller-stream",
                                        headers={"X-Internal-Api-Key": TEST_API_KEY},
                                    ) as ws:
                                        ws.send_json(valid_init)
                                        for line in CHART_RESPONSE:
                                            ws.send_text(line)
                                        ws.send_json({"type": "complete", "exit_code": 0})

        # Verify chart handler called
        mock_chart_handler.generate_chart.assert_called_once()


class TestErrorHandlingFlow:
    """Integration tests for error scenarios."""

    def test_error_message_triggers_error_flow(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """Error message from poller triggers error emission."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ):
                                    with patch(
                                        "features.proactive_agent.poller_stream.event_emitter.get_proactive_registry"
                                    ) as mock_registry:
                                        mock_reg_instance = AsyncMock()
                                        mock_registry.return_value = mock_reg_instance

                                        with client.websocket_connect(
                                            "/poller-stream",
                                            headers={"X-Internal-Api-Key": TEST_API_KEY},
                                        ) as ws:
                                            ws.send_json(valid_init)
                                            # Start streaming
                                            ws.send_text('{"type": "system", "session_id": "x"}')
                                            # Then send error
                                            ws.send_json({
                                                "type": "error",
                                                "code": "rate_limit",
                                                "message": "429 Too Many Requests",
                                            })

        # Verify stream_error was pushed
        mock_reg_instance.push_to_user.assert_called()
        call_kwargs = mock_reg_instance.push_to_user.call_args.kwargs
        assert call_kwargs["message"]["type"] == "stream_error"
        assert call_kwargs["message"]["data"]["code"] == "rate_limit"


class TestStreamEndContent:
    """Integration tests for stream_end content accumulation."""

    def test_stream_end_receives_accumulated_content(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """stream_end is called with accumulated text content."""
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ) as mock_end:
                                    with client.websocket_connect(
                                        "/poller-stream",
                                        headers={"X-Internal-Api-Key": TEST_API_KEY},
                                    ) as ws:
                                        ws.send_json(valid_init)
                                        for line in SIMPLE_TEXT_RESPONSE:
                                            ws.send_text(line)
                                        ws.send_json({"type": "complete", "exit_code": 0})

        # Verify stream_end was called with content
        mock_end.assert_called_once()
        call_kwargs = mock_end.call_args.kwargs
        assert "Hello" in call_kwargs["full_content"]
        assert "world" in call_kwargs["full_content"]

    def test_full_content_includes_thinking_tags_for_ai_reasoning_extraction(
        self, client, valid_init, mock_db_session, mock_repository,
        mock_chart_handler, mock_research_handler
    ):
        """full_content includes thinking tags so handle_stream_end can extract ai_reasoning.

        M6.2 Bug Fix: Previously, websocket_handler passed get_clean_text() which stripped
        thinking tags. This caused ai_reasoning to always be empty since lifecycle_handlers
        couldn't extract tags from already-stripped content.

        Now we pass get_accumulated_text() which preserves tags, allowing lifecycle_handlers
        to correctly populate ai_reasoning.
        """
        with patch(
            "features.proactive_agent.poller_stream.websocket_handler.INTERNAL_API_KEY",
            TEST_API_KEY,
        ):
            with patch(
                "features.proactive_agent.poller_stream.websocket_handler.get_db_session_direct",
                mock_db_session,
            ):
                with patch(
                    "features.proactive_agent.poller_stream.websocket_handler.ProactiveAgentRepository",
                    return_value=mock_repository,
                ):
                    with patch(
                        "features.proactive_agent.poller_stream.websocket_handler.ChartHandler",
                        return_value=mock_chart_handler,
                    ):
                        with patch(
                            "features.proactive_agent.poller_stream.websocket_handler.DeepResearchHandler",
                            return_value=mock_research_handler,
                        ):
                            with patch(
                                "features.proactive_agent.poller_stream.event_emitter.handle_stream_start"
                            ):
                                with patch(
                                    "features.proactive_agent.poller_stream.event_emitter.handle_stream_end"
                                ) as mock_end:
                                    with client.websocket_connect(
                                        "/poller-stream",
                                        headers={"X-Internal-Api-Key": TEST_API_KEY},
                                    ) as ws:
                                        ws.send_json(valid_init)
                                        for line in THINKING_RESPONSE:
                                            ws.send_text(line)
                                        ws.send_json({"type": "complete", "exit_code": 0})

        # Verify full_content includes thinking tags for extraction
        call_kwargs = mock_end.call_args.kwargs
        # Thinking tags must be present for ai_reasoning extraction
        assert "<thinking>" in call_kwargs["full_content"]
        assert "</thinking>" in call_kwargs["full_content"]
        assert "Let me think" in call_kwargs["full_content"]
        # Final answer also present
        assert "The answer is 42." in call_kwargs["full_content"]
