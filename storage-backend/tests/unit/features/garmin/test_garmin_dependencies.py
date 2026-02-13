"""Unit tests for Garmin dependency wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.exceptions import ConfigurationError
from features.garmin import dependencies


@pytest.fixture(autouse=True)
def reset_session_dependency(monkeypatch):
    """Ensure cached dependency state is reset between tests."""

    monkeypatch.setattr("features.garmin.dependencies._session_dependency", None)


@pytest.mark.anyio
async def test_get_garmin_session_yields_none_when_disabled(monkeypatch):
    """Garmin dependency yields None exactly once when disabled via settings."""

    monkeypatch.setattr(
        "features.garmin.dependencies.settings",
        SimpleNamespace(garmin_enabled=False),
    )

    sessions: list[object | None] = []
    async for session in dependencies.get_garmin_session():
        sessions.append(session)

    assert sessions == [None]


@pytest.mark.anyio
async def test_get_garmin_session_raises_when_enabled_without_db(monkeypatch):
    """Garmin dependency fails fast when enabled but the DB URL is missing."""

    monkeypatch.setattr(
        "features.garmin.dependencies.settings",
        SimpleNamespace(garmin_enabled=True),
    )

    def _raise():
        raise ConfigurationError("missing GARMIN_DB_URL", key="GARMIN_DB_URL")

    monkeypatch.setattr("features.garmin.dependencies.require_garmin_session_factory", _raise)

    with pytest.raises(ConfigurationError, match="GARMIN_DB_URL"):
        async for _session in dependencies.get_garmin_session():
            pass


@pytest.mark.anyio
async def test_get_garmin_session_yields_session_when_enabled(monkeypatch):
    """Garmin dependency yields actual sessions when configured."""

    monkeypatch.setattr(
        "features.garmin.dependencies.settings",
        SimpleNamespace(garmin_enabled=True),
    )

    def _fake_factory():  # pragma: no cover - sentinel return only
        return object()

    async def _fake_dependency():
        yield "session"

    monkeypatch.setattr(
        "features.garmin.dependencies.require_garmin_session_factory",
        _fake_factory,
    )
    def _dependency_factory(_factory):
        return _fake_dependency

    monkeypatch.setattr(
        "features.garmin.dependencies.get_session_dependency",
        _dependency_factory,
    )

    sessions: list[object | None] = []
    async for session in dependencies.get_garmin_session():
        sessions.append(session)

    assert sessions == ["session"]
