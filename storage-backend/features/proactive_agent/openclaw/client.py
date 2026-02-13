"""OpenClaw Gateway WebSocket client.

This module provides the low-level WebSocket client for communicating with
OpenClaw Gateway. It handles connection lifecycle, protocol handshake, and
message framing.

Protocol version: 3
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Awaitable, Callable, Optional

import websockets
from websockets import ClientConnection

from .exceptions import OpenClawError, ProtocolError, RequestError
from .frame_handler import FrameHandler

logger = logging.getLogger(__name__)

# Re-export exceptions for backwards compatibility
__all__ = ["OpenClawClient", "OpenClawError", "ProtocolError", "RequestError"]


class OpenClawClient:
    """WebSocket client for OpenClaw Gateway.

    Handles connection lifecycle, protocol handshake, and message framing.
    Does NOT handle device authentication (see auth.py) or chat logic (see adapter.py).
    """

    PROTOCOL_VERSION = 3
    CONNECTION_TIMEOUT = 10.0
    DEFAULT_REQUEST_TIMEOUT = 30.0
    RETRYABLE_CODES = {"UNAVAILABLE", "AGENT_TIMEOUT"}

    def __init__(
        self,
        url: str,
        on_event: Callable[[dict[str, Any]], Awaitable[None]],
        on_connected: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        on_disconnected: Optional[Callable[[Optional[Exception]], Awaitable[None]]] = None,
    ):
        """Initialize the OpenClaw client.

        Args:
            url: WebSocket URL (ws://host:port)
            on_event: Async callback for all events (including chat events)
            on_connected: Async callback when hello-ok received
            on_disconnected: Async callback when connection lost
        """
        self._url = url
        self._on_event = on_event
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected

        self._ws: Optional[ClientConnection] = None
        self._pending_requests: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._receive_task: Optional[asyncio.Task[None]] = None
        self._connected = False
        self._frame_handler = FrameHandler(self._pending_requests, on_event)

    @property
    def connected(self) -> bool:
        """Return True if client is connected and handshake completed."""
        return self._connected

    @property
    def challenge_nonce(self) -> Optional[str]:
        """Return the challenge nonce received from gateway."""
        return self._frame_handler.challenge_nonce

    @property
    def _last_tick(self) -> float:
        """Return timestamp of last tick event."""
        return self._frame_handler.last_tick

    @_last_tick.setter
    def _last_tick(self, value: float) -> None:
        """Set timestamp of last tick event (for testing)."""
        self._frame_handler._last_tick = value

    @property
    def _challenge_nonce(self) -> Optional[str]:
        """Return the challenge nonce (internal, for testing)."""
        return self._frame_handler._challenge_nonce

    @_challenge_nonce.setter
    def _challenge_nonce(self, value: Optional[str]) -> None:
        """Set challenge nonce (for testing)."""
        self._frame_handler._challenge_nonce = value

    @property
    def _challenge_received(self) -> Optional[asyncio.Event]:
        """Return challenge received event (for testing)."""
        return self._frame_handler._challenge_received

    @_challenge_received.setter
    def _challenge_received(self, value: Optional[asyncio.Event]) -> None:
        """Set challenge received event (for testing)."""
        self._frame_handler._challenge_received = value

    async def _handle_frame(self, frame: dict[str, Any]) -> None:
        """Proxy to frame handler (for testing compatibility)."""
        await self._frame_handler.handle_frame(frame)

    async def connect(self) -> str:
        """Connect to gateway and wait for challenge event.

        Returns:
            Challenge nonce (needed for device signature in auth.py)

        Raises:
            ConnectionError: If connection fails
            TimeoutError: If no challenge received within timeout
        """
        if self._ws is not None:
            raise ProtocolError("Already connected")

        challenge_event = asyncio.Event()
        self._frame_handler.set_challenge_event(challenge_event)

        try:
            logger.info(f"Connecting to OpenClaw gateway: {self._url}")

            self._ws = await asyncio.wait_for(
                websockets.connect(self._url, ping_interval=None),
                timeout=self.CONNECTION_TIMEOUT,
            )

            self._receive_task = asyncio.create_task(self._receive_loop())

            await asyncio.wait_for(challenge_event.wait(), timeout=self.CONNECTION_TIMEOUT)

            if self._frame_handler.challenge_nonce is None:
                raise ProtocolError("Challenge received but nonce is missing")

            logger.info(f"Challenge received, nonce: {self._frame_handler.challenge_nonce[:8]}...")
            return self._frame_handler.challenge_nonce

        except asyncio.TimeoutError:
            await self._cleanup()
            raise TimeoutError("Timeout waiting for gateway challenge")
        except websockets.WebSocketException as e:
            await self._cleanup()
            raise ConnectionError(f"WebSocket connection failed: {e}") from e
        except Exception:
            await self._cleanup()
            raise

    async def handshake(self, connect_params: dict[str, Any]) -> dict[str, Any]:
        """Send connect request and receive hello-ok.

        Args:
            connect_params: Full connect request params (from auth.py)

        Returns:
            hello-ok payload (includes deviceToken, features, policy)

        Raises:
            ProtocolError: If handshake fails
            RequestError: If gateway rejects connect request
        """
        if self._ws is None:
            raise ProtocolError("Not connected - call connect() first")
        if self._connected:
            raise ProtocolError("Already completed handshake")

        logger.info("Sending connect request for handshake")

        try:
            response = await self.request("connect", connect_params)
        except RequestError as e:
            raise ProtocolError(f"Handshake rejected: {e.code} - {e.message}") from e

        self._connected = True
        logger.info(f"Handshake complete, server: {response.get('server', {}).get('displayName', 'unknown')}")

        if self._on_connected:
            await self._on_connected(response)

        return response

    async def request(
        self,
        method: str,
        params: dict[str, Any],
        timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        """Send request and wait for matching response.

        Args:
            method: RPC method name (e.g., "connect", "chat.send")
            params: Method parameters
            timeout: Response timeout in seconds

        Returns:
            Response payload (if ok=true)

        Raises:
            RequestError: If response has ok=false
            TimeoutError: If no response within timeout
            ProtocolError: If not connected
        """
        if self._ws is None:
            raise ProtocolError("Not connected")

        request_id = str(uuid.uuid4())
        frame = {"type": "req", "id": request_id, "method": method, "params": params}

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_requests[request_id] = future

        try:
            logger.debug(f"Sending request: method={method} id={request_id[:8]}...")
            await self._ws.send(json.dumps(frame))

            response = await asyncio.wait_for(future, timeout=timeout)

            if response.get("ok"):
                return response.get("payload", {})
            else:
                error = response.get("error", {})
                code = error.get("code", "UNKNOWN")
                message = error.get("message", "Unknown error")
                raise RequestError(code, message, code in self.RETRYABLE_CODES)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Request {method} timed out after {timeout}s")
        finally:
            self._pending_requests.pop(request_id, None)

    async def _receive_loop(self) -> None:
        """Background task to receive and dispatch messages."""
        disconnect_exception: Optional[Exception] = None

        try:
            if self._ws is None:
                return

            async for message in self._ws:
                try:
                    frame = json.loads(message)
                    await self._frame_handler.handle_frame(frame)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON from gateway: {e}")

        except websockets.ConnectionClosed as e:
            logger.info(f"Connection closed: code={e.code} reason={e.reason}")
            disconnect_exception = e
        except Exception as e:
            logger.exception("Unexpected error in receive loop")
            disconnect_exception = e
        finally:
            self._connected = False
            for future in self._pending_requests.values():
                if not future.done():
                    future.cancel()

            if self._on_disconnected:
                try:
                    await self._on_disconnected(disconnect_exception)
                except Exception:
                    logger.exception("Error in on_disconnected callback")

    async def close(self) -> None:
        """Close connection gracefully."""
        logger.info("Closing OpenClaw connection")
        await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up resources."""
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        for future in self._pending_requests.values():
            if not future.done():
                future.cancel()
        self._pending_requests.clear()

        self._connected = False
        self._frame_handler.reset_challenge()
