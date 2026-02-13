from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.exceptions import ProviderError, ValidationError
from features.semantic_search.services.session_summary_service import SessionSummaryService


class DummyMessage:
    def __init__(self, sender: str, message: str, created_at: datetime | None = None):
        self.sender = sender
        self.message = message
        self.created_at = created_at or datetime.now(UTC)


class InMemorySummary:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class DummySummaryRepo:
    def __init__(self):
        self.storage: dict[str, InMemorySummary] = {}

    async def get_by_session_id(self, session_id: str):
        return self.storage.get(session_id)

    async def create(self, **kwargs):
        summary = InMemorySummary(
            **kwargs,
            generated_at=datetime.now(UTC),
            last_updated=datetime.now(UTC),
        )
        self.storage[kwargs["session_id"]] = summary
        return summary

    async def update(self, session_id: str, **kwargs):
        summary = self.storage.get(session_id)
        if not summary:
            return None
        for key, value in kwargs.items():
            setattr(summary, key, value)
        summary.last_updated = datetime.now(UTC)
        return summary


class DummyMessageRepo:
    def __init__(self, messages: list[DummyMessage]):
        self.messages = messages

    async def get_messages_for_session(self, session_id: str):
        return self.messages


@pytest.fixture()
def text_provider(monkeypatch):
    provider = SimpleNamespace(provider_name="openai")
    provider.generate = AsyncMock()
    provider.get_model_config = lambda: SimpleNamespace(
        provider_name=provider.provider_name,
        model_name="test-model",
    )

    def _get_provider(_settings):
        return provider

    monkeypatch.setattr(
        "features.semantic_search.services.session_summary_service.get_text_provider",
        _get_provider,
    )
    return provider


def test_load_config_and_prompt(text_provider):
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo([]))
    assert service.config.summarization.model
    assert "You are summarizing a chat conversation" in service.prompt_template


def test_format_messages_truncates(text_provider):
    messages = [
        DummyMessage("user", "hello"),
        DummyMessage("AI", "response" * 500),
    ]
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo(messages))
    formatted = service._format_messages_for_prompt(messages)
    assert "User: hello" in formatted
    assert len(formatted.splitlines()) >= 2


@pytest.mark.asyncio
async def test_generate_summary_success(monkeypatch, text_provider):
    messages = [
        DummyMessage("user", "Idea 1"),
        DummyMessage("ai", "Let's discuss"),
    ]
    message_repo = DummyMessageRepo(messages)
    summary_repo = DummySummaryRepo()
    service = SessionSummaryService(summary_repo, message_repo)
    service.config.backfill.min_messages = 2
    text_provider.generate.return_value = SimpleNamespace(
        text="```json\n" +
        json.dumps(
            {
                "summary": "Detailed summary",
                "key_topics": ["topic-a"],
                "main_entities": ["Entity"],
            }
        ) +
        "\n```"
    )

    result = await service.generate_summary_for_session("session-1", 42)

    assert result["message_count"] == 2
    stored = await summary_repo.get_by_session_id("session-1")
    assert stored.summary == "Detailed summary"
    assert stored.key_topics == ["topic-a"]


@pytest.mark.asyncio
async def test_generate_summary_handles_json_errors(text_provider):
    messages = [DummyMessage("user", "Idea 1")]
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo(messages))
    service.config.backfill.min_messages = 1
    text_provider.generate.return_value = SimpleNamespace(text="not-json")

    with pytest.raises(ProviderError):
        await service.generate_summary_for_session("session-1", 1)


@pytest.mark.asyncio
async def test_generate_summary_requires_messages(text_provider):
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo([]))
    with pytest.raises(ValidationError):
        await service.generate_summary_for_session("session-1", 1)


@pytest.mark.asyncio
async def test_generate_summary_extracts_embedded_json(text_provider):
    messages = [DummyMessage("user", "Idea 1")]
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo(messages))
    service.config.backfill.min_messages = 1
    embedded = "Noise before JSON\n{\"summary\": \"ok\", \"key_topics\": [], \"main_entities\": []}\nMore text"
    text_provider.generate.return_value = SimpleNamespace(text=embedded)

    result = await service.generate_summary_for_session("session-1", 1)
    assert result["summary"] == "ok"


@pytest.mark.asyncio
async def test_generate_summary_respects_min_messages(text_provider):
    messages = [
        DummyMessage("user", "hi"),
    ]
    service = SessionSummaryService(DummySummaryRepo(), DummyMessageRepo(messages))
    service.config.backfill.min_messages = 2

    with pytest.raises(ValidationError):
        await service.generate_summary_for_session("session-1", 1)


@pytest.mark.asyncio
async def test_generate_summary_applies_provider_overrides(text_provider):
    text_provider.provider_name = "gemini"
    text_provider.get_model_config = lambda: SimpleNamespace(provider_name="gemini", model_name="gemini-flash")
    messages = [DummyMessage("user", "Idea 1"), DummyMessage("ai", "Ack")]
    summary_repo = DummySummaryRepo()
    message_repo = DummyMessageRepo(messages)
    overrides = {
        "tool_settings": {"code_execution": False, "google_search": {"enabled": False}},
        "builtin_tool_config": {"web_search": False, "code_interpreter": False},
        "disable_native_tools": True,
    }
    service = SessionSummaryService(
        summary_repo,
        message_repo,
        provider_overrides=overrides,
    )
    service.config.backfill.min_messages = 2
    text_provider.generate.return_value = SimpleNamespace(
        text=json.dumps({
            "summary": "ok",
            "key_topics": [],
            "main_entities": [],
        })
    )

    await service.generate_summary_for_session("session-override", 1)

    kwargs = text_provider.generate.await_args.kwargs
    assert kwargs["tool_settings"]["code_execution"] is False
    assert kwargs["tool_settings"]["google_search"]["enabled"] is False
    assert "builtin_tool_config" not in kwargs
    assert "disable_native_tools" not in kwargs


@pytest.mark.asyncio
async def test_generate_summary_filters_overrides_per_provider(text_provider):
    text_provider.provider_name = "anthropic"
    text_provider.get_model_config = lambda: SimpleNamespace(provider_name="anthropic", model_name="claude")
    messages = [DummyMessage("user", "Idea 1"), DummyMessage("ai", "Ack")]
    summary_repo = DummySummaryRepo()
    message_repo = DummyMessageRepo(messages)
    overrides = {
        "tool_settings": {"code_execution": False},
        "builtin_tool_config": {"web_search": False},
        "disable_native_tools": True,
    }
    service = SessionSummaryService(
        summary_repo,
        message_repo,
        provider_overrides=overrides,
    )
    service.config.backfill.min_messages = 2
    text_provider.generate.return_value = SimpleNamespace(
        text=json.dumps({
            "summary": "ok",
            "key_topics": [],
            "main_entities": [],
        })
    )

    await service.generate_summary_for_session("session-anthropic", 1)

    kwargs = text_provider.generate.await_args.kwargs
    assert "tool_settings" not in kwargs
    assert "builtin_tool_config" not in kwargs
    assert kwargs["disable_native_tools"] is True


@pytest.mark.asyncio
async def test_generate_summary_applies_openai_overrides(text_provider):
    text_provider.provider_name = "openai"
    text_provider.get_model_config = lambda: SimpleNamespace(provider_name="openai", model_name="gpt-5-mini")
    messages = [DummyMessage("user", "Idea 1"), DummyMessage("ai", "Ack")]
    summary_repo = DummySummaryRepo()
    message_repo = DummyMessageRepo(messages)
    overrides = {
        "tool_settings": {"code_execution": False, "google_search": {"enabled": False}},
        "builtin_tool_config": {"web_search": False, "code_interpreter": False},
        "disable_native_tools": True,
    }
    service = SessionSummaryService(
        summary_repo,
        message_repo,
        provider_overrides=overrides,
    )
    service.config.backfill.min_messages = 2
    text_provider.generate.return_value = SimpleNamespace(
        text=json.dumps({
            "summary": "ok",
            "key_topics": [],
            "main_entities": [],
        })
    )

    await service.generate_summary_for_session("session-openai", 1)

    kwargs = text_provider.generate.await_args.kwargs
    assert "tool_settings" not in kwargs
    assert kwargs["builtin_tool_config"]["web_search"] is False
    assert kwargs["builtin_tool_config"]["code_interpreter"] is False
    assert "disable_native_tools" not in kwargs
