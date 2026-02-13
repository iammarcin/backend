"""Unit tests covering chat history retrieval helpers and formatting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import ValidationError
from features.chat.services.history.base import HistoryRepositories
from features.chat.services.history.service import ChatHistoryService
from features.chat.utils.chat_history_formatter import (
    extract_and_format_chat_history,
    get_provider_name_from_model,
)


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture()
def mock_repositories(monkeypatch: pytest.MonkeyPatch) -> HistoryRepositories:
    """Provide a patched repository bundle for ChatHistoryService."""

    sessions_repo = SimpleNamespace(
        create_session=AsyncMock(
            return_value=SimpleNamespace(session_id="session-123")
        )
    )

    insert_results = [
        SimpleNamespace(message_id=1),
        SimpleNamespace(message_id=2),
    ]
    messages_repo = SimpleNamespace(
        insert_message=AsyncMock(side_effect=insert_results),
    )

    prompts_repo = MagicMock()
    users_repo = MagicMock()

    repositories = HistoryRepositories(
        sessions=sessions_repo,
        messages=messages_repo,
        prompts=prompts_repo,
        users=users_repo,
    )

    monkeypatch.setattr(
        "features.chat.services.history.service.build_repositories",
        lambda session: repositories,
    )
    return repositories


class TestChatHistoryService:
    """Tests for the chat history service orchestration."""

    @pytest.mark.asyncio
    async def test_fork_session_from_history_inserts_messages(
        self, mock_repositories: HistoryRepositories
    ) -> None:
        """The service should create a session and insert each historical message."""

        service = ChatHistoryService(AsyncMock())
        history = [
            {"message": "My favourite colour is blue", "is_user_message": True},
            {
                "message": "Great choice! I'll remember that.",
                "is_user_message": False,
                "ai_character_name": "assistant",
            },
        ]

        session_id = await service.fork_session_from_history(
            customer_id=7,
            chat_history=history,
            session_name="Forked session",
            ai_character_name="assistant",
        )

        assert session_id == "session-123"
        assert mock_repositories.sessions.create_session.await_count == 1
        assert mock_repositories.messages.insert_message.await_count == len(history)

        first_call = mock_repositories.messages.insert_message.await_args_list[0].kwargs
        second_call = mock_repositories.messages.insert_message.await_args_list[1].kwargs

        assert first_call["is_ai_message"] is False
        assert second_call["is_ai_message"] is True
        assert second_call["payload"]["ai_character_name"] == "assistant"

    @pytest.mark.asyncio
    async def test_fork_session_from_history_empty_history_raises(
        self, mock_repositories: HistoryRepositories
    ) -> None:
        """Empty chat history payloads should be rejected."""

        service = ChatHistoryService(AsyncMock())

        with pytest.raises(ValidationError):
            await service.fork_session_from_history(
                customer_id=3,
                chat_history=[],
            )


class TestChatHistoryFormatting:
    """Tests for formatting helpers that prepare provider messages."""

    def test_extract_history_for_openai(self) -> None:
        """OpenAI formatting should include system prompt and history."""

        user_input = {
            "chat_history": [
                {"role": "user", "content": "Remember this fact."},
                {"role": "assistant", "content": "Noted."},
            ],
            "prompt": "What fact did I mention?",
        }

        messages = extract_and_format_chat_history(
            user_input=user_input,
            system_prompt="You are helpful.",
            provider_name="openai",
            model_name="gpt-4o-mini",
        )

        assert messages[0] == {"role": "system", "content": "You are helpful."}
        assert messages[1]["content"] == "Remember this fact."
        assert messages[-1]["content"] == "What fact did I mention?"

    def test_extract_history_for_anthropic(self) -> None:
        """Anthropic formatting keeps the system prompt separate."""

        user_input = {
            "chat_history": [
                {"role": "user", "content": "Track this detail."},
                {"role": "assistant", "content": "I'll remember."},
            ],
            "prompt": "What detail am I referring to?",
        }

        messages = extract_and_format_chat_history(
            user_input=user_input,
            system_prompt="Separate system",
            provider_name="anthropic",
            model_name="claude-haiku-4-5",
        )

        assert all(message["role"] != "system" for message in messages)
        assert messages[-1]["content"] == "What detail am I referring to?"
        assert len(messages) == 3

    def test_extract_history_for_gemini(self) -> None:
        """Gemini formatting should preserve history order and omit system prompt."""

        user_input = {
            "chat_history": [
                {"role": "user", "content": "Fact one."},
                {"role": "assistant", "content": "Acknowledged."},
            ],
            "prompt": "Repeat the fact",
        }

        messages = extract_and_format_chat_history(
            user_input=user_input,
            system_prompt="Gemini system",
            provider_name="gemini",
            model_name="gemini-flash-latest",
        )

        assert len(messages) == 3
        assert messages[0]["content"] == "Fact one."
        assert messages[-1]["content"] == "Repeat the fact"

    def test_get_provider_name_from_model(self) -> None:
        """Model names should map to their provider identifiers."""

        assert get_provider_name_from_model("claude-haiku-4-5") == "anthropic"
        assert get_provider_name_from_model("gpt-4o-mini") == "openai"
        assert get_provider_name_from_model("gemini-flash-latest") == "gemini"
        assert get_provider_name_from_model("deepseek-r1") == "deepseek"
