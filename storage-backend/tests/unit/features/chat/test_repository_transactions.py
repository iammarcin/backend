"""Transactional behaviour for chat repositories."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from features.chat.repositories.chat_messages import ChatMessageRepository
from features.chat.repositories.chat_sessions import ChatSessionRepository


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend() -> str:
    """Limit AnyIO to the asyncio backend for these tests."""

    return "asyncio"


def _build_session_mock() -> AsyncSession:
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.rollback = AsyncMock()
    return session


async def test_chat_message_insert_flushes_without_commit() -> None:
    """``insert_message`` must flush but never commit the session."""

    session = _build_session_mock()
    repository = ChatMessageRepository(session)

    message = await repository.insert_message(
        session_id="session-123",
        customer_id=42,
        payload={"message": "hello", "sender": "User"},
        is_ai_message=False,
    )

    session.add.assert_called_once_with(message)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()


async def test_chat_session_create_flushes_without_commit() -> None:
    """``create_session`` must flush but never commit the session."""

    session = _build_session_mock()
    repository = ChatSessionRepository(session)

    chat_session = await repository.create_session(customer_id=7)

    session.add.assert_called_once_with(chat_session)
    session.flush.assert_awaited_once_with()
    session.commit.assert_not_called()
