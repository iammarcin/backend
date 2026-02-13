from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from features.semantic_search.schemas import SemanticSearchMode
from features.semantic_search.services.multi_tier_search_service import (
    MultiTierSearchConfig,
    MultiTierSearchService,
)


class StubSessionSearchService:
    def __init__(self, results):
        self.results = results

    async def search(self, **kwargs):
        return self.results


class StubMessageSearchService:
    def __init__(self, messages):
        self.messages = messages

    async def search(self, **kwargs):
        return self.messages


@pytest.mark.asyncio
async def test_multi_tier_search_service_returns_hierarchy():
    session_results = [
        {"session_id": "abc", "summary": "Talked roadmap", "key_topics": ["roadmap"], "main_entities": [], "score": 0.9}
    ]
    message_results = [
        SimpleNamespace(message_id=1, content="Plan release", score=0.85, metadata={"message_type": "assistant"})
    ]
    service = MultiTierSearchService(
        session_search_service=StubSessionSearchService(session_results),
        message_search_service=StubMessageSearchService(message_results),
    )

    config = MultiTierSearchConfig(
        top_sessions=1,
        messages_per_session=1,
        session_search_mode=SemanticSearchMode.SESSION_HYBRID,
        message_search_mode=SemanticSearchMode.HYBRID,
    )

    results = await service.search(query="roadmap", customer_id=1, config=config)

    assert len(results) == 1
    assert results[0].session_id == "abc"
    assert len(results[0].matched_messages) == 1
    assert results[0].matched_messages[0]["content"] == "Plan release"


@pytest.mark.asyncio
async def test_multi_tier_handles_no_sessions():
    service = MultiTierSearchService(
        session_search_service=StubSessionSearchService([]),
        message_search_service=StubMessageSearchService([]),
    )

    results = await service.search(
        query="anything",
        customer_id=1,
        config=MultiTierSearchConfig(top_sessions=1, messages_per_session=1),
    )

    assert results == []
