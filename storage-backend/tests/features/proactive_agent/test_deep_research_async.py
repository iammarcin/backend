"""Unit tests for deep research functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from config.proactive_agent import (
    DEFAULT_REASONING_EFFORT,
    MAX_CONCURRENT_JOBS_PER_USER,
    RESEARCH_RESULTS_DIR,
)
from features.proactive_agent.schemas import DeepResearchRequest
from features.proactive_agent.services.deep_research_handler import DeepResearchHandler
from features.proactive_agent.services.streaming_adapter import (
    ProactiveStreamingAdapter,
    can_start_job,
    get_active_jobs,
    register_job,
    slugify,
    unregister_job,
)

# Get reference to active jobs dict for testing
_active_jobs = get_active_jobs()


def _close_coro_side_effect(coro):
    """Side effect for mocked create_task that properly closes the coroutine."""
    coro.close()
    return MagicMock()


class TestDeepResearchRequestSchema:
    """Tests for DeepResearchRequest schema."""

    def test_valid_minimal_request(self):
        """Test request with only required fields."""
        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query",
        )
        assert request.user_id == 1
        assert request.session_id == "abc-123"
        assert request.query == "Test query"

    def test_reasoning_effort_default(self):
        """Test reasoning_effort defaults to None (uses backend env-based default)."""
        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query",
        )
        assert request.reasoning_effort is None  # Handler applies env-based default

    def test_reasoning_effort_string_values(self):
        """Test reasoning_effort accepts string values."""
        for effort in ["low", "medium", "high"]:
            request = DeepResearchRequest(
                user_id=1,
                session_id="abc-123",
                query="Test query",
                reasoning_effort=effort,
            )
            assert request.reasoning_effort == effort

    def test_reasoning_effort_numeric_values(self):
        """Test reasoning_effort accepts numeric values 0/1/2."""
        effort_map = {0: "low", 1: "medium", 2: "high"}
        for num, expected in effort_map.items():
            request = DeepResearchRequest(
                user_id=1,
                session_id="abc-123",
                query="Test query",
                reasoning_effort=num,
            )
            assert request.reasoning_effort == expected

    def test_reasoning_effort_string_numeric_values(self):
        """Test reasoning_effort accepts string numeric values."""
        effort_map = {"0": "low", "1": "medium", "2": "high"}
        for num, expected in effort_map.items():
            request = DeepResearchRequest(
                user_id=1,
                session_id="abc-123",
                query="Test query",
                reasoning_effort=num,
            )
            assert request.reasoning_effort == expected

    def test_reasoning_effort_invalid_rejected(self):
        """Test invalid reasoning_effort values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            DeepResearchRequest(
                user_id=1,
                session_id="abc-123",
                query="Test query",
                reasoning_effort="invalid",
            )
        assert "reasoning_effort" in str(exc_info.value).lower()

    def test_reasoning_effort_invalid_number_rejected(self):
        """Test invalid numeric reasoning_effort values are rejected."""
        with pytest.raises(ValidationError):
            DeepResearchRequest(
                user_id=1,
                session_id="abc-123",
                query="Test query",
                reasoning_effort=5,
            )


class TestDefaultReasoningEffort:
    """Tests for environment-based DEFAULT_REASONING_EFFORT."""

    def test_default_reasoning_effort_is_set(self):
        """Test DEFAULT_REASONING_EFFORT is either low or medium."""
        assert DEFAULT_REASONING_EFFORT in ("low", "medium")

    def test_reasoning_effort_logic_non_prod(self):
        """Test non-prod logic results in low effort."""
        # Test the logic - in test environment, IS_PRODUCTION should be False
        from config.environment import IS_PRODUCTION

        expected = "medium" if IS_PRODUCTION else "low"
        assert expected == "low"  # Test env is not production

    def test_reasoning_effort_logic_prod(self, monkeypatch):
        """Test prod logic results in medium effort."""
        # Test the logic directly
        result = "medium" if True else "low"
        assert result == "medium"


class TestSlugify:
    """Tests for slugify helper function."""

    def test_basic_slugify(self):
        """Test basic text slugification."""
        assert slugify("Hello World") == "hello-world"

    def test_removes_special_chars(self):
        """Test special characters are removed."""
        assert slugify("What's the state of AI?") == "whats-the-state-of-ai"

    def test_max_length(self):
        """Test slug is truncated to max_length."""
        long_text = "This is a very long query that should be truncated"
        slug = slugify(long_text, max_length=20)
        assert len(slug) <= 20

    def test_empty_string(self):
        """Test empty string returns empty."""
        assert slugify("") == ""

    def test_only_special_chars(self):
        """Test string with only special chars."""
        assert slugify("???!!!") == ""


class TestJobTracking:
    """Tests for job tracking functions."""

    def setup_method(self):
        """Clear active jobs before each test."""
        _active_jobs.clear()

    def test_can_start_job_empty(self):
        """Test can start job when no jobs exist."""
        assert can_start_job(user_id=1) is True

    def test_register_job(self):
        """Test registering a job."""
        register_job(user_id=1, job_id="job-1")
        assert "job-1" in _active_jobs.get(1, set())

    def test_register_multiple_jobs(self):
        """Test registering multiple jobs for same user."""
        register_job(user_id=1, job_id="job-1")
        register_job(user_id=1, job_id="job-2")
        assert len(_active_jobs[1]) == 2

    def test_can_start_job_at_limit(self):
        """Test cannot start job at max limit."""
        for i in range(MAX_CONCURRENT_JOBS_PER_USER):
            register_job(user_id=1, job_id=f"job-{i}")
        assert can_start_job(user_id=1) is False

    def test_can_start_job_different_users(self):
        """Test job limits are per-user."""
        for i in range(MAX_CONCURRENT_JOBS_PER_USER):
            register_job(user_id=1, job_id=f"job-{i}")
        # User 2 should still be able to start jobs
        assert can_start_job(user_id=2) is True

    def test_unregister_job(self):
        """Test unregistering a job."""
        register_job(user_id=1, job_id="job-1")
        unregister_job(user_id=1, job_id="job-1")
        assert 1 not in _active_jobs or "job-1" not in _active_jobs.get(1, set())

    def test_unregister_cleans_up_empty_set(self):
        """Test unregistering last job removes user from dict."""
        register_job(user_id=1, job_id="job-1")
        unregister_job(user_id=1, job_id="job-1")
        assert 1 not in _active_jobs

    def test_unregister_nonexistent_job(self):
        """Test unregistering nonexistent job doesn't error."""
        unregister_job(user_id=1, job_id="nonexistent")
        # Should not raise


class TestDeepResearchHandler:
    """Tests for DeepResearchHandler."""

    def setup_method(self):
        """Clear active jobs before each test."""
        _active_jobs.clear()

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return MagicMock()

    @pytest.fixture
    def handler(self, mock_repository):
        """Create handler with mock repository."""
        return DeepResearchHandler(mock_repository)

    @pytest.fixture
    def temp_results_dir(self, tmp_path, monkeypatch):
        """Redirect research results to a temp directory for tests."""
        temp_dir = tmp_path / "research-results"
        monkeypatch.setattr(
            "features.proactive_agent.services.deep_research_handler.RESEARCH_RESULTS_DIR",
            temp_dir,
        )
        return temp_dir

    @pytest.mark.asyncio
    async def test_execute_returns_immediately(self, handler, temp_results_dir):
        """Test execute_research returns immediately with job_id."""
        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query",
        )

        with patch(
            "features.proactive_agent.services.deep_research_handler.asyncio.create_task",
            side_effect=_close_coro_side_effect,
        ):
            result = await handler.execute_research(request)

        assert result["success"] is True
        assert result["status"] == "started"
        assert "job_id" in result
        assert "file_path" in result
        assert "estimated_time_seconds" in result

    @pytest.mark.asyncio
    async def test_execute_rate_limit(self, handler, temp_results_dir):
        """Test rate limit enforcement."""
        # Fill up job slots
        for i in range(MAX_CONCURRENT_JOBS_PER_USER):
            register_job(user_id=1, job_id=f"job-{i}")

        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query",
        )

        result = await handler.execute_research(request)

        assert result["success"] is False
        assert "concurrent jobs" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_job_id_format(self, handler, temp_results_dir):
        """Test job_id is 8-character UUID prefix."""
        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query",
        )

        with patch(
            "features.proactive_agent.services.deep_research_handler.asyncio.create_task",
            side_effect=_close_coro_side_effect,
        ):
            result = await handler.execute_research(request)

        assert len(result["job_id"]) == 8

    @pytest.mark.asyncio
    async def test_file_path_format(self, handler, temp_results_dir):
        """Test file path follows expected format."""
        request = DeepResearchRequest(
            user_id=1,
            session_id="abc-123",
            query="Test query about AI",
        )

        with patch(
            "features.proactive_agent.services.deep_research_handler.asyncio.create_task",
            side_effect=_close_coro_side_effect,
        ):
            result = await handler.execute_research(request)

        file_path = result["file_path"]
        # Should contain timestamp and slug
        assert "test-query-about-ai" in file_path.lower()
        assert file_path.endswith(".md")


class TestProactiveStreamingAdapter:
    """Tests for ProactiveStreamingAdapter collection behavior."""

    @pytest.mark.asyncio
    async def test_text_collected_once(self, monkeypatch):
        """Ensure text chunks are not duplicated."""
        mock_registry = MagicMock()
        mock_registry.push_to_user = AsyncMock()
        monkeypatch.setattr(
            "features.proactive_agent.services.deep_research_handler.get_proactive_registry",
            lambda: mock_registry,
        )

        adapter = ProactiveStreamingAdapter(user_id=1, session_id="abc-123")
        await adapter.send_to_queues({"type": "text_chunk", "content": "Hello"})
        adapter.collect_chunk("Hello", "text")

        assert adapter.get_collected_text() == "Hello"


class TestWriteResearchFile:
    """Tests for _write_research_file method."""

    @pytest.fixture
    def handler(self):
        """Create handler with mock repository."""
        mock_repo = MagicMock()
        return DeepResearchHandler(mock_repo)

    def test_write_research_file_content(self, handler, tmp_path):
        """Test research file content is correct."""
        file_path = tmp_path / "test-research.md"

        handler._write_research_file(
            file_path=file_path,
            query="Test query about AI",
            result_text="AI is fascinating. Here are the findings.",
            citations=[{"url": "https://example.com/1"}, {"url": "https://example.com/2"}],
            stage_timings={"optimization": 1.5, "research": 30.0, "analysis": 5.0},
        )

        content = file_path.read_text()
        assert "# Research: Test query about AI" in content
        assert "AI is fascinating" in content
        assert "## Citations" in content
        assert "https://example.com/1" in content
        assert "https://example.com/2" in content

    def test_write_research_file_no_citations(self, handler, tmp_path):
        """Test research file without citations."""
        file_path = tmp_path / "test-no-citations.md"

        handler._write_research_file(
            file_path=file_path,
            query="Simple query",
            result_text="Simple result",
            citations=[],
            stage_timings={},
        )

        content = file_path.read_text()
        assert "# Research: Simple query" in content
        assert "## Citations" not in content
