"""Tests for proactive agent session naming.

M6.5: Session naming triggered on first response in production.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from features.proactive_agent.utils.session_naming import (
    DEFAULT_SESSION_NAMES,
    should_trigger_session_naming,
    trigger_session_naming_background,
    schedule_session_naming,
)


class TestDefaultSessionNames:
    """Verify default session name detection."""

    def test_default_names_include_characters(self):
        """Default names include both character variations."""
        assert "Sherlock" in DEFAULT_SESSION_NAMES
        assert "Bugsy" in DEFAULT_SESSION_NAMES
        assert "sherlock" in DEFAULT_SESSION_NAMES
        assert "bugsy" in DEFAULT_SESSION_NAMES


class TestShouldTriggerSessionNaming:
    """Tests for should_trigger_session_naming check."""

    @pytest.mark.asyncio
    async def test_returns_false_in_non_production(self):
        """Should not trigger in non-production environments."""
        mock_repo = AsyncMock()

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", False):
            result = await should_trigger_session_naming(mock_repo, "test-session")
            assert result is False
            # Should not even check the session
            mock_repo.get_session_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_if_session_not_found(self):
        """Should return False if session doesn't exist."""
        mock_repo = AsyncMock()
        mock_repo.get_session_by_id.return_value = None

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", True):
            result = await should_trigger_session_naming(mock_repo, "nonexistent")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_if_custom_name_exists(self):
        """Should not trigger if session already has a custom name."""
        mock_session = MagicMock()
        mock_session.session_name = "My Custom Chat Topic"

        mock_repo = AsyncMock()
        mock_repo.get_session_by_id.return_value = mock_session

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", True):
            result = await should_trigger_session_naming(mock_repo, "test-session")
            assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_for_default_sherlock_name(self):
        """Should trigger if session has default 'Sherlock' name."""
        mock_session = MagicMock()
        mock_session.session_name = "Sherlock"

        mock_repo = AsyncMock()
        mock_repo.get_session_by_id.return_value = mock_session

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", True):
            result = await should_trigger_session_naming(mock_repo, "test-session")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_default_bugsy_name(self):
        """Should trigger if session has default 'Bugsy' name."""
        mock_session = MagicMock()
        mock_session.session_name = "Bugsy"

        mock_repo = AsyncMock()
        mock_repo.get_session_by_id.return_value = mock_session

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", True):
            result = await should_trigger_session_naming(mock_repo, "test-session")
            assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_for_empty_name(self):
        """Should trigger if session has empty name."""
        mock_session = MagicMock()
        mock_session.session_name = ""

        mock_repo = AsyncMock()
        mock_repo.get_session_by_id.return_value = mock_session

        with patch("features.proactive_agent.utils.session_naming.IS_PRODUCTION", True):
            result = await should_trigger_session_naming(mock_repo, "test-session")
            assert result is True


class TestTriggerSessionNamingBackground:
    """Tests for background session naming execution."""

    @pytest.mark.asyncio
    async def test_loads_session_and_generates_name(self):
        """Should load session, generate name, and persist it."""
        mock_session = MagicMock()
        mock_session.messages = [
            MagicMock(message="What is the weather today?"),
            MagicMock(message="The weather is sunny with 72°F."),
        ]

        mock_response = MagicMock()
        mock_response.text = "Weather Check"

        # Patch at the source location since imports are inside the function
        with patch(
            "features.chat.utils.session_name.load_session_for_prompt",
            new_callable=AsyncMock,
            return_value=mock_session,
        ) as mock_load:
            with patch(
                "features.chat.utils.session_name.build_prompt_from_session_history",
                return_value="Test prompt",
            ) as mock_build:
                with patch(
                    "features.chat.service.ChatService"
                ) as MockService:
                    with patch(
                        "features.chat.utils.session_name.request_session_name",
                        new_callable=AsyncMock,
                        return_value=mock_response,
                    ) as mock_request:
                        with patch(
                            "features.chat.utils.session_name.persist_session_name",
                            new_callable=AsyncMock,
                        ) as mock_persist:
                            await trigger_session_naming_background(
                                session_id="test-session",
                                customer_id=123,
                            )

                            mock_load.assert_called_once()
                            mock_build.assert_called_once_with(mock_session)
                            mock_request.assert_called_once()
                            mock_persist.assert_called_once()

                            # Verify the persisted name
                            persist_call = mock_persist.call_args
                            assert persist_call.kwargs["session_name"] == "Weather Check"

    @pytest.mark.asyncio
    async def test_handles_session_not_found_gracefully(self):
        """Should handle missing session without raising."""
        with patch(
            "features.chat.utils.session_name.load_session_for_prompt",
            new_callable=AsyncMock,
            return_value=None,
        ):
            # Should not raise
            await trigger_session_naming_background(
                session_id="nonexistent",
                customer_id=123,
            )

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self):
        """Should log but not propagate exceptions."""
        with patch(
            "features.chat.utils.session_name.load_session_for_prompt",
            new_callable=AsyncMock,
            side_effect=Exception("Database error"),
        ):
            # Should not raise
            await trigger_session_naming_background(
                session_id="test-session",
                customer_id=123,
            )


class TestScheduleSessionNaming:
    """Tests for fire-and-forget scheduling."""

    @pytest.mark.asyncio
    async def test_schedules_background_task(self):
        """Should schedule a background task for naming."""
        created_coro = None

        def capture_and_close_coro(coro, **kwargs):
            """Capture the coroutine and close it to avoid 'never awaited' warning."""
            nonlocal created_coro
            created_coro = coro
            coro.close()
            return MagicMock()

        with patch("asyncio.create_task", side_effect=capture_and_close_coro) as mock_create_task:
            schedule_session_naming("test-session", 123)

            mock_create_task.assert_called_once()
            call_kwargs = mock_create_task.call_args.kwargs
            assert "session_naming_test-session" in call_kwargs["name"]
