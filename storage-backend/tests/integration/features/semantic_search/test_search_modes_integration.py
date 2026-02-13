"""Integration-style tests for semantic search mode mapping."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from config.semantic_search.utils import get_collection_for_mode
from core.providers.semantic.schemas import SearchResult
from features.semantic_search.service import SemanticSearchService


class DummyManager:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def send_to_queues(self, payload, queue_type: str = "all") -> None:  # pragma: no cover - helper
        self.events.append(payload)


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["semantic", "hybrid", "keyword"])
async def test_search_maps_mode_to_collection(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    captured: dict[str, str] = {}

    async def fake_search(request):
        captured["mode"] = request.search_mode
        captured["collection"] = request.collection_name
        return []

    stub_provider = SimpleNamespace(search=AsyncMock(side_effect=fake_search))

    monkeypatch.setattr(
        "features.semantic_search.service.base.get_semantic_provider",
        lambda: stub_provider,
    )

    service = SemanticSearchService()

    await service.search(query="hello", customer_id=1, search_mode=mode)

    assert captured["mode"] == mode
    assert captured["collection"] == get_collection_for_mode(mode)


@pytest.mark.anyio
async def test_search_and_format_context_passes_search_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str] = {}
    results = [
        SearchResult(message_id=1, content="hello world", score=0.9, metadata={}),
    ]

    async def fake_search(request):
        captured["mode"] = request.search_mode
        captured["collection"] = request.collection_name
        return results

    stub_provider = SimpleNamespace(search=AsyncMock(side_effect=fake_search))

    monkeypatch.setattr(
        "features.semantic_search.service.base.get_semantic_provider",
        lambda: stub_provider,
    )

    service = SemanticSearchService()
    service.context_formatter = SimpleNamespace(
        format_results=lambda **_: "context",
        token_counter=SimpleNamespace(count_tokens=lambda _: 0),
    )

    context = await service.search_and_format_context(
        query="hi",
        customer_id=5,
        search_mode="semantic",
    )

    assert context == "context"
    assert captured["mode"] == "semantic"
    assert captured["collection"] == get_collection_for_mode("semantic")


@pytest.mark.anyio
async def test_search_and_format_context_emits_scores_event(monkeypatch: pytest.MonkeyPatch) -> None:
    results = [
        SearchResult(message_id=1, content="hello world", score=0.9, metadata={}),
        SearchResult(message_id=2, content="more context", score=0.6, metadata={}),
    ]

    stub_provider = SimpleNamespace(search=AsyncMock(return_value=results))

    monkeypatch.setattr(
        "features.semantic_search.service.base.get_semantic_provider",
        lambda: stub_provider,
    )

    service = SemanticSearchService()
    service.context_formatter = SimpleNamespace(
        format_results=lambda **kwargs: "context block",
        token_counter=SimpleNamespace(count_tokens=lambda _: 10),
    )

    manager = DummyManager()

    context = await service.search_and_format_context(
        query="hi",
        customer_id=9,
        manager=manager,
    )

    assert context == "context block"
    assert manager.events, "Expected semantic search score event"
    event = manager.events[0]
    assert event["type"] == "custom_event"
    content = event["content"]
    assert content["type"] == "semanticSearchScores"
    assert content["result_count"] == len(results)
    assert content["top_scores"] == [f"{r.score:.3f}" for r in results[:5]]
