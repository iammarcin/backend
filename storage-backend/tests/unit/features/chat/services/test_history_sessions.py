from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.exceptions import DatabaseError
from features.chat.schemas.requests import RemoveSessionRequest
from features.chat.services.history import sessions as history_sessions
from features.chat.services.history.base import HistoryRepositories


def _build_repositories(delete_return):
    sessions_repo = MagicMock()
    sessions_repo.delete_session = AsyncMock(return_value=delete_return)
    return HistoryRepositories(
        sessions=sessions_repo,
        messages=MagicMock(),
        prompts=MagicMock(),
        users=MagicMock(),
    )


@pytest.mark.anyio
async def test_remove_session_triggers_semantic_deletion(monkeypatch):
    observed_message_ids: list[list[int]] = []

    async def fake_queue(*, message_ids):
        observed_message_ids.append(list(message_ids))

    monkeypatch.setattr(
        history_sessions,
        "queue_semantic_deletion_tasks",
        fake_queue,
    )

    repositories = _build_repositories((True, [1, 2, 3]))
    request = RemoveSessionRequest(session_id="abc", customer_id=1)

    result = await history_sessions.remove_session(repositories, request)

    repositories.sessions.delete_session.assert_awaited_once_with(
        session_id="abc", customer_id=1
    )
    assert result.removed_count == 3
    assert result.message_ids == [1, 2, 3]
    assert observed_message_ids == [[1, 2, 3]]


@pytest.mark.anyio
async def test_remove_session_missing_session(monkeypatch):
    monkeypatch.setattr(
        history_sessions,
        "queue_semantic_deletion_tasks",
        AsyncMock(),
    )
    repositories = _build_repositories((False, []))
    request = RemoveSessionRequest(session_id="missing", customer_id=7)

    with pytest.raises(DatabaseError):
        await history_sessions.remove_session(repositories, request)

    repositories.sessions.delete_session.assert_awaited_once_with(
        session_id="missing", customer_id=7
    )
    history_sessions.queue_semantic_deletion_tasks.assert_not_called()
