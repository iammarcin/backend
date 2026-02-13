"""Tests for StreamingManager completion token ownership."""

import pytest

from core.exceptions import CompletionOwnershipError, StreamingError
from core.streaming.manager import StreamingManager


@pytest.fixture
def anyio_backend() -> str:
    """Ensure anyio tests execute with the asyncio backend."""

    return "asyncio"


@pytest.mark.anyio("asyncio")
async def test_create_token_once() -> None:
    manager = StreamingManager()
    token = manager.create_completion_token()

    assert isinstance(token, str)
    assert token


@pytest.mark.anyio("asyncio")
async def test_create_token_twice_raises() -> None:
    manager = StreamingManager()
    manager.create_completion_token()

    with pytest.raises(StreamingError):
        manager.create_completion_token()


@pytest.mark.anyio("asyncio")
async def test_completion_requires_token() -> None:
    manager = StreamingManager()
    manager.create_completion_token()

    with pytest.raises(CompletionOwnershipError):
        await manager.signal_completion(token="")


@pytest.mark.anyio("asyncio")
async def test_completion_valid_token() -> None:
    manager = StreamingManager()
    token = manager.create_completion_token()

    await manager.signal_completion(token=token)


@pytest.mark.anyio("asyncio")
async def test_completion_wrong_token() -> None:
    manager = StreamingManager()
    manager.create_completion_token()

    with pytest.raises(CompletionOwnershipError):
        await manager.signal_completion(token="wrong")


@pytest.mark.anyio("asyncio")
async def test_completion_without_creation() -> None:
    manager = StreamingManager()

    with pytest.raises(CompletionOwnershipError):
        await manager.signal_completion(token="orphan")


@pytest.mark.anyio("asyncio")
async def test_completion_idempotent_with_same_token() -> None:
    manager = StreamingManager()
    token = manager.create_completion_token()

    await manager.signal_completion(token=token)
    await manager.signal_completion(token=token)


@pytest.mark.anyio("asyncio")
async def test_reset_clears_token_state() -> None:
    manager = StreamingManager()
    token = manager.create_completion_token()
    await manager.signal_completion(token=token)

    manager.reset()

    new_token = manager.create_completion_token()
    assert new_token != token
