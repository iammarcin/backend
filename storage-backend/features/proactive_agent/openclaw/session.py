"""OpenClaw shared connection manager.

Manages a single shared WebSocket connection to OpenClaw Gateway that serves
all sessions and users. Handles connection lifecycle, reconnection, and
event dispatching.

Usage:
    manager = get_openclaw_session_manager()
    adapter = await manager.get_adapter()
    run_id = await adapter.send_message(...)
"""

import asyncio
import logging
from typing import Any, Optional

from .adapter import OpenClawAdapter
from .auth import DeviceAuth
from .client import OpenClawClient, OpenClawError, ProtocolError
from .config import OpenClawConfig, get_openclaw_config

logger = logging.getLogger(__name__)


class OpenClawSessionManager:
    """Manages a single shared OpenClaw WebSocket connection.

    Features:
    - Lazy connection on first use
    - Automatic reconnection on disconnect
    - Event dispatching to adapter
    - Thread-safe connection management
    """

    RECONNECT_DELAY_SECONDS = 5.0
    MAX_RECONNECT_ATTEMPTS = 3

    def __init__(self, config: OpenClawConfig):
        """Initialize the session manager.

        Args:
            config: OpenClaw configuration
        """
        self._config = config
        self._client: Optional[OpenClawClient] = None
        self._adapter: Optional[OpenClawAdapter] = None
        self._auth: Optional[DeviceAuth] = None
        self._connect_lock = asyncio.Lock()
        self._connected = False
        self._connecting = False
        self._reconnect_task: Optional[asyncio.Task[None]] = None
        self._device_token: Optional[str] = None

    @property
    def connected(self) -> bool:
        """Return True if connected and handshake completed."""
        return self._connected and self._client is not None and self._client.connected

    async def get_adapter(self) -> OpenClawAdapter:
        """Get the OpenClaw adapter, connecting if necessary.

        Returns:
            OpenClawAdapter for sending messages

        Raises:
            OpenClawError: If connection fails
        """
        if not self.connected:
            await self._ensure_connected()

        if self._adapter is None:
            raise OpenClawError("Adapter not initialized")

        return self._adapter

    async def _ensure_connected(self) -> None:
        """Ensure connection is established.

        Uses a lock to prevent concurrent connection attempts. If already
        connected, returns immediately. Otherwise, establishes a new connection.
        """
        async with self._connect_lock:
            if self.connected:
                return

            self._connecting = True
            try:
                await self._connect()
            finally:
                self._connecting = False

    async def _connect(self) -> None:
        """Establish connection to OpenClaw Gateway."""
        logger.info("Connecting to OpenClaw Gateway: %s", self._config.gateway_url)

        # Initialize auth if needed
        if self._auth is None:
            self._auth = DeviceAuth(
                keypair_path=self._config.keypair_path,
                token_cache_path=self._config.token_cache_path,
            )
            self._auth.load_or_generate_keypair()
            logger.info("Device initialized: %s", self._auth.device_id[:16] + "...")

        # Get cached token if available
        self._device_token = self._auth.get_cached_token()

        # Create client
        self._client = OpenClawClient(
            url=self._config.gateway_url,
            on_event=self._handle_event,
            on_connected=self._handle_connected,
            on_disconnected=self._handle_disconnected,
        )

        # Connect and get challenge nonce
        nonce = await self._client.connect()

        # Build connect params with signature
        connect_params = self._auth.build_connect_params(
            client_id=self._config.client_id,
            client_version=self._config.client_version,
            platform=self._config.platform,
            gateway_token=self._config.gateway_token,
            nonce=nonce,
            stored_device_token=self._device_token,
        )

        # Complete handshake
        hello_response = await self._client.handshake(connect_params)

        # Cache device token for future connections
        new_token = hello_response.get("deviceToken")
        if new_token and new_token != self._device_token:
            self._auth.cache_token(new_token)
            self._device_token = new_token
            logger.info("Cached new device token")

        # Create adapter
        self._adapter = OpenClawAdapter(self._client)
        self._connected = True

        logger.info(
            "OpenClaw connected: server=%s, device=%s",
            hello_response.get("server", {}).get("displayName", "unknown"),
            self._auth.device_id[:16] + "...",
        )

    async def _handle_event(self, event: dict[str, Any]) -> None:
        """Handle events from OpenClaw Gateway."""
        if self._adapter is not None:
            await self._adapter.handle_event(event)

    async def _handle_connected(self, payload: dict[str, Any]) -> None:
        """Handle successful connection."""
        logger.debug("OpenClaw connected callback: %s", payload.get("server", {}))

    async def _handle_disconnected(self, error: Optional[Exception]) -> None:
        """Handle disconnection - force-complete active streams and reconnect."""
        self._connected = False
        logger.warning("OpenClaw disconnected: %s", error)

        # Force-complete active streams to save accumulated content
        if self._adapter is not None:
            active_run_ids = self._adapter.get_active_run_ids()
            if active_run_ids:
                logger.warning(
                    "Force-completing %d active streams due to disconnect",
                    len(active_run_ids)
                )
                for run_id in active_run_ids:
                    try:
                        await self._adapter.force_complete_stream(run_id, reason="disconnect")
                    except Exception as e:
                        logger.error(
                            "Failed to force-complete stream %s: %s",
                            run_id[:8], e
                        )
                        # Still try to clean up
                        self._adapter.cleanup_stream(run_id)

        # Schedule reconnect
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        attempt = 0
        delay = self.RECONNECT_DELAY_SECONDS

        while attempt < self.MAX_RECONNECT_ATTEMPTS:
            attempt += 1
            logger.info(
                "OpenClaw reconnect attempt %d/%d in %.1fs",
                attempt,
                self.MAX_RECONNECT_ATTEMPTS,
                delay,
            )

            await asyncio.sleep(delay)

            try:
                await self._connect()
                logger.info("OpenClaw reconnected successfully")
                return
            except Exception as e:
                logger.error("OpenClaw reconnect failed: %s", e)
                delay = min(delay * 2, 60.0)

        logger.error(
            "OpenClaw reconnect failed after %d attempts", self.MAX_RECONNECT_ATTEMPTS
        )

    async def close(self) -> None:
        """Close the connection."""
        if self._reconnect_task and not self._reconnect_task.done():
            try:
                self._reconnect_task.cancel()
                await self._reconnect_task
            except (asyncio.CancelledError, RuntimeError):
                # RuntimeError can occur if event loop is closed
                pass

        if self._client is not None:
            await self._client.close()
            self._client = None

        self._adapter = None
        self._connected = False
        logger.info("OpenClaw session manager closed")


_session_manager: Optional[OpenClawSessionManager] = None
_manager_lock = asyncio.Lock()


async def get_openclaw_session_manager() -> OpenClawSessionManager:
    """Get the shared OpenClaw session manager (singleton)."""
    global _session_manager

    async with _manager_lock:
        if _session_manager is None:
            config = get_openclaw_config()
            if not config.enabled:
                raise OpenClawError("OpenClaw is not enabled")
            _session_manager = OpenClawSessionManager(config)

        return _session_manager


async def close_openclaw_session() -> None:
    """Close the shared OpenClaw session."""
    global _session_manager

    async with _manager_lock:
        if _session_manager is not None:
            await _session_manager.close()
            _session_manager = None


def reset_session_manager_for_testing() -> None:
    """Reset the global session manager state (for testing only)."""
    global _session_manager
    if _session_manager is not None:
        # Cancel any pending reconnect task to prevent leaked asyncio tasks
        if _session_manager._reconnect_task and not _session_manager._reconnect_task.done():
            try:
                _session_manager._reconnect_task.cancel()
            except RuntimeError:
                pass  # Event loop already closed
            # Suppress "Task was destroyed but it is pending" noise at exit
            _session_manager._reconnect_task._log_destroy_pending = False
    _session_manager = None
