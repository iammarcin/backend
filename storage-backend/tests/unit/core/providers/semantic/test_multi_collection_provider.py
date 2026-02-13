"""Tests for multi-collection semantic provider wrapper."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.providers.semantic.multi_collection_provider import (
    MultiCollectionSemanticProvider,
)
from core.providers.semantic.schemas import SearchRequest


class StubCircuitBreaker:
    def __init__(self) -> None:
        self._attempts = 0

    def can_attempt(self) -> bool:
        return True

    def record_success(self) -> None:  # pragma: no cover - simple stub
        self._attempts += 1

    def record_failure(self) -> None:  # pragma: no cover - simple stub
        self._attempts += 1


def _build_primary_provider() -> SimpleNamespace:
    client = SimpleNamespace(
        upsert=AsyncMock(),
        delete=AsyncMock(),
        get_collections=AsyncMock(return_value=SimpleNamespace(collections=[])),
        create_payload_index=AsyncMock(),
        create_collection=AsyncMock(),
    )

    embedding_provider = SimpleNamespace(
        generate=AsyncMock(return_value=[0.1, 0.2]),
        generate_batch=AsyncMock(return_value=[[0.1], [0.2]]),
        dimensions=2,
    )
    sparse_provider = SimpleNamespace(generate=lambda _: {"indices": [0], "values": [1.0]})

    return SimpleNamespace(
        client=client,
        embedding_provider=embedding_provider,
        sparse_provider=sparse_provider,
        circuit_breaker=StubCircuitBreaker(),
        collection_name="chat_messages_prod_hybrid",
        search=AsyncMock(return_value=[]),
        health_check=AsyncMock(return_value={"healthy": True}),
        create_collection=AsyncMock(),
    )


@pytest.mark.anyio
async def test_dual_index_invokes_both_collections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "core.providers.semantic.qdrant_indexing.content_hash_exists",
        AsyncMock(return_value=False),
    )

    primary = _build_primary_provider()
    provider = MultiCollectionSemanticProvider(primary)

    await provider.index(1, "hello world", {"customer_id": 7})

    collections = [call.kwargs["collection_name"] for call in primary.client.upsert.await_args_list]
    assert provider.semantic_collection in collections
    assert provider.hybrid_collection in collections


@pytest.mark.anyio
async def test_delete_removes_from_both_collections(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _build_primary_provider()
    provider = MultiCollectionSemanticProvider(primary)

    await provider.delete(42)

    delete_calls = [call.kwargs["collection_name"] for call in primary.client.delete.await_args_list]
    assert provider.semantic_collection in delete_calls
    assert provider.hybrid_collection in delete_calls


@pytest.mark.anyio
async def test_search_delegates_to_primary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _build_primary_provider()
    provider = MultiCollectionSemanticProvider(primary)

    request = SearchRequest(query="hello", customer_id=1)

    await provider.search(request)

    primary.search.assert_awaited()
