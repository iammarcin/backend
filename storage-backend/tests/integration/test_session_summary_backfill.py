from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.backfill_session_summaries import backfill_summaries


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_backfill_summaries_processes_batches(monkeypatch):
    processed: list[tuple[str, int]] = []

    class FakeSummaryRepo:
        def __init__(self, db):
            self.db = db

        async def get_sessions_without_summary(self, customer_id, min_messages, limit):
            return ["session-1", "session-2"]

    class FakeSessionRepo:
        def __init__(self, db):
            self.db = db

        async def get_by_id(self, session_id):
            return SimpleNamespace(customer_id=1)

    class FakeMessageRepo:
        def __init__(self, db):
            self.db = db

    class DummyService:
        def __init__(self, summary_repo, message_repo, **_):
            self.summary_repo = summary_repo
            self.message_repo = message_repo

        async def generate_summary_for_session(self, session_id, customer_id):
            processed.append((session_id, customer_id))
            return {"session_id": session_id}

    monkeypatch.setattr("scripts.backfill_session_summaries.SessionSummaryRepository", FakeSummaryRepo)
    monkeypatch.setattr("scripts.backfill_session_summaries.ChatSessionRepository", FakeSessionRepo)
    monkeypatch.setattr("scripts.backfill_session_summaries.ChatMessageRepository", FakeMessageRepo)
    monkeypatch.setattr("scripts.backfill_session_summaries.SessionSummaryService", DummyService)

    factory = lambda: FakeSession()

    result = await backfill_summaries(
        customer_id=1,
        limit=None,
        batch_size=1,
        min_messages=1,
        session_factory=factory,
    )

    assert result == {"created": 2, "failed": 0}
    assert processed == [("session-1", 1), ("session-2", 1)]
