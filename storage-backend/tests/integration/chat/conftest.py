"""Fixtures for chat repository integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any, Iterator
from urllib.parse import urlencode

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from infrastructure.db import prepare_database
from fastapi.testclient import TestClient
from main import create_app
from features.chat.websocket import websocket_chat_endpoint




def _build_chat_test_app():
    app = create_app()
    routes = []
    for route in app.router.routes:
        if getattr(route, "path", None) == "/chat/ws":
            continue
        routes.append(route)
    app.router.routes = routes
    app.add_api_websocket_route("/chat/ws", websocket_chat_endpoint)
    return app


@pytest.fixture()
def chat_test_client(auth_token: str) -> Iterator[TestClient]:
    """FastAPI client with the chat websocket endpoint registered.

    CRITICAL: Disposes global MySQL engines after test to prevent event loop conflicts.
    When asyncio.run() closes the event loop in cleanup, MySQL connection pool must not
    hold references to the dead loop, or the next test's fresh loop will hit:
    "RuntimeError: Task got Future attached to a different loop"
    """

    app = _build_chat_test_app()
    with TestClient(app) as client:
        client.headers.update({"Authorization": f"Bearer {auth_token}"})
        try:
            yield client
        finally:
            # Dispose all global database engines and reset references
            # This must happen BEFORE the event loop closes (which asyncio.run does)
            from infrastructure.db import mysql
            import asyncio as aio

            async def _dispose_engines():
                """Gracefully dispose all engines."""
                for attr in ["main_engine", "garmin_engine", "blood_engine", "ufc_engine"]:
                    engine = getattr(mysql, attr, None)
                    if engine is not None:
                        try:
                            await engine.dispose()
                        except Exception:
                            pass  # Ignore errors during cleanup

            # Run disposal in current event loop if possible, otherwise create new one
            try:
                aio.run(_dispose_engines())
            except RuntimeError:
                # Event loop already closed - that's fine, we're cleaning up anyway
                pass

            # Reset engine references so next test creates fresh ones
            mysql.main_engine = None
            mysql.main_session_factory = None
            mysql.garmin_engine = None
            mysql.garmin_session_factory = None
            mysql.blood_engine = None
            mysql.blood_session_factory = None
            mysql.ufc_engine = None
            mysql.ufc_session_factory = None


@pytest.fixture()
def websocket_url_factory(auth_token_factory):
    """Build websocket URLs with a valid bearer token."""

    def _factory(token: str | None = None, **params: Any) -> str:
        actual_token = token or auth_token_factory()
        query: dict[str, Any] = {"token": actual_token}
        query.update({key: value for key, value in params.items() if value is not None})
        return "/chat/ws?" + urlencode(query)

    return _factory


@pytest.fixture()
def engine() -> Iterator[AsyncEngine]:
    """Initialise an in-memory SQLite engine for each test.

    Function scope ensures fresh database state and avoids event loop conflicts
    between tests when using TestClient.
    """

    try:
        import aiosqlite  # noqa: F401  # pragma: no cover - dependency check
    except ModuleNotFoundError:  # pragma: no cover - optional dependency
        pytest.skip("aiosqlite is required for chat integration tests")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Use asyncio.run to get a fresh event loop for setup/teardown
    asyncio.run(prepare_database(engine))
    try:
        yield engine
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture()
def session(
    engine: AsyncEngine
) -> Iterator[AsyncSession]:
    """Yield a transaction-scoped session rolled back after each test."""

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _open_session() -> tuple[AsyncSession, Any]:
        session = factory()
        await session.__aenter__()
        transaction = await session.begin()
        return session, transaction

    async def _close_session(session: AsyncSession, transaction: Any) -> None:
        if transaction is not None and transaction.is_active:
            await transaction.rollback()
        await session.__aexit__(None, None, None)

    db_session, transaction = asyncio.run(_open_session())
    try:
        yield db_session
    finally:
        asyncio.run(_close_session(db_session, transaction))
