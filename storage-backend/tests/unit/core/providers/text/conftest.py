"""Gemini live-provider fixtures for text provider tests."""

from __future__ import annotations

import asyncio
import inspect
import threading
from types import MethodType
from typing import Any, Callable, Generator

import pytest

from core.clients.ai import ai_clients


class _BackgroundLoop:
    """Manage a long-lived asyncio event loop on a background thread."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="gemini-sdk-loop", daemon=True)
        self._ready = threading.Event()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        self.loop.run_forever()

    def start(self) -> None:
        self._thread.start()
        self._ready.wait()

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join()
        self.loop.close()


def _initialise_async_client(loop: asyncio.AbstractEventLoop) -> None:
    """Bind the Gemini async client to the managed loop."""

    client = ai_clients.get("gemini")
    if not client:
        raise RuntimeError("Gemini client is not configured")

    ready = threading.Event()

    def _bind() -> None:
        # Accessing ``aio`` ensures the SDK initialises using this loop.
        getattr(client, "aio", None)
        ready.set()

    loop.call_soon_threadsafe(_bind)
    ready.wait()


async def _shutdown_async_client() -> None:
    """Close the Gemini async client if the SDK exposes a shutdown hook."""

    client = ai_clients.get("gemini")
    if not client:
        return

    async_client = getattr(client, "aio", None)
    if not async_client:
        return

    close: Callable[..., Any] | None = getattr(async_client, "close", None) or getattr(async_client, "aclose", None)
    if not close:
        return

    result = close()
    if inspect.isawaitable(result):
        await result


@pytest.fixture(scope="session")
def gemini_background_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Provide a shared background loop for the Google Gemini SDK."""

    if "gemini" not in ai_clients:
        pytest.skip("GOOGLE_API_KEY is not configured; skipping Gemini live-provider tests")

    manager = _BackgroundLoop()
    manager.start()
    _initialise_async_client(manager.loop)

    yield manager.loop

    future = asyncio.run_coroutine_threadsafe(_shutdown_async_client(), manager.loop)
    try:
        future.result(timeout=10)
    except Exception:
        # Test environments occasionally kill the interpreter before the SDK
        # finishes closing. Ignore shutdown errors to keep teardown robust.
        pass

    manager.stop()


@pytest.fixture
def gemini_text_provider(gemini_background_loop: asyncio.AbstractEventLoop):
    """Return a Gemini text provider whose SDK calls run on the background loop."""

    from core.providers.factory import get_text_provider

    settings: dict[str, Any] = {"text": {"model": "cheapest-gemini"}}
    provider = get_text_provider(settings)
    original_generate_async = provider._generate_async

    async def _generate_on_background(self: Any, model: str, contents: list[Any], config: Any) -> Any:
        coroutine = original_generate_async(model, contents, config)
        future = asyncio.run_coroutine_threadsafe(coroutine, gemini_background_loop)
        return await asyncio.wrap_future(future)

    provider._generate_async = MethodType(_generate_on_background, provider)
    return provider
