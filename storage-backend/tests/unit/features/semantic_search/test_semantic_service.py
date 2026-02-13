from __future__ import annotations

import asyncio

import pytest

from features.semantic_search.service import SemanticSearchService


class DummyProvider:
    def __init__(self, *, fail_ids: set[int] | None = None) -> None:
        self.fail_ids = fail_ids or set()
        self.deleted: list[int] = []

    async def delete(self, message_id: int) -> None:
        await asyncio.sleep(0)  # exercise async scheduling
        if message_id in self.fail_ids:
            raise RuntimeError("boom")
        self.deleted.append(message_id)


@pytest.fixture()
def semantic_service() -> tuple[SemanticSearchService, DummyProvider]:
    provider = DummyProvider()
    service = SemanticSearchService.__new__(SemanticSearchService)
    service.provider = provider  # type: ignore[attr-defined]
    service.context_formatter = None  # type: ignore[attr-defined]
    service.metadata_builder = None  # type: ignore[attr-defined]
    service._initialized = False  # type: ignore[attr-defined]
    return service, provider


@pytest.mark.asyncio
async def test_delete_messages_bulk_deduplicates_ids(semantic_service):
    service, provider = semantic_service

    success, failed = await service.delete_messages_bulk([1, 2, 2, 3, None])

    assert success == 3
    assert failed == 0
    assert provider.deleted == [1, 2, 3]


@pytest.mark.asyncio
async def test_delete_messages_bulk_counts_failures(monkeypatch):
    provider = DummyProvider(fail_ids={2})
    service = SemanticSearchService.__new__(SemanticSearchService)
    service.provider = provider  # type: ignore[attr-defined]
    service.context_formatter = None  # type: ignore[attr-defined]
    service.metadata_builder = None  # type: ignore[attr-defined]
    service._initialized = False  # type: ignore[attr-defined]

    success, failed = await service.delete_messages_bulk([1, 2, 3], concurrency=1)

    assert success == 2
    assert failed == 1
    assert provider.deleted == [1, 3]
