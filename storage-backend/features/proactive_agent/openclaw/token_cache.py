"""Token cache for OpenClaw device authentication.

This module manages device token caching for reconnection:
- Caches tokens per device ID and role
- Uses JSON file storage with restrictive permissions
- Handles corrupted cache files gracefully
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TokenCache:
    """Manages device token caching for OpenClaw Gateway.

    Tokens are cached per device ID and role combination, allowing
    quick reconnection without re-authentication.

    Usage:
        cache = TokenCache("/path/to/tokens.json")
        cache.cache_token(device_id="abc", token="xyz", role="operator")
        token = cache.get_token(device_id="abc", role="operator")
        cache.clear_token(device_id="abc", role="operator")
    """

    DEFAULT_ROLE = "operator"

    def __init__(self, cache_path: Optional[str] = None):
        """Initialize TokenCache.

        Args:
            cache_path: Path to token cache JSON file (optional)
        """
        self._cache_path = Path(cache_path) if cache_path else None

    def get_token(self, device_id: str, role: Optional[str] = None) -> Optional[str]:
        """Get cached device token for this device and role.

        Args:
            device_id: Device ID (hex string)
            role: Access role (defaults to DEFAULT_ROLE)

        Returns:
            Cached token string, or None if not found
        """
        if not self._cache_path or not self._cache_path.exists():
            return None

        role = role or self.DEFAULT_ROLE
        cache_key = f"{device_id}:{role}"

        try:
            cache = json.loads(self._cache_path.read_text())
            return cache.get(cache_key)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read token cache: {e}")
            return None

    def cache_token(
        self, device_id: str, token: str, role: Optional[str] = None
    ) -> None:
        """Cache device token for reuse.

        Args:
            device_id: Device ID (hex string)
            token: Device token from hello-ok response
            role: Access role (defaults to DEFAULT_ROLE)
        """
        if not self._cache_path:
            logger.debug("No token cache path configured, skipping cache")
            return

        role = role or self.DEFAULT_ROLE
        cache_key = f"{device_id}:{role}"

        # Load existing cache or create new
        cache: dict[str, str] = {}
        if self._cache_path.exists():
            try:
                cache = json.loads(self._cache_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        cache[cache_key] = token

        # Write cache
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(cache, indent=2))
        self._cache_path.chmod(0o600)

        logger.debug(f"Cached token for {cache_key[:24]}...")

    def clear_token(self, device_id: str, role: Optional[str] = None) -> None:
        """Clear cached token for this device and role.

        Args:
            device_id: Device ID (hex string)
            role: Access role (defaults to DEFAULT_ROLE)
        """
        if not self._cache_path or not self._cache_path.exists():
            return

        role = role or self.DEFAULT_ROLE
        cache_key = f"{device_id}:{role}"

        try:
            cache = json.loads(self._cache_path.read_text())
            if cache_key in cache:
                del cache[cache_key]
                self._cache_path.write_text(json.dumps(cache, indent=2))
                logger.debug(f"Cleared cached token for {cache_key[:24]}...")
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to clear token cache: {e}")
