from __future__ import annotations

import pytest

from features.semantic_search.schemas import SemanticSearchMode
from features.semantic_search.service import SemanticSearchService
from features.semantic_search.services.multi_tier_search_service import (
    MultiTierSearchConfig,
    MultiTierSearchService,
)
from features.semantic_search.services.session_search_service import SessionSearchService
from features.semantic_search.utils.context_formatter import ContextFormatter


class DummySessionSearch(SessionSearchService):
    def __init__(self, results):
        self._results = results

    async def search(self, **kwargs):
        return self._results


class DummyMessageService:
    async def search(self, **kwargs):
        class Result:
            message_id = 1
            content = "Discussed rollout plan"
            score = 0.88
            metadata = {"message_type": "assistant"}

        return [Result()]


@pytest.mark.asyncio
async def test_multi_tier_context_formatting():
    service = SemanticSearchService.__new__(SemanticSearchService)
    service.context_formatter = ContextFormatter()
    service.session_search_service = DummySessionSearch(
        [
            {
                "session_id": "abc",
                "summary": "Roadmap conversation",
                "key_topics": ["roadmap"],
                "main_entities": [],
                "score": 0.92,
            }
        ]
    )
    service.multi_tier_service = MultiTierSearchService(
        session_search_service=service.session_search_service,
        message_search_service=DummyMessageService(),
    )
    service._session_modes = {
        SemanticSearchMode.SESSION_SEMANTIC,
        SemanticSearchMode.SESSION_HYBRID,
    }

    context = await SemanticSearchService.search_and_format_context(
        service,
        query="roadmap",
        customer_id=1,
        search_mode="multi_tier",
        top_sessions=1,
        messages_per_session=1,
    )

    assert "Roadmap conversation" in context
    assert "Discussed rollout plan" in context
