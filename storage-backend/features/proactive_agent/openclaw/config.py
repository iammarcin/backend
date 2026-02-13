"""OpenClaw configuration loading from environment variables.

Environment Variables:
- OPENCLAW_ENABLED: Enable OpenClaw routing (default: false)
- OPENCLAW_GATEWAY_URL: WebSocket URL (default: ws://100.89.249.49:18789)
- OPENCLAW_GATEWAY_TOKEN: Gateway auth token (required when enabled)
- OPENCLAW_CLIENT_ID: Client identifier (default: gateway-client)
- OPENCLAW_CLIENT_VERSION: Client version (default: 0.1.0)
- OPENCLAW_PLATFORM: Platform identifier (default: backend)
- OPENCLAW_KEYPAIR_PATH: Path to device keypair JSON
- OPENCLAW_TOKEN_CACHE_PATH: Path to token cache JSON
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OpenClawConfig:
    """OpenClaw Gateway configuration."""

    gateway_url: str
    gateway_token: str
    client_id: str
    client_version: str
    platform: str
    keypair_path: str
    token_cache_path: str
    enabled: bool

    @classmethod
    def from_env(cls) -> "OpenClawConfig":
        """Load configuration from environment variables."""
        return cls(
            gateway_url=os.getenv(
                "OPENCLAW_GATEWAY_URL", "ws://100.89.249.49:18789"
            ),
            gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN", ""),
            client_id=os.getenv("OPENCLAW_CLIENT_ID", "gateway-client"),
            client_version=os.getenv("OPENCLAW_CLIENT_VERSION", "0.1.0"),
            platform=os.getenv("OPENCLAW_PLATFORM", "backend"),
            keypair_path=os.getenv(
                "OPENCLAW_KEYPAIR_PATH",
                "config/openclaw/device.json",
            ),
            token_cache_path=os.getenv(
                "OPENCLAW_TOKEN_CACHE_PATH",
                "config/openclaw/device_tokens.json",
            ),
            enabled=os.getenv("OPENCLAW_ENABLED", "true").lower() == "true",
        )

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if self.enabled:
            if not self.gateway_token:
                errors.append("OPENCLAW_GATEWAY_TOKEN is required when enabled")
            if not self.gateway_url:
                errors.append("OPENCLAW_GATEWAY_URL is required")
        return errors


_config: Optional[OpenClawConfig] = None


def get_openclaw_config() -> OpenClawConfig:
    """Get OpenClaw configuration (cached singleton)."""
    global _config
    if _config is None:
        _config = OpenClawConfig.from_env()
        if _config.enabled:
            errors = _config.validate()
            if errors:
                logger.error("OpenClaw config validation failed: %s", errors)
            else:
                logger.info(
                    "OpenClaw enabled: url=%s, client=%s",
                    _config.gateway_url,
                    _config.client_id,
                )
        else:
            logger.debug("OpenClaw disabled")
    return _config


def is_openclaw_enabled() -> bool:
    """Check if OpenClaw is enabled."""
    return get_openclaw_config().enabled


def reset_config() -> None:
    """Reset cached config (for testing)."""
    global _config
    _config = None
