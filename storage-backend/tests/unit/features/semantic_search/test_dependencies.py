"""Unit tests for semantic search dependency behavior."""

from __future__ import annotations

import pytest
from dataclasses import replace

from config.semantic_search import defaults as semantic_defaults
from config.semantic_search import qdrant as qdrant_config
from core.clients import semantic as semantic_client
from core.config import Settings, settings as core_settings
from core.exceptions import ConfigurationError
from core.providers.semantic import factory as semantic_factory
from features.semantic_search import dependencies as deps_module
from features.semantic_search import service as service_module


@pytest.fixture(autouse=True)
def reset_semantic_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure singleton is cleared between tests."""

    monkeypatch.setattr(service_module, "_service_instance", None)
    monkeypatch.setattr(semantic_client, "_qdrant_client", None)
    monkeypatch.setattr(semantic_factory, "_PROVIDER_CACHE", {})


@pytest.mark.anyio
async def test_dependency_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_module, "settings", replace(deps_module.settings, semantic_search_enabled=False))

    result = await deps_module.get_semantic_search_service_dependency()

    assert result is None


@pytest.mark.anyio
async def test_dependency_initializes_service_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    init_calls: list[str] = []

    class StubService:
        def __init__(self) -> None:
            self._initialized = False

        async def initialize(self) -> None:  # pragma: no cover - exercised in test
            init_calls.append("called")
            self._initialized = True

    stub = StubService()

    monkeypatch.setattr(deps_module, "get_semantic_search_service", lambda: stub)

    result = await deps_module.get_semantic_search_service_dependency()

    assert result is stub
    assert init_calls == ["called"]
    assert stub._initialized is True


@pytest.mark.anyio
async def test_dependency_raises_when_openai_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_module, "settings", replace(deps_module.settings, semantic_search_enabled=True))
    monkeypatch.setattr(qdrant_config, "URL", "http://qdrant:6333")
    monkeypatch.setattr(service_module, "OPENAI_API_KEY", "")

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        await deps_module.get_semantic_search_service_dependency()


@pytest.mark.anyio
async def test_dependency_raises_when_qdrant_url_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.config
    monkeypatch.setattr(core.config, "settings", replace(core_settings, semantic_search_enabled=True, qdrant_url=""))
    monkeypatch.setattr(service_module, "OPENAI_API_KEY", "sk-test")

    with pytest.raises(ConfigurationError, match="Semantic search initialization failed"):
        await deps_module.get_semantic_search_service_dependency()
