"""Tests for the ``session_scope`` context manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.mysql import AsyncSessionFactory, session_scope


pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend() -> str:
    """Limit AnyIO to the asyncio backend for these tests."""

    return "asyncio"


class _SentinelError(Exception):
    """Custom exception used to exercise rollback paths."""


async def test_session_scope_commits_on_success() -> None:
    """The context manager commits and closes the session on success."""

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    factory: AsyncSessionFactory = MagicMock(return_value=session)

    async with session_scope(factory) as provided:
        assert provided is session

    session.commit.assert_awaited_once_with()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once_with()


async def test_session_scope_rolls_back_and_reraises() -> None:
    """The context manager rolls back and closes the session on error."""

    session = MagicMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    factory: AsyncSessionFactory = MagicMock(return_value=session)

    with pytest.raises(_SentinelError):
        async with session_scope(factory):
            raise _SentinelError()

    session.commit.assert_not_called()
    session.rollback.assert_awaited()
    session.close.assert_awaited_once_with()
