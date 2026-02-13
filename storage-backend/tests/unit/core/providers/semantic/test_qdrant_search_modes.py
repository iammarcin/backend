"""Tests for multi-mode search provider behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.providers.semantic.qdrant import QdrantSemanticProvider
from core.providers.semantic.schemas import SearchRequest, SearchResult


def make_provider() -> QdrantSemanticProvider:
    client = SimpleNamespace()
    embedding_provider = SimpleNamespace(dimensions=1536)
    sparse_provider = SimpleNamespace()

    return QdrantSemanticProvider(
        client=client,  # type: ignore[arg-type]
        collection_name="test",
        embedding_provider=embedding_provider,  # type: ignore[arg-type]
        sparse_provider=sparse_provider,  # type: ignore[arg-type]
        timeout=0.1,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("mode", "method_name"),
    [
        ("hybrid", "_search_hybrid"),
        ("semantic", "_search_semantic_only"),
        ("keyword", "_search_keyword_only"),
    ],
)
async def test_search_dispatches_to_requested_mode(
    mode: str, method_name: str
) -> None:
    provider = make_provider()

    results = [SearchResult(message_id=1, content="test", score=0.5, metadata={})]

    for name in ("_search_hybrid", "_search_semantic_only", "_search_keyword_only"):
        mock = AsyncMock(return_value=results if name == method_name else [])
        setattr(provider.search_engine, name, mock)

    request = SearchRequest(query="hello", customer_id=1, search_mode=mode)

    response = await provider.search(request)
    assert response == results

    for name in ("_search_hybrid", "_search_semantic_only", "_search_keyword_only"):
        mock = getattr(provider.search_engine, name)
        if name == method_name:
            assert mock.await_count == 1
        else:
            assert mock.await_count == 0


def test_search_request_invalid_mode() -> None:
    with pytest.raises(ValueError, match="Invalid search_mode"):
        SearchRequest(query="hi", customer_id=1, search_mode="invalid")
