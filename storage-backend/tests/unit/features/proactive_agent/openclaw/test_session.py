"""Unit tests for OpenClaw session manager."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from features.proactive_agent.openclaw.config import OpenClawConfig, reset_config
from features.proactive_agent.openclaw.session import (
    OpenClawSessionManager,
    close_openclaw_session,
    reset_session_manager_for_testing,
)


@pytest.fixture
def mock_config():
    """Create a mock config."""
    return OpenClawConfig(
        gateway_url="ws://test:8080",
        gateway_token="test-token",
        client_id="test-client",
        client_version="1.0.0",
        platform="test",
        keypair_path="/tmp/test-device.json",
        token_cache_path="/tmp/test-tokens.json",
        enabled=True,
    )


class TestOpenClawSessionManager:
    """Test OpenClawSessionManager class."""

    def test_init_stores_config(self, mock_config):
        """Manager stores config."""
        manager = OpenClawSessionManager(mock_config)
        assert manager._config is mock_config
        assert manager._connected is False
        assert manager._client is None
        assert manager._adapter is None

    def test_connected_property_false_initially(self, mock_config):
        """connected is False initially."""
        manager = OpenClawSessionManager(mock_config)
        assert manager.connected is False

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, mock_config):
        """close cleans up resources."""
        manager = OpenClawSessionManager(mock_config)

        # Mock client
        mock_client = AsyncMock()
        manager._client = mock_client
        manager._connected = True

        await manager.close()

        mock_client.close.assert_called_once()
        assert manager._client is None
        assert manager._adapter is None
        assert manager._connected is False


class TestSessionManagerConnection:
    """Test connection flow."""

    @pytest.mark.asyncio
    async def test_get_adapter_connects_on_first_call(self, mock_config, tmp_path):
        """get_adapter establishes connection on first call."""
        # Update config to use temp paths
        mock_config.keypair_path = str(tmp_path / "device.json")
        mock_config.token_cache_path = str(tmp_path / "tokens.json")

        manager = OpenClawSessionManager(mock_config)

        # Mock the client and connection flow
        mock_client = MagicMock()
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value="test-nonce")
        mock_client.handshake = AsyncMock(return_value={
            "deviceToken": "new-device-token",
            "server": {"displayName": "Test Server"},
        })

        with patch(
            "features.proactive_agent.openclaw.session.OpenClawClient",
            return_value=mock_client,
        ):
            adapter = await manager.get_adapter()

        assert adapter is not None
        assert manager._connected is True
        mock_client.connect.assert_called_once()
        mock_client.handshake.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_adapter_reuses_connection(self, mock_config, tmp_path):
        """get_adapter reuses existing connection."""
        mock_config.keypair_path = str(tmp_path / "device.json")
        mock_config.token_cache_path = str(tmp_path / "tokens.json")

        manager = OpenClawSessionManager(mock_config)

        mock_client = MagicMock()
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value="test-nonce")
        mock_client.handshake = AsyncMock(return_value={
            "deviceToken": "token",
            "server": {"displayName": "Server"},
        })

        with patch(
            "features.proactive_agent.openclaw.session.OpenClawClient",
            return_value=mock_client,
        ):
            adapter1 = await manager.get_adapter()
            adapter2 = await manager.get_adapter()

        assert adapter1 is adapter2
        # connect should only be called once
        assert mock_client.connect.call_count == 1


class TestSessionManagerReconnect:
    """Test reconnection handling."""

    @pytest.mark.asyncio
    async def test_handle_disconnected_force_completes_streams(self, mock_config):
        """Disconnection force-completes active streams."""
        manager = OpenClawSessionManager(mock_config)

        # Setup mock adapter with active streams
        mock_adapter = MagicMock()
        mock_adapter.get_active_run_ids = MagicMock(return_value=["run-1", "run-2"])
        mock_adapter.force_complete_stream = AsyncMock(return_value=True)
        manager._adapter = mock_adapter
        manager._connected = True

        # Trigger disconnect handler
        await manager._handle_disconnected(Exception("Connection lost"))

        assert manager._connected is False
        mock_adapter.get_active_run_ids.assert_called_once()
        # Should force-complete each active stream
        assert mock_adapter.force_complete_stream.call_count == 2
        mock_adapter.force_complete_stream.assert_any_call("run-1", reason="disconnect")
        mock_adapter.force_complete_stream.assert_any_call("run-2", reason="disconnect")

        # Cleanup: cancel reconnect task spawned by _handle_disconnected
        if manager._reconnect_task and not manager._reconnect_task.done():
            manager._reconnect_task.cancel()
            try:
                await manager._reconnect_task
            except asyncio.CancelledError:
                pass


class TestCloseOpenClawSession:
    """Test module-level close function."""

    def setup_method(self):
        """Reset config and session manager before each test."""
        reset_config()
        reset_session_manager_for_testing()

    def teardown_method(self):
        """Reset config and session manager after each test."""
        reset_config()
        reset_session_manager_for_testing()

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """close_openclaw_session handles no session gracefully."""
        # Should not raise
        await close_openclaw_session()
