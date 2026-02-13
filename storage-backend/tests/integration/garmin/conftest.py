"""Fixtures for Garmin integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator

import pytest

try:  # pragma: no cover - optional dependency guard
    from docker.errors import DockerException
except ModuleNotFoundError:  # pragma: no cover - docker-py missing
    DockerException = Exception
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from infrastructure.db import prepare_database
from infrastructure.db.mysql import create_mysql_engine


@pytest.fixture(scope="session", autouse=True)
def require_garmin_enabled():
    """Skip all Garmin tests if GARMIN_ENABLED is not set to true."""
    import os
    if os.getenv("GARMIN_ENABLED", "").lower() != "true":
        pytest.skip("Garmin tests skipped. Set GARMIN_ENABLED=true to run them.")
@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    """Create a session-scoped event loop for async tests."""

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()


def _require_docker_daemon() -> None:
    docker = pytest.importorskip(
        "docker", reason="Docker SDK is required for Garmin integration tests"
    )

    try:
        client = docker.from_env()
    except docker.errors.DockerException as exc:  # type: ignore[attr-defined]
        pytest.skip(f"Docker daemon is required for Garmin integration tests: {exc}")
        return

    try:
        client.ping()
    except docker.errors.DockerException as exc:  # type: ignore[attr-defined]
        pytest.skip(f"Docker daemon is required for Garmin integration tests: {exc}")
    finally:
        client.close()


@pytest.fixture(scope="session")
def mysql_container() -> Iterator["MySqlContainer"]:
    _require_docker_daemon()

    try:
        from testcontainers.mysql import MySqlContainer
    except ModuleNotFoundError:  # pragma: no cover - dependency guard
        pytest.skip("testcontainers is required for Garmin integration tests")

    try:
        container = MySqlContainer("mysql:8.0", username="garmin", password="garmin", dbname="garmin")
    except DockerException as exc:
        pytest.skip(f"Docker daemon is required for Garmin integration tests: {exc}")

    started = False
    try:
        container.start()
        started = True
    except DockerException as exc:
        pytest.skip(f"Docker daemon is required for Garmin integration tests: {exc}")
    try:
        yield container
    finally:
        if started:
            container.stop()


@pytest.fixture(scope="session")
def engine(mysql_container: "MySqlContainer", event_loop: asyncio.AbstractEventLoop) -> Iterator[AsyncEngine]:
    url = mysql_container.get_connection_url()
    async_url = url.replace("mysql://", "mysql+aiomysql://")
    engine = create_mysql_engine(async_url)
    try:
        yield engine
    finally:
        event_loop.run_until_complete(engine.dispose())


@pytest.fixture(scope="session")
def apply_schema(engine: AsyncEngine, event_loop: asyncio.AbstractEventLoop) -> None:
    event_loop.run_until_complete(prepare_database(engine))


@pytest.fixture()
def session(
    engine: AsyncEngine,
    apply_schema: None,
    event_loop: asyncio.AbstractEventLoop,
) -> Iterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _create_session():
        session = factory()
        transaction = await session.begin()
        return session, transaction

    session, transaction = event_loop.run_until_complete(_create_session())
    try:
        yield session
    finally:
        async def _cleanup():
            if transaction.is_active:
                await transaction.rollback()
            await session.close()
        event_loop.run_until_complete(_cleanup())
