"""Unit tests for OpenClaw WebSocket client."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from features.proactive_agent.openclaw.client import (
    OpenClawClient,
    OpenClawError,
    ProtocolError,
    RequestError,
)


class TestExceptions:
    """Test custom exception classes."""

    def test_openclaw_error_base(self):
        """OpenClawError is the base exception."""
        error = OpenClawError("test error")
        assert str(error) == "test error"
        assert isinstance(error, Exception)

    def test_protocol_error_inherits(self):
        """ProtocolError inherits from OpenClawError."""
        error = ProtocolError("protocol failed")
        assert isinstance(error, OpenClawError)
        assert str(error) == "protocol failed"

    def test_request_error_properties(self):
        """RequestError stores code, message, and retryable flag."""
        error = RequestError("UNAVAILABLE", "Gateway unavailable", retryable=True)

        assert error.code == "UNAVAILABLE"
        assert error.message == "Gateway unavailable"
        assert error.retryable is True
        assert str(error) == "UNAVAILABLE: Gateway unavailable"

    def test_request_error_default_not_retryable(self):
        """RequestError defaults to not retryable."""
        error = RequestError("INVALID_REQUEST", "Bad params")
        assert error.retryable is False


class TestClientInit:
    """Test OpenClawClient initialization."""

    def test_init_stores_parameters(self):
        """Constructor stores URL and callbacks."""
        on_event = AsyncMock()
        on_connected = AsyncMock()
        on_disconnected = AsyncMock()

        client = OpenClawClient(
            url="ws://test:18789",
            on_event=on_event,
            on_connected=on_connected,
            on_disconnected=on_disconnected,
        )

        assert client._url == "ws://test:18789"
        assert client._on_event is on_event
        assert client._on_connected is on_connected
        assert client._on_disconnected is on_disconnected

    def test_init_default_state(self):
        """Client starts in disconnected state."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        assert client.connected is False
        assert client.challenge_nonce is None
        assert client._ws is None
        assert len(client._pending_requests) == 0


class TestClientConnect:
    """Test connect() method."""

    @pytest.mark.asyncio
    async def test_connect_receives_challenge(self):
        """connect() returns nonce from connect.challenge event."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        mock_ws = AsyncMock()

        # Simulate receiving challenge event
        challenge_frame = json.dumps({
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "test-nonce-12345"},
        })

        async def mock_iter():
            yield challenge_frame
            # Keep connection alive
            await asyncio.sleep(10)

        mock_ws.__aiter__ = lambda self: mock_iter()
        mock_ws.close = AsyncMock()

        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            nonce = await client.connect()

        assert nonce == "test-nonce-12345"
        assert client.challenge_nonce == "test-nonce-12345"

    @pytest.mark.asyncio
    async def test_connect_already_connected_raises(self):
        """connect() raises if already connected."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = MagicMock()  # Simulate existing connection

        with pytest.raises(ProtocolError, match="Already connected"):
            await client.connect()

    @pytest.mark.asyncio
    async def test_connect_timeout_no_challenge(self):
        """connect() times out if no challenge received."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client.CONNECTION_TIMEOUT = 0.1  # Short timeout for test

        mock_ws = AsyncMock()

        async def mock_iter():
            # Never send challenge
            await asyncio.sleep(10)
            yield ""

        mock_ws.__aiter__ = lambda self: mock_iter()
        mock_ws.close = AsyncMock()

        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            with pytest.raises(TimeoutError, match="Timeout waiting for gateway challenge"):
                await client.connect()


class TestClientHandshake:
    """Test handshake() method."""

    @pytest.mark.asyncio
    async def test_handshake_not_connected_raises(self):
        """handshake() raises if not connected."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        with pytest.raises(ProtocolError, match="Not connected"):
            await client.handshake({"test": "params"})

    @pytest.mark.asyncio
    async def test_handshake_already_done_raises(self):
        """handshake() raises if already completed."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = MagicMock()
        client._connected = True

        with pytest.raises(ProtocolError, match="Already completed handshake"):
            await client.handshake({"test": "params"})

    @pytest.mark.asyncio
    async def test_handshake_success_sets_connected(self):
        """Successful handshake sets connected flag and calls callback."""
        on_connected = AsyncMock()
        client = OpenClawClient(
            url="ws://test:18789",
            on_event=AsyncMock(),
            on_connected=on_connected,
        )

        # Setup mocked request
        hello_ok_payload = {
            "server": {"displayName": "OpenClaw Gateway"},
            "deviceToken": "token-123",
        }

        with patch.object(client, "request", AsyncMock(return_value=hello_ok_payload)):
            client._ws = MagicMock()
            result = await client.handshake({"minProtocol": 3})

        assert client.connected is True
        assert result == hello_ok_payload
        on_connected.assert_awaited_once_with(hello_ok_payload)

    @pytest.mark.asyncio
    async def test_handshake_failure_raises_protocol_error(self):
        """Failed handshake raises ProtocolError."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = MagicMock()

        with patch.object(
            client,
            "request",
            AsyncMock(side_effect=RequestError("NOT_PAIRED", "Device not paired")),
        ):
            with pytest.raises(ProtocolError, match="Handshake rejected"):
                await client.handshake({"minProtocol": 3})

        assert client.connected is False


class TestClientRequest:
    """Test request() method."""

    @pytest.mark.asyncio
    async def test_request_not_connected_raises(self):
        """request() raises if not connected."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        with pytest.raises(ProtocolError, match="Not connected"):
            await client.request("test.method", {"param": "value"})

    @pytest.mark.asyncio
    async def test_request_sends_correct_frame(self):
        """request() sends properly formatted JSON frame."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        # Setup response
        async def mock_send(data: str) -> None:
            frame = json.loads(data)
            # Verify frame structure
            assert frame["type"] == "req"
            assert "id" in frame
            assert frame["method"] == "chat.send"
            assert frame["params"] == {"message": "hello"}

            # Simulate response
            response_frame = {
                "type": "res",
                "id": frame["id"],
                "ok": True,
                "payload": {"result": "success"},
            }
            client._pending_requests[frame["id"]].set_result(response_frame)

        client._ws.send = mock_send

        result = await client.request("chat.send", {"message": "hello"})
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_request_error_response_raises(self):
        """request() raises RequestError for ok=false response."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        async def mock_send(data: str) -> None:
            frame = json.loads(data)
            error_response = {
                "type": "res",
                "id": frame["id"],
                "ok": False,
                "error": {"code": "INVALID_REQUEST", "message": "Bad params"},
            }
            client._pending_requests[frame["id"]].set_result(error_response)

        client._ws.send = mock_send

        with pytest.raises(RequestError) as exc_info:
            await client.request("bad.method", {})

        assert exc_info.value.code == "INVALID_REQUEST"
        assert exc_info.value.retryable is False

    @pytest.mark.asyncio
    async def test_request_retryable_error_code(self):
        """RequestError is retryable for UNAVAILABLE code."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        async def mock_send(data: str) -> None:
            frame = json.loads(data)
            error_response = {
                "type": "res",
                "id": frame["id"],
                "ok": False,
                "error": {"code": "UNAVAILABLE", "message": "Gateway shutting down"},
            }
            client._pending_requests[frame["id"]].set_result(error_response)

        client._ws.send = mock_send

        with pytest.raises(RequestError) as exc_info:
            await client.request("test.method", {})

        assert exc_info.value.code == "UNAVAILABLE"
        assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """request() raises TimeoutError if no response."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        # Never resolve the response
        client._ws.send = AsyncMock()

        with pytest.raises(TimeoutError, match="timed out"):
            await client.request("slow.method", {}, timeout=0.1)

    @pytest.mark.asyncio
    async def test_request_cleans_up_pending(self):
        """request() removes from pending_requests after completion."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        request_id_captured = None

        async def mock_send(data: str) -> None:
            nonlocal request_id_captured
            frame = json.loads(data)
            request_id_captured = frame["id"]
            response_frame = {"type": "res", "id": frame["id"], "ok": True, "payload": {}}
            client._pending_requests[frame["id"]].set_result(response_frame)

        client._ws.send = mock_send

        await client.request("test", {})

        assert request_id_captured not in client._pending_requests


class TestHandleFrame:
    """Test _handle_frame() dispatching."""

    @pytest.mark.asyncio
    async def test_handle_response_resolves_future(self):
        """Response frame resolves matching pending request."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        client._pending_requests["req-123"] = future

        response_frame = {
            "type": "res",
            "id": "req-123",
            "ok": True,
            "payload": {"data": "test"},
        }

        await client._handle_frame(response_frame)

        assert future.done()
        assert future.result() == response_frame

    @pytest.mark.asyncio
    async def test_handle_unknown_response_ignored(self):
        """Response for unknown request is logged but ignored."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        # Should not raise
        await client._handle_frame({
            "type": "res",
            "id": "unknown-id",
            "ok": True,
            "payload": {},
        })

    @pytest.mark.asyncio
    async def test_handle_challenge_event_stores_nonce(self):
        """connect.challenge event stores nonce and signals event."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._challenge_received = asyncio.Event()

        await client._handle_frame({
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "challenge-nonce"},
        })

        assert client._challenge_nonce == "challenge-nonce"
        assert client._challenge_received.is_set()

    @pytest.mark.asyncio
    async def test_handle_tick_event_updates_timestamp(self):
        """tick event updates last tick timestamp."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._last_tick = 0.0

        await client._handle_frame({
            "type": "event",
            "event": "tick",
            "payload": {},
        })

        assert client._last_tick > 0

    @pytest.mark.asyncio
    async def test_handle_chat_event_dispatches_to_callback(self):
        """Other events dispatch to on_event callback."""
        on_event = AsyncMock()
        client = OpenClawClient(url="ws://test:18789", on_event=on_event)

        chat_frame = {
            "type": "event",
            "event": "chat",
            "payload": {"state": "delta", "message": {"content": [{"text": "Hi"}]}},
        }

        await client._handle_frame(chat_frame)

        on_event.assert_awaited_once_with(chat_frame)

    @pytest.mark.asyncio
    async def test_handle_unknown_frame_type_ignored(self):
        """Unknown frame types are logged but ignored."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        # Should not raise
        await client._handle_frame({"type": "unknown", "data": "test"})


class TestClientClose:
    """Test close() method."""

    @pytest.mark.asyncio
    async def test_close_cancels_receive_task(self):
        """close() cancels the receive loop task."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        # Create a real task that we can cancel
        task_started = asyncio.Event()

        async def long_running_task():
            task_started.set()
            await asyncio.sleep(100)

        client._receive_task = asyncio.create_task(long_running_task())
        client._ws = AsyncMock()

        # Wait for task to start
        await task_started.wait()

        await client.close()

        # Task should be done (cancelled)
        assert client._receive_task is None

    @pytest.mark.asyncio
    async def test_close_closes_websocket(self):
        """close() closes the WebSocket connection."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())

        mock_ws = AsyncMock()
        client._ws = mock_ws

        await client.close()

        mock_ws.close.assert_awaited_once()
        assert client._ws is None

    @pytest.mark.asyncio
    async def test_close_cancels_pending_requests(self):
        """close() cancels all pending request futures."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()

        future1: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        future2: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()
        client._pending_requests["req-1"] = future1
        client._pending_requests["req-2"] = future2

        await client.close()

        assert future1.cancelled()
        assert future2.cancelled()
        assert len(client._pending_requests) == 0

    @pytest.mark.asyncio
    async def test_close_resets_state(self):
        """close() resets connection state."""
        client = OpenClawClient(url="ws://test:18789", on_event=AsyncMock())
        client._ws = AsyncMock()
        client._connected = True
        client._challenge_nonce = "some-nonce"

        await client.close()

        assert client.connected is False
        assert client._challenge_nonce is None


class TestReceiveLoop:
    """Test _receive_loop() behavior."""

    @pytest.mark.asyncio
    async def test_receive_loop_calls_disconnected_on_close(self):
        """_receive_loop() calls on_disconnected when connection closes."""
        import websockets

        on_disconnected = AsyncMock()
        client = OpenClawClient(
            url="ws://test:18789",
            on_event=AsyncMock(),
            on_disconnected=on_disconnected,
        )

        class MockWSIterator:
            def __init__(self):
                self._raised = False

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._raised:
                    raise StopAsyncIteration
                self._raised = True
                raise websockets.ConnectionClosed(None, None)

        client._ws = MockWSIterator()

        await client._receive_loop()

        on_disconnected.assert_awaited_once()
        assert client._connected is False

    @pytest.mark.asyncio
    async def test_receive_loop_handles_invalid_json(self):
        """_receive_loop() handles invalid JSON gracefully."""
        on_event = AsyncMock()
        client = OpenClawClient(url="ws://test:18789", on_event=on_event)

        messages = ["not valid json", json.dumps({"type": "event", "event": "test", "payload": {}})]
        msg_index = 0

        async def mock_iter():
            nonlocal msg_index
            for msg in messages:
                msg_index += 1
                yield msg

        mock_ws = MagicMock()
        mock_ws.__aiter__ = lambda self: mock_iter()
        client._ws = mock_ws

        await client._receive_loop()

        # Should still process valid message
        on_event.assert_awaited_once()


class TestProtocolConstants:
    """Test protocol constants."""

    def test_protocol_version(self):
        """Protocol version is 3."""
        assert OpenClawClient.PROTOCOL_VERSION == 3

    def test_retryable_codes(self):
        """Retryable error codes are defined."""
        assert "UNAVAILABLE" in OpenClawClient.RETRYABLE_CODES
        assert "AGENT_TIMEOUT" in OpenClawClient.RETRYABLE_CODES
        assert "INVALID_REQUEST" not in OpenClawClient.RETRYABLE_CODES
