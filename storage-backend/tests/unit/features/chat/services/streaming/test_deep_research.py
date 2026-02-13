from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.streaming.manager import StreamingManager
from features.chat.repositories.chat_sessions import ChatSessionRepository
from features.chat.services.streaming.collector import collect_streaming_chunks
from features.chat.services.streaming.events import (
    emit_deep_research_completed,
    emit_deep_research_started,
)
from features.chat.services.streaming.deep_research import DeepResearchOutcome
from features.chat.utils.model_swap import (
    get_provider_for_model,
    restore_model_config,
    save_model_config,
)


@pytest.mark.asyncio
async def test_collect_streaming_chunks_deep_research(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deep research flag should route to orchestrator and set collection flag."""

    def fake_stream_deep_research_response(**_: Any):
        async def _gen():
            yield "chunk-1"

        class _Wrapper:
            def __init__(self) -> None:
                self._generator = _gen()
                self.deep_research_outcome = {
                    "value": DeepResearchOutcome(
                        session_id="session-created",
                        optimized_prompt="Today is 2025-01-01\nDo research",
                        research_response="Report",
                        citations=[{"title": "Source", "url": "https://example.com"}],
                        stage_timings={"optimization": 0.5, "research": 0.5, "analysis": 0.5},
                        message_ids={"user_message_id": 1, "ai_message_id": 2},
                        notification_tagged=True,
                        analysis_chunks=[],
                    )
                }

            def __aiter__(self) -> "_Wrapper":
                return self

            async def __anext__(self) -> str:
                return await self._generator.__anext__()

        return _Wrapper()

    monkeypatch.setattr(
        "features.chat.services.streaming.deep_research.stream_deep_research_response",
        fake_stream_deep_research_response,
    )

    manager = StreamingManager()
    settings: Dict[str, Any] = {"text": {"deep_research_enabled": True}}

    collection = await collect_streaming_chunks(
        provider=object(),
        manager=manager,
        prompt_text="hello",
        model="gpt-4o",
        temperature=0.7,
        max_tokens=1024,
        system_prompt=None,
        settings=settings,
        timings={},
        messages=[{"role": "user", "content": "hi"}],
        customer_id=123,
        session_id="session-1",
    )

    assert collection.is_deep_research is True
    assert collection.chunks == ["chunk-1"]
    assert collection.reasoning_chunks == []
    assert collection.deep_research_metadata == {
        "session_id": "session-created",
        "citations": [{"title": "Source", "url": "https://example.com"}],
        "stage_timings": {"optimization": 0.5, "research": 0.5, "analysis": 0.5},
        "message_ids": {"user_message_id": 1, "ai_message_id": 2},
        "notification_tagged": True,
        "optimized_prompt": "Today is 2025-01-01\nDo research",
        "research_response": "Report",
        "analysis_response": "chunk-1",
    }


@pytest.mark.asyncio
async def test_deep_research_event_emission(monkeypatch: pytest.MonkeyPatch) -> None:
    """Convenience event helpers should forward deep research events."""

    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    await emit_deep_research_started(manager)
    await emit_deep_research_completed(manager, citations_count=5)

    assert manager.send_to_queues.await_count == 2
    started_event = manager.send_to_queues.await_args_list[0][0][0]
    completed_event = manager.send_to_queues.await_args_list[1][0][0]

    assert started_event["event_type"] == "deepResearch"
    assert started_event["content"]["type"] == "deepResearchStarted"
    assert completed_event["content"]["type"] == "deepResearchCompleted"
    assert completed_event["content"]["citationsCount"] == 5
    assert completed_event["content"]["tag"] == "notification"


@pytest.mark.asyncio
async def test_notification_tag_addition(monkeypatch: pytest.MonkeyPatch) -> None:
    """Notification tag helper should append without overwriting existing tags."""

    repo = ChatSessionRepository(session=MagicMock())
    existing_session = MagicMock()
    existing_session.tags = ["user-tag", "important"]

    repo.get_by_id = AsyncMock(return_value=existing_session)
    repo.update_session_metadata = AsyncMock()

    await repo.add_notification_tag(session_id="session-123", customer_id=42)

    repo.update_session_metadata.assert_awaited_once()
    tags: List[str] = repo.update_session_metadata.await_args.kwargs["tags"]
    assert "notification" in tags
    assert "user-tag" in tags
    assert "important" in tags


def test_model_swap_utility(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model swap utility should preserve original settings and return provider."""

    captured_settings: Dict[str, Any] = {}

    class DummyProvider:
        pass

    def fake_get_text_provider(settings: Dict[str, Any]):
        captured_settings["value"] = settings
        return DummyProvider()

    monkeypatch.setattr(
        "features.chat.utils.model_swap.get_text_provider", fake_get_text_provider
    )

    base_settings = {"text": {"model": "gpt-4o", "temperature": 0.7}}
    saved = save_model_config(base_settings)
    assert saved["model"] == "gpt-4o"
    assert saved["temperature"] == 0.7

    provider = get_provider_for_model(
        "sonar-deep-research", base_settings, enable_reasoning=True
    )

    assert isinstance(provider, DummyProvider)
    assert base_settings["text"]["model"] == "gpt-4o"
    assert captured_settings["value"]["text"]["model"] == "sonar-deep-research"
    assert captured_settings["value"]["text"]["enable_reasoning"] is True

    restored_settings = restore_model_config({"text": {}}, saved)
    assert restored_settings["text"]["model"] == "gpt-4o"
    assert restored_settings["text"]["temperature"] == 0.7
