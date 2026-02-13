"""Unit tests for ProactiveAgentRepository."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from features.proactive_agent.repositories.proactive_agent_repository import (
    ProactiveAgentRepository,
)


@pytest.mark.asyncio
async def test_get_or_create_session_returns_existing_with_mismatched_character():
    repo = ProactiveAgentRepository(session=MagicMock())
    existing = MagicMock()
    existing.session_id = "session-123"
    existing.ai_character_name = "bugsy"

    repo._chat_session_repo = MagicMock()
    repo._chat_session_repo.get_by_id = AsyncMock(return_value=existing)
    repo._chat_session_repo.create_session = AsyncMock()
    repo._chat_session_repo.get_or_create_for_character = AsyncMock()

    result = await repo.get_or_create_session(
        user_id=55,
        session_id="session-123",
        ai_character_name="sherlock",
    )

    assert result is existing
    repo._chat_session_repo.create_session.assert_not_called()
    repo._chat_session_repo.get_or_create_for_character.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_session_creates_with_provided_id_when_missing():
    repo = ProactiveAgentRepository(session=MagicMock())
    created = MagicMock()

    repo._chat_session_repo = MagicMock()
    repo._chat_session_repo.get_by_id = AsyncMock(return_value=None)
    repo._chat_session_repo.create_session = AsyncMock(return_value=created)
    repo._chat_session_repo.get_or_create_for_character = AsyncMock()

    result = await repo.get_or_create_session(
        user_id=55,
        session_id="session-abc",
        ai_character_name="sherlock",
    )

    assert result is created
    repo._chat_session_repo.create_session.assert_awaited_once_with(
        customer_id=55,
        session_name="Sherlock",
        ai_character_name="sherlock",
        session_id="session-abc",
    )
    repo._chat_session_repo.get_or_create_for_character.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_session_creates_new_when_id_missing():
    repo = ProactiveAgentRepository(session=MagicMock())
    created = MagicMock()

    repo._chat_session_repo = MagicMock()
    repo._chat_session_repo.create_session = AsyncMock(return_value=created)
    repo._chat_session_repo.get_or_create_for_character = AsyncMock()

    result = await repo.get_or_create_session(
        user_id=55,
        session_id=None,
        ai_character_name="bugsy",
    )

    assert result is created
    repo._chat_session_repo.create_session.assert_awaited_once_with(
        customer_id=55,
        session_name="Bugsy",
        ai_character_name="bugsy",
    )
    repo._chat_session_repo.get_or_create_for_character.assert_not_called()


@pytest.mark.asyncio
async def test_update_message_audio_url_updates_file_locations():
    repo = ProactiveAgentRepository(session=MagicMock())
    message = MagicMock()
    message.message_id = 10
    message.customer_id = 123
    message.file_locations = ["existing.txt"]

    repo._chat_message_repo = MagicMock()
    repo._chat_message_repo.get_message_by_id = AsyncMock(return_value=message)
    repo._chat_message_repo.update_message = AsyncMock()

    await repo.update_message_audio_url(
        message_id=10,
        audio_file_url="https://audio.test/file.mp3",
    )

    repo._chat_message_repo.update_message.assert_called_once_with(
        message_id=10,
        customer_id=123,
        payload={"file_locations": ["https://audio.test/file.mp3", "existing.txt"]},
    )
