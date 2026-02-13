"""Tests for Qdrant indexing helpers."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.providers.semantic import qdrant_indexing as indexing


class StubCircuitBreaker:
    def can_attempt(self) -> bool:  # pragma: no cover - simple stub
        return True

    def record_failure(self) -> None:  # pragma: no cover - unused
        pass

    def record_success(self) -> None:  # pragma: no cover - unused
        pass


class StubProvider:
    def __init__(self) -> None:
        self.client = SimpleNamespace(
            scroll=AsyncMock(),
            upsert=AsyncMock(),
        )
        self.embedding_provider = SimpleNamespace(
            generate=AsyncMock(return_value=[0.1, 0.2]),
            generate_batch=AsyncMock(return_value=[[0.1], [0.2]]),
        )
        self.sparse_provider = SimpleNamespace(
            generate=lambda _: {"indices": [0], "values": [1.0]}
        )
        self.collection_name = "test"
        self.circuit_breaker = StubCircuitBreaker()
        self.logger = logging.getLogger("test")


@pytest.mark.anyio
async def test_index_skips_when_hash_exists() -> None:
    provider = StubProvider()
    provider.client.scroll.return_value = ([SimpleNamespace(id=99)], None)

    await indexing.index_message(
        provider,
        message_id=1,
        content="duplicate content",
        metadata={"customer_id": 42},
    )

    provider.client.upsert.assert_not_awaited()
    provider.embedding_provider.generate.assert_not_awaited()


@pytest.mark.anyio
async def test_bulk_index_filters_duplicates() -> None:
    provider = StubProvider()

    # Only unique messages should trigger hash lookup
    provider.client.scroll.side_effect = [
        ([], None),  # first unique message
        ([], None),  # second unique message
    ]

    messages = [
        (1, "same content", {"customer_id": 7}),
        (2, "same content", {"customer_id": 7}),  # batch-local duplicate
        (3, "different content", {"customer_id": 7}),
    ]

    await indexing.bulk_index(provider, messages)

    # Only two remote checks: first and third messages
    assert provider.client.scroll.await_count == 2
    provider.embedding_provider.generate_batch.assert_awaited()
    provider.client.upsert.assert_awaited()

    # Ensure Qdrant receives exactly two points (unique contents)
    upsert_call = provider.client.upsert.await_args
    points = upsert_call.kwargs["points"]
    assert len(points) == 2
    payload_hashes = {point.payload.get("content_hash") for point in points}
    assert len(payload_hashes) == 2
