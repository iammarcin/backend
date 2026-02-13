from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from features.semantic_search.services.summary_update_service import SummaryUpdateService


class FakeSummaryRepo:
    def __init__(self):
        self.db = SimpleNamespace(execute=AsyncMock())

    async def get_stale_summaries(self, **kwargs):
        return [("session-a", None)]


class FakeSessionRepo:
    async def get_by_id(self, session_id):
        return SimpleNamespace(customer_id=1)


class FakeMessageRepo:
    pass


class FakeSummaryService:
    async def generate_summary_for_session(self, session_id, customer_id):
        return {"session_id": session_id, "customer_id": customer_id}


class FakeIndexingService:
    def __init__(self):
        self.index_session = AsyncMock()


@pytest.mark.asyncio
async def test_regenerate_summary_success():
    service = SummaryUpdateService(
        summary_repo=FakeSummaryRepo(),
        session_repo=FakeSessionRepo(),
        message_repo=FakeMessageRepo(),
        summary_service=FakeSummaryService(),
        indexing_service=FakeIndexingService(),
    )

    result = await service.regenerate_summary("session-a")

    assert result["success"]
    assert result["summary"]["session_id"] == "session-a"


@pytest.mark.asyncio
async def test_find_stale_summaries_combines_sources(monkeypatch):
    summary_repo = FakeSummaryRepo()

    class FakeResult:
        def __init__(self, values):
            self._values = values

        def scalars(self):
            return iter(self._values)

        def __iter__(self):
            return iter(self._values)

    summary_repo.db.execute = AsyncMock(return_value=SimpleNamespace(scalars=lambda: iter(["session-b"])))

    service = SummaryUpdateService(
        summary_repo=summary_repo,
        session_repo=FakeSessionRepo(),
        message_repo=FakeMessageRepo(),
        summary_service=FakeSummaryService(),
        indexing_service=FakeIndexingService(),
    )
    monkeypatch.setattr(service, "_current_config_version", lambda: 2)

    stale_ids = await service.find_stale_summaries()

    assert sorted(stale_ids) == ["session-a", "session-b"]


@pytest.mark.asyncio
async def test_auto_update_stale_reports_counts(monkeypatch):
    service = SummaryUpdateService.__new__(SummaryUpdateService)
    service.find_stale_summaries = AsyncMock(return_value=["x", "y"])
    service.regenerate_batch = AsyncMock(return_value={"regenerated": 2, "failed": 0})

    result = await SummaryUpdateService.auto_update_stale(
        service,
        customer_id=None,
    )

    assert result["found"] == 2
    assert result["regenerated"] == 2
