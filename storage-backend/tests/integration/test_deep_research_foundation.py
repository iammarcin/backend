from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_deep_research_foundation_integration() -> None:
    """Ensure deep research foundation modules are importable."""

    from features.chat.services.streaming.deep_research import stream_deep_research_response
    from features.chat.services.streaming.events import emit_deep_research_started
    from features.chat.utils.model_swap import get_provider_for_model

    assert callable(stream_deep_research_response)
    assert callable(emit_deep_research_started)
    assert callable(get_provider_for_model)
