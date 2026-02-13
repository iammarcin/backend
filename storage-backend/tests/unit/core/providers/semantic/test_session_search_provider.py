from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.providers.semantic.session_search_provider import (
    SessionSearchProvider,
    SessionSearchType,
)
from core.exceptions import ProviderError


def build_provider():
    fake_client = SimpleNamespace()
    fake_client.query_points = AsyncMock()
    fake_client.close = AsyncMock()

    fake_embedding_provider = SimpleNamespace()
    fake_embedding_provider.generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

    provider = SessionSearchProvider(qdrant_client=fake_client, embedding_provider=fake_embedding_provider)
    return provider, fake_client, fake_embedding_provider


def test_generate_sparse_vector_filters_short_tokens():
    provider, _, _ = build_provider()
    vector = provider._generate_sparse_vector("AI is fun for business planning")
    assert len(vector.indices) == len(vector.values)
    # short tokens like "AI" and "is" should be filtered out
    assert len(vector.indices) >= 2


@pytest.mark.asyncio
async def test_search_dense_returns_payload():
    provider, fake_client, _ = build_provider()
    fake_client.query_points.return_value = SimpleNamespace(
        points=[
            SimpleNamespace(
                payload={
                    "session_id": "abc",
                    "customer_id": 1,
                    "summary": "Recap",
                    "message_count": 3,
                },
                score=0.87,
            )
        ]
    )

    results = await provider.search(
        query="project planning discussion",
        customer_id=1,
        search_type=SessionSearchType.DENSE,
        limit=5,
    )

    assert len(results) == 1
    assert results[0].to_dict()["session_id"] == "abc"
    fake_client.query_points.assert_awaited()


@pytest.mark.asyncio
async def test_search_raises_on_failure():
    provider, fake_client, _ = build_provider()
    fake_client.query_points.side_effect = RuntimeError("boom")

    with pytest.raises(ProviderError):
        await provider.search(
            query="test",
            customer_id=1,
            search_type=SessionSearchType.DENSE,
        )
