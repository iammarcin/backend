"""Unit tests for OpenClaw configuration."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from features.proactive_agent.openclaw.config import (
    OpenClawConfig,
    get_openclaw_config,
    is_openclaw_enabled,
    reset_config,
)


class TestOpenClawConfig:
    """Test OpenClawConfig dataclass."""

    def test_from_env_defaults(self):
        """from_env uses correct defaults when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            config = OpenClawConfig.from_env()

        assert config.gateway_url == "ws://100.89.249.49:18789"
        assert config.gateway_token == ""
        assert config.client_id == "gateway-client"
        assert config.client_version == "0.1.0"
        assert config.platform == "backend"
        assert config.keypair_path == "config/openclaw/device.json"
        assert config.token_cache_path == "config/openclaw/device_tokens.json"
        assert config.enabled is True

    def test_from_env_custom_values(self):
        """from_env reads custom env values."""
        env = {
            "OPENCLAW_GATEWAY_URL": "ws://custom:9999",
            "OPENCLAW_GATEWAY_TOKEN": "secret-token",
            "OPENCLAW_CLIENT_ID": "custom-client",
            "OPENCLAW_CLIENT_VERSION": "2.0.0",
            "OPENCLAW_PLATFORM": "custom-platform",
            "OPENCLAW_KEYPAIR_PATH": "/custom/path/device.json",
            "OPENCLAW_TOKEN_CACHE_PATH": "/custom/path/tokens.json",
            "OPENCLAW_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=True):
            config = OpenClawConfig.from_env()

        assert config.gateway_url == "ws://custom:9999"
        assert config.gateway_token == "secret-token"
        assert config.client_id == "custom-client"
        assert config.client_version == "2.0.0"
        assert config.platform == "custom-platform"
        assert config.keypair_path == "/custom/path/device.json"
        assert config.token_cache_path == "/custom/path/tokens.json"
        assert config.enabled is True

    def test_enabled_case_insensitive(self):
        """OPENCLAW_ENABLED is case insensitive."""
        for value in ["true", "True", "TRUE", "TrUe"]:
            with patch.dict(os.environ, {"OPENCLAW_ENABLED": value}, clear=True):
                config = OpenClawConfig.from_env()
                assert config.enabled is True

        for value in ["false", "False", "0", "", "no"]:
            with patch.dict(os.environ, {"OPENCLAW_ENABLED": value}, clear=True):
                config = OpenClawConfig.from_env()
                assert config.enabled is False


class TestConfigValidation:
    """Test config validation."""

    def test_validate_disabled_no_errors(self):
        """Disabled config has no validation errors."""
        config = OpenClawConfig(
            gateway_url="",
            gateway_token="",
            client_id="",
            client_version="",
            platform="",
            keypair_path="",
            token_cache_path="",
            enabled=False,
        )
        assert config.validate() == []

    def test_validate_enabled_missing_token(self):
        """Enabled config without token has error."""
        config = OpenClawConfig(
            gateway_url="ws://localhost:8080",
            gateway_token="",
            client_id="client",
            client_version="1.0",
            platform="backend",
            keypair_path="/path",
            token_cache_path="/path",
            enabled=True,
        )
        errors = config.validate()
        assert len(errors) == 1
        assert "OPENCLAW_GATEWAY_TOKEN" in errors[0]

    def test_validate_enabled_missing_url(self):
        """Enabled config without URL has error."""
        config = OpenClawConfig(
            gateway_url="",
            gateway_token="token",
            client_id="client",
            client_version="1.0",
            platform="backend",
            keypair_path="/path",
            token_cache_path="/path",
            enabled=True,
        )
        errors = config.validate()
        assert len(errors) == 1
        assert "OPENCLAW_GATEWAY_URL" in errors[0]

    def test_validate_enabled_valid(self):
        """Valid enabled config has no errors."""
        config = OpenClawConfig(
            gateway_url="ws://localhost:8080",
            gateway_token="token",
            client_id="client",
            client_version="1.0",
            platform="backend",
            keypair_path="/path",
            token_cache_path="/path",
            enabled=True,
        )
        assert config.validate() == []


class TestGetOpenClawConfig:
    """Test get_openclaw_config singleton."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_config()

    def test_get_openclaw_config_caches(self):
        """get_openclaw_config returns same instance."""
        with patch.dict(os.environ, {"OPENCLAW_ENABLED": "false"}, clear=True):
            config1 = get_openclaw_config()
            config2 = get_openclaw_config()

        assert config1 is config2

    def test_reset_config_clears_cache(self):
        """reset_config clears cached config."""
        with patch.dict(os.environ, {"OPENCLAW_GATEWAY_URL": "ws://first:1"}, clear=True):
            config1 = get_openclaw_config()

        reset_config()

        with patch.dict(os.environ, {"OPENCLAW_GATEWAY_URL": "ws://second:2"}, clear=True):
            config2 = get_openclaw_config()

        assert config1.gateway_url == "ws://first:1"
        assert config2.gateway_url == "ws://second:2"
        assert config1 is not config2


class TestIsOpenClawEnabled:
    """Test is_openclaw_enabled helper."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def teardown_method(self):
        """Reset config after each test."""
        reset_config()

    def test_is_openclaw_enabled_true(self):
        """Returns True when enabled."""
        with patch.dict(os.environ, {"OPENCLAW_ENABLED": "true"}, clear=True):
            assert is_openclaw_enabled() is True

    def test_is_openclaw_enabled_false(self):
        """Returns False when disabled."""
        with patch.dict(os.environ, {"OPENCLAW_ENABLED": "false"}, clear=True):
            assert is_openclaw_enabled() is False
