import sys
import types
from typing import Any

import pytest

from config.semantic_search import defaults as semantic_defaults


# Provide lightweight stubs for optional dependencies that may not be installed
# in the unit test environment.
if "qdrant_client" not in sys.modules:
    qdrant_module = types.ModuleType("qdrant_client")

    class _AsyncQdrantClient:  # pragma: no cover - import stub
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

    qdrant_module.AsyncQdrantClient = _AsyncQdrantClient

    models_module = types.ModuleType("qdrant_client.models")
    for attr in (
        "Distance",
        "FieldCondition",
        "Filter",
        "MatchAny",
        "MatchValue",
        "PayloadSchemaType",
        "PointIdsList",
        "PointStruct",
        "Range",
        "VectorParams",
    ):
        setattr(models_module, attr, type(attr, (), {}))

    qdrant_module.models = models_module
    sys.modules["qdrant_client"] = qdrant_module
    sys.modules["qdrant_client.models"] = models_module

if "tiktoken" not in sys.modules:
    tiktoken_module = types.ModuleType("tiktoken")

    class _StubEncoding:  # pragma: no cover - import stub
        def encode(self, text: str) -> list[int]:
            return [ord(char) for char in text]

        def decode(self, tokens: list[int]) -> str:
            return "".join(chr(token) for token in tokens)

    def get_encoding(_name: str) -> _StubEncoding:  # type: ignore[override]
        return _StubEncoding()

    tiktoken_module.get_encoding = get_encoding  # type: ignore[attr-defined]
    sys.modules["tiktoken"] = tiktoken_module

from features.semantic_search import prompt_enhancement
from features.semantic_search.prompt_enhancement import (
    SemanticEnhancementResult,
    enhance_prompt_with_semantic_context,
)


class DummyManager:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    async def send_to_queues(self, data, queue_type: str = "all") -> None:  # pragma: no cover - simple collector
        self.events.append(data)


class DummyTokenCounter:
    def count_tokens(self, text: str) -> int:
        return len(text.split())


class DummyFormatter:
    def __init__(self) -> None:
        self.token_counter = DummyTokenCounter()


class DummySemanticService:
    def __init__(self, context: str) -> None:
        self._context = context
        self.context_formatter = DummyFormatter()
        self.calls: list[dict[str, Any]] = []

    async def search_and_format_context(self, **kwargs: Any) -> str:
        self.calls.append(dict(kwargs))
        return self._context


class DummyRateLimiter:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed
        self.calls: list[int] = []

    def is_allowed(self, customer_id: int) -> bool:
        self.calls.append(customer_id)
        return self.allowed


@pytest.fixture(autouse=True)
def enable_semantic_search(monkeypatch: pytest.MonkeyPatch) -> DummyRateLimiter:
    """Ensure semantic search is enabled for tests regardless of env flags."""

    from features.semantic_search.utils import settings_parser

    monkeypatch.setattr(semantic_defaults, "ENABLED", True)

    limiter = DummyRateLimiter()

    monkeypatch.setattr(
        "features.semantic_search.rate_limiter.get_rate_limiter",
        lambda: limiter,
    )

    return limiter


@pytest.mark.asyncio
async def test_enhance_prompt_with_context_adds_metadata_and_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = (
        "Based on your previous conversations, here are relevant discussions:\n"
        "\n## Session (2024-05-01)\n"
        "**User:** Hello there!\n"
        "**Assistant:** Hi, how can I help you today?\n"
        "\n---\n\nCurrent question: Tell me about Python\n"
    )

    service = DummySemanticService(context)

    monkeypatch.setattr(
        prompt_enhancement,
        "get_semantic_search_service",
        lambda: service,
    )

    manager = DummyManager()
    prompt = "Tell me about Python"

    result = await enhance_prompt_with_semantic_context(
        prompt=prompt,
        customer_id=123,
        user_settings={"semantic": {"enabled": True}},
        manager=manager,
    )

    assert isinstance(result, SemanticEnhancementResult)
    assert result.context_added is True
    assert result.result_count == 2
    assert result.tokens_used == len(context.split())
    assert result.filters_applied is False
    assert result.error is None
    assert isinstance(result.enhanced_prompt, str)
    assert str(result.enhanced_prompt).endswith(prompt)

    metadata = result.metadata
    assert metadata["context_added"] is True
    assert metadata["result_count"] == 2
    assert metadata["tokens_used"] == len(context.split())
    assert metadata["filters_applied"] is False

    assert service.calls, "Expected semantic service to be invoked"
    call = service.calls[0]
    assert call["limit"] == semantic_defaults.DEFAULT_LIMIT
    assert call["score_threshold"] == semantic_defaults.DEFAULT_SCORE_THRESHOLD
    assert call["tags"] is None
    assert call["date_range"] is None
    assert call["message_type"] is None
    assert call["session_ids"] is None

    assert manager.events, "Expected custom event to be emitted"
    event = manager.events[0]
    assert event["type"] == "custom_event"
    assert event["content"]["type"] == "semanticContextAdded"
    assert event["content"]["result_count"] == 2
    assert event["content"]["tokens_used"] == len(context.split())
    assert "filters_applied" not in event["content"]


@pytest.mark.asyncio
async def test_enhance_prompt_with_filters_in_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = "context"
    service = DummySemanticService(context)

    monkeypatch.setattr(
        prompt_enhancement,
        "get_semantic_search_service",
        lambda: service,
    )

    manager = DummyManager()
    prompt = "Summarise"
    user_settings = {
        "semantic": {
            "enabled": True,
            "tags": ["business", "ideas"],
            "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
            "message_type": "user",
            "session_ids": ["abc123", 42],
            "limit": 5,
            "threshold": 0.8,
        }
    }

    result = await enhance_prompt_with_semantic_context(
        prompt=prompt,
        customer_id=321,
        user_settings=user_settings,
        manager=manager,
    )

    assert result.context_added is True
    assert result.filters_applied is True
    assert service.calls, "Expected semantic service to be invoked"
    call = service.calls[0]
    assert call["tags"] == ["business", "ideas"]
    assert call["date_range"] == ("2024-01-01", "2024-02-01")
    assert call["message_type"] == "user"
    assert call["session_ids"] == ["abc123", 42]
    assert call["limit"] == 5
    assert call["score_threshold"] == 0.8

    assert manager.events, "Expected event for semantic context"
    content = manager.events[0]["content"]
    filters_applied = content.get("filters_applied")
    assert filters_applied == {
        "tags": ["business", "ideas"],
        "date_range": {"start": "2024-01-01", "end": "2024-02-01"},
        "message_type": "user",
        "session_ids": ["abc123", 42],
    }


@pytest.mark.asyncio
async def test_enhance_prompt_with_invalid_filter_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = "context"
    service = DummySemanticService(context)

    monkeypatch.setattr(
        prompt_enhancement,
        "get_semantic_search_service",
        lambda: service,
    )

    manager = DummyManager()
    user_settings = {
        "semantic": {
            "enabled": True,
            "tags": "business",
            "date_range": {"start": "2024-01-01"},
            "message_type": "invalid",
            "session_ids": "oops",
            "limit": "bad",
            "threshold": "bad",
        }
    }

    prompt = "Hello"
    result = await enhance_prompt_with_semantic_context(
        prompt=prompt,
        customer_id=654,
        user_settings=user_settings,
        manager=manager,
    )

    assert result.context_added is True
    assert result.filters_applied is False
    call = service.calls[0]
    assert call["tags"] is None
    assert call["date_range"] is None
    assert call["message_type"] is None
    assert call["session_ids"] is None
    assert call["limit"] == semantic_defaults.DEFAULT_LIMIT
    assert call["score_threshold"] == semantic_defaults.DEFAULT_SCORE_THRESHOLD

    assert manager.events
    content = manager.events[0]["content"]
    assert "filters_applied" not in content


@pytest.mark.asyncio
async def test_enhance_prompt_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_called = False

    service = DummySemanticService("irrelevant")

    def fake_dependency() -> DummySemanticService:  # pragma: no cover - should not be invoked
        nonlocal dependency_called
        dependency_called = True
        return service

    monkeypatch.setattr(
        prompt_enhancement,
        "get_semantic_search_service",
        fake_dependency,
    )

    manager = DummyManager()
    prompt = "Hello"

    result = await enhance_prompt_with_semantic_context(
        prompt=prompt,
        customer_id=456,
        user_settings={"semantic": {"enabled": False}},
        manager=manager,
    )

    assert isinstance(result, SemanticEnhancementResult)
    assert result.context_added is False
    assert result.enhanced_prompt == prompt
    assert result.metadata == {
        "context_added": False,
        "result_count": 0,
        "tokens_used": 0,
        "filters_applied": False,
        "rate_limited": False,
    }
    assert manager.events == []
    assert dependency_called is False
    assert service.calls == []
