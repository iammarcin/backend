"""Test configuration helpers."""

from __future__ import annotations
from .helpers import (
    is_semantic_search_available,
    is_garmin_db_available,
    is_ufc_db_available,
    is_sqs_available,
    get_missing_prerequisites,
)

from . import conftest_semantic_stub  # noqa: F401

import asyncio
import inspect
import logging
import os
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict

import pytest
from jose import jwt

# Explicitly opt-in to the async plugins we rely on. Some execution environments
# (including a few CI runners) disable plugin auto-discovery via the
# ``PYTEST_DISABLE_PLUGIN_AUTOLOAD`` environment variable which prevents
# ``pytest-asyncio`` and AnyIO's plugin from being loaded even if the packages
# are installed. Declaring ``pytest_plugins`` ensures the event loop fixtures and
# ``@pytest.mark.anyio`` decorators always work.
pytest_plugins = ("anyio", "pytest_asyncio")

# Ensure the repository root is importable as a module path so that ``import core``
# and other absolute imports used throughout the codebase succeed when tests are
# executed from arbitrary working directories.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("MY_AUTH_TOKEN", "test-secret")
os.environ.setdefault("DB_TYPE", "postgresql")


def _safe_excepthook(exc_type, exc, tb) -> None:
    """Prevent noisy excepthook failures during interpreter shutdown."""
    try:
        sys.__excepthook__(exc_type, exc, tb)
    except Exception:
        pass


def _suppress_grpc_shutdown_noise() -> None:
    """Suppress gRPC async shutdown noise during interpreter exit.

    gRPC's AioChannel.__dealloc__ calls shutdown_grpc_aio() during garbage
    collection, which can fail with AssertionError if gRPC async wasn't
    properly initialized or was already shutdown. This atexit handler
    suppresses stderr briefly to hide this cosmetic error.
    """
    import atexit

    def _silence_stderr() -> None:
        try:
            # Redirect stderr to /dev/null during interpreter shutdown
            devnull_fd = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull_fd, 2)
        except Exception:
            pass

    # Register at the LAST position (runs first during exit)
    atexit.register(_silence_stderr)


# Register the suppressor early
_suppress_grpc_shutdown_noise()


@pytest.fixture(scope="session", autouse=True)
def restore_default_excepthooks() -> None:
    """Reset sys/threading excepthooks to defaults to avoid shutdown noise."""
    sys.excepthook = _safe_excepthook
    if hasattr(threading, "__excepthook__"):
        threading.excepthook = threading.__excepthook__  # type: ignore[assignment]


def _init_grpc_aio_if_needed() -> None:
    """Initialize gRPC aio to prevent shutdown assertion errors."""
    try:
        import grpc._cython.cygrpc as cygrpc

        if hasattr(cygrpc, "init_grpc_aio"):
            cygrpc.init_grpc_aio()
    except Exception:
        pass


def _shutdown_grpc_aio_safely() -> None:
    """Shutdown gRPC aio, suppressing errors during interpreter cleanup."""
    try:
        import grpc._cython.cygrpc as cygrpc

        if hasattr(cygrpc, "shutdown_grpc_aio"):
            cygrpc.shutdown_grpc_aio()
    except (AssertionError, Exception):
        # Ignore assertion errors during interpreter shutdown
        pass


def pytest_sessionstart(session: Any) -> None:
    """Initialize gRPC aio early to ensure proper shutdown later."""
    _init_grpc_aio_if_needed()


def _cancel_pending_background_tasks() -> None:
    """Cancel pending background tasks to avoid 'Task was destroyed' warnings.

    Covers:
    - session_naming_ tasks from schedule_session_naming()
    - OpenClawSessionManager._reconnect_loop tasks from disconnect handling
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # No running loop

    for task in asyncio.all_tasks(loop):
        task_name = task.get_name() or ""
        if task_name.startswith("session_naming_"):
            task.cancel()
            continue
        coro = task.get_coro()
        coro_qualname = getattr(coro, "__qualname__", "") if coro else ""
        if "_reconnect_loop" in coro_qualname:
            try:
                task.cancel()
            except RuntimeError:
                pass  # Event loop already closed
            task._log_destroy_pending = False


@pytest.fixture(autouse=True)
def cleanup_background_tasks():
    """Cancel pending background tasks after each test."""
    yield
    _cancel_pending_background_tasks()


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    """Ensure safe excepthooks are restored before pytest exits."""
    sys.excepthook = _safe_excepthook

    # Cancel any leaked OpenClaw reconnect tasks before loop closes
    from features.proactive_agent.openclaw.session import reset_session_manager_for_testing

    reset_session_manager_for_testing()
    _shutdown_grpc_aio_safely()


@pytest.fixture
def anyio_backend() -> str:
    """Default AnyIO backend used when tests do not override the fixture."""

    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def suppress_asyncio_debug_logging() -> None:
    """Prevent asyncio debug logs from writing to closed pytest capture streams."""

    logger = logging.getLogger("asyncio")
    effective_level = logger.getEffectiveLevel()

    # Avoid debug-level emissions during interpreter shutdown where pytest may
    # have already closed its log capture streams.
    if effective_level < logging.INFO:
        logger.setLevel(logging.INFO)


@pytest.fixture(scope="session", autouse=True)
def close_ai_clients() -> None:
    """Ensure async AI SDK clients release their httpx transports during teardown."""

    yield

    # Always create a new event loop for session teardown to avoid asyncio.get_event_loop() deprecation warnings
    async_logger = logging.getLogger("asyncio")
    previous_disabled = async_logger.disabled
    async_logger.disabled = True
    try:
        loop = asyncio.new_event_loop()
    finally:
        async_logger.disabled = previous_disabled
    asyncio.set_event_loop(loop)
    created_loop = True

    from core.clients.ai import ai_clients

    # Close sync clients first (especially Gemini which uses gRPC)
    for name in list(ai_clients.keys()):
        client = ai_clients[name]
        close = getattr(client, "close", None)
        if close is None or not callable(close):
            continue
        # Check if it's a sync close (not awaitable)
        if not inspect.iscoroutinefunction(close):
            try:
                close()
            except Exception:
                pass

    async def _shutdown() -> None:
        for client in ai_clients.values():
            close = getattr(client, "close", None)
            if close is None or not callable(close):
                continue

            try:
                result = close()
            except TypeError:
                # Some clients expose close descriptors that require arguments; skip them.
                continue

            if inspect.isawaitable(result):
                try:
                    await result
                except RuntimeError:
                    # Ignore loop lifecycle races from third-party SDKs.
                    pass

    async_logger.disabled = True
    try:
        asyncio.run(_shutdown())
    finally:
        async_logger.disabled = previous_disabled

    if created_loop and loop is not None:
        loop.close()
        asyncio.set_event_loop(None)

    # Shutdown gRPC aio after all clients are closed
    _shutdown_grpc_aio_safely()


@pytest.fixture(scope="session")
def auth_token_secret() -> str:
    """Return the JWT secret configured for tests."""

    return os.environ["MY_AUTH_TOKEN"]


@pytest.fixture()
def auth_token_factory(auth_token_secret: str) -> Callable[..., str]:
    """Factory producing signed JWTs for authenticated requests."""

    def _factory(
        *,
        customer_id: int = 1,
        email: str = "user@example.com",
        expires_delta: timedelta | None = timedelta(hours=1),
        extra_claims: Dict[str, Any] | None = None,
    ) -> str:
        payload: Dict[str, Any] = {"id": customer_id, "email": email}
        if extra_claims:
            payload.update(extra_claims)
        if expires_delta is not None:
            payload["exp"] = datetime.now(timezone.utc) + expires_delta
        return jwt.encode(payload, auth_token_secret, algorithm="HS256")

    return _factory


@pytest.fixture()
def auth_token(auth_token_factory: Callable[..., str]) -> str:
    """Return a default signed JWT for convenience."""

    return auth_token_factory()


@pytest.fixture()
def authenticated_client(auth_token: str) -> TestClient:
    """Return a TestClient with JWT authentication headers pre-configured."""

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return client


@pytest.fixture()
async def async_authenticated_client(auth_token: str):
    """Return an AsyncClient with JWT authentication headers pre-configured."""

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {auth_token}"},
    ) as client:
        yield client


# ============================================================================
# Service Availability Fixtures (Milestone 1)
# ============================================================================


if not hasattr(pytest, "helpers"):
    class _PytestHelpersNamespace:
        """Lightweight namespace for pytest helper functions."""

        pass

    pytest.helpers = _PytestHelpersNamespace()  # type: ignore[attr-defined]

pytest.helpers.is_semantic_search_available = (  # type: ignore[attr-defined]
    is_semantic_search_available
)
pytest.helpers.is_garmin_db_available = is_garmin_db_available  # type: ignore[attr-defined]
pytest.helpers.is_ufc_db_available = is_ufc_db_available  # type: ignore[attr-defined]
pytest.helpers.is_sqs_available = is_sqs_available  # type: ignore[attr-defined]
pytest.helpers.get_missing_prerequisites = (  # type: ignore[attr-defined]
    get_missing_prerequisites
)


@pytest.fixture
def require_semantic_search():
    """Skip test if semantic search is not properly configured.

    Checks for:
    - OPENAI_API_KEY environment variable
    - semantic_search_enabled setting

    Usage:
        def test_semantic_search(require_semantic_search):
            # This test only runs when semantic search is available
            ...
    """

    if not is_semantic_search_available():
        missing = get_missing_prerequisites("semantic_search")
        pytest.skip(f"Semantic search not configured. Missing: {', '.join(missing)}")


@pytest.fixture
def require_garmin_db():
    """Skip test if Garmin database is not configured.

    Checks for:
    - GARMIN_DB_URL environment variable

    Usage:
        def test_garmin_feature(require_garmin_db):
            # This test only runs when Garmin DB is available
            ...
    """

    from core.config import settings

    if not settings.garmin_enabled:
        pytest.skip("Garmin features disabled via GARMIN_ENABLED=false")

    if not is_garmin_db_available():
        missing = get_missing_prerequisites("garmin_db")
        pytest.skip(f"Garmin database not configured. Missing: {', '.join(missing)}")


@pytest.fixture
def require_ufc_db():
    """Skip test if UFC database is not configured.

    Checks for:
    - UFC_DB_URL environment variable

    Usage:
        def test_ufc_feature(require_ufc_db):
            # This test only runs when UFC DB is available
            ...
    """

    if not is_ufc_db_available():
        missing = get_missing_prerequisites("ufc_db")
        pytest.skip(f"UFC database not configured. Missing: {', '.join(missing)}")


@pytest.fixture
def require_sqs():
    """Skip test if SQS queue service is not configured.

    Checks for:
    - AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

    Usage:
        def test_sqs_queue(require_sqs):
            # This test only runs when SQS is available
            ...
    """

    if not is_sqs_available():
        missing = get_missing_prerequisites("sqs")
        pytest.skip(f"SQS queue service not configured. Missing: {', '.join(missing)}")
