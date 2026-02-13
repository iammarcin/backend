from __future__ import annotations

import pytest

from features.semantic_search.schemas import SemanticSearchMode
from features.semantic_search.service import SemanticSearchService
from features.semantic_search.utils.context_formatter import ContextFormatter


class DummySessionSearch:
    def __init__(self, results):
        self.results = results

    async def search(self, **kwargs):
        return self.results


@pytest.mark.asyncio
async def test_session_search_context_formatting():
    service = SemanticSearchService.__new__(SemanticSearchService)
    service.context_formatter = ContextFormatter()
    service._session_modes = {
        SemanticSearchMode.SESSION_SEMANTIC,
        SemanticSearchMode.SESSION_HYBRID,
    }
    service.session_search_service = DummySessionSearch(
        [
            {
                "session_id": "alpha",
                "customer_id": 1,
                "summary": "Discussed AI strategy and launch plans.",
                "key_topics": ["ai", "strategy"],
                "main_entities": ["ProjectX"],
                "message_count": 7,
                "score": 0.91,
            }
        ]
    )
    service._session_modes = service._session_modes  # reuse defaults from class

    context = await SemanticSearchService.search_and_format_context(
        service,
        query="ai roadmap",
        customer_id=1,
        search_mode="session_hybrid",
    )

    assert "Relevant Conversations" in context
    assert "Discussed AI strategy" in context
