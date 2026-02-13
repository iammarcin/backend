import asyncio
from dataclasses import replace
from typing import Any

import pytest

from core.config import Settings
from core.exceptions import ConfigurationError
from features.chat.services.history import semantic_indexing


@pytest.mark.anyio
async def test_queue_semantic_deletion_tasks_enqueues_delete_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded_ids: list[int] = []

    class StubService:
        async def delete_message(self, message_id: int) -> None:  # pragma: no cover - simple stub
            recorded_ids.append(message_id)

    async def stub_dependency() -> StubService:
        return StubService()

    created_tasks: list[asyncio.Task[Any]] = []
    loop = asyncio.get_running_loop()

    def capture_task(coro):  # pragma: no cover - exercised indirectly
        task = loop.create_task(coro)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(
        semantic_indexing, "get_semantic_search_service_dependency", stub_dependency
    )
    monkeypatch.setattr(semantic_indexing, "settings", replace(semantic_indexing.settings, semantic_search_indexing_enabled=True))
    monkeypatch.setattr(semantic_indexing.asyncio, "create_task", capture_task)

    await semantic_indexing.queue_semantic_deletion_tasks(message_ids=[1, 2, 2])

    if created_tasks:
        await asyncio.gather(*created_tasks)

    assert recorded_ids == [1, 2, 2]


@pytest.mark.anyio
async def test_queue_semantic_deletion_tasks_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency_calls: list[str] = []

    async def stub_dependency() -> None:
        dependency_calls.append("called")
        return None

    monkeypatch.setattr(
        semantic_indexing, "get_semantic_search_service_dependency", stub_dependency
    )
    monkeypatch.setattr(semantic_indexing, "settings", replace(semantic_indexing.settings, semantic_search_indexing_enabled=False))

    await semantic_indexing.queue_semantic_deletion_tasks(message_ids=[42])

    assert dependency_calls == []


@pytest.mark.anyio
async def test_queue_semantic_indexing_tasks_raises_when_misconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def stub_dependency():  # pragma: no cover - simple stub
        raise ConfigurationError("OPENAI_API_KEY missing", key="OPENAI_API_KEY")

    monkeypatch.setattr(
        semantic_indexing, "get_semantic_search_service_dependency", stub_dependency
    )
    monkeypatch.setattr(semantic_indexing, "settings", replace(semantic_indexing.settings, semantic_search_indexing_enabled=True))

    message = type("Message", (), {"message": "hello", "message_id": 1, "sender": "user"})()
    session_obj = type(
        "Session",
        (),
        {"tags": [], "session_name": "demo", "session_id": 1},
    )()

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        await semantic_indexing.queue_semantic_indexing_tasks(
            entries=[("index", message)],
            session_obj=session_obj,
            customer_id=1,
        )
