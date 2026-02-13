"""Tests for the realtime provider factory registry."""

from __future__ import annotations

from typing import AsyncIterator, Iterator, Mapping

import pytest

from core.providers.realtime.base import (
    BaseRealtimeProvider,
    RealtimeEvent,
    RealtimeEventType,
)
from core.providers.realtime.factory import (
    clear_registry,
    get_realtime_provider,
    list_realtime_providers,
    register_realtime_provider,
)
from core.providers.realtime.utils import NullRealtimeProvider


@pytest.fixture(autouse=True)
def reset_registry() -> Iterator[None]:
    clear_registry()
    yield
    clear_registry()


class DummyRealtimeProvider(BaseRealtimeProvider):
    name = "dummy"

    async def open_session(self, *, settings: Mapping[str, object]) -> None:  # pragma: no cover - simple stub
        self.settings = dict(settings)

    async def close_session(self) -> None:  # pragma: no cover - simple stub
        self.settings = {}

    async def send_user_event(self, payload: Mapping[str, object]) -> None:  # pragma: no cover - simple stub
        self.last_payload = dict(payload)

    async def receive_events(self) -> AsyncIterator[RealtimeEvent]:  # pragma: no cover - simple stub
        if False:
            yield RealtimeEvent(RealtimeEventType.CONTROL, {})
        return


def test_unknown_model_returns_null_provider() -> None:
    provider = get_realtime_provider("some-unregistered-model")
    assert isinstance(provider, NullRealtimeProvider)


def test_openai_aliases_resolve_to_registered_provider() -> None:
    register_realtime_provider("openai", DummyRealtimeProvider)

    provider = get_realtime_provider("openai-realtime")
    assert isinstance(provider, DummyRealtimeProvider)


def test_google_model_resolves_to_registered_provider() -> None:
    register_realtime_provider("google", DummyRealtimeProvider)

    provider = get_realtime_provider("gemini-live:beta")
    assert isinstance(provider, DummyRealtimeProvider)


def test_list_realtime_providers_excludes_null_by_default() -> None:
    register_realtime_provider("openai", DummyRealtimeProvider)
    register_realtime_provider("google", DummyRealtimeProvider)

    visible = list_realtime_providers()
    assert visible == ["google", "openai"]

    internal = list_realtime_providers(include_internal=True)
    assert "null" in internal
