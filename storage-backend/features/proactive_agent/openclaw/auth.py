"""Device authentication for OpenClaw Gateway.

This module manages device identity and authentication:
- Ed25519 keypair management (via KeypairManager)
- Signature payload creation for connect handshake
- Device token caching (via TokenCache)

Protocol: OpenClaw Gateway v2 device authentication
"""

import base64
import logging
import time
from typing import Any, Optional

from .keypair import KeypairManager
from .token_cache import TokenCache

logger = logging.getLogger(__name__)


class DeviceAuth:
    """Manages device identity and authentication for OpenClaw Gateway.

    Responsibilities:
    - Generate/load Ed25519 keypair (via KeypairManager)
    - Sign authentication payloads
    - Store/retrieve device tokens (via TokenCache)
    """

    SIGNATURE_VERSION = "v2"
    DEFAULT_ROLE = "operator"
    DEFAULT_SCOPES = ["operator.read", "operator.write"]
    DEFAULT_MODE = "backend"

    def __init__(
        self,
        keypair_path: str,
        token_cache_path: Optional[str] = None,
    ):
        """Initialize DeviceAuth.

        Args:
            keypair_path: Path to keypair JSON file (created if not exists)
            token_cache_path: Path to token cache JSON file (optional)
        """
        self._keypair_manager = KeypairManager(keypair_path)
        self._token_cache = TokenCache(token_cache_path)
        # Keep path references for backwards compatibility
        from pathlib import Path
        self._keypair_path = Path(keypair_path)
        self._token_cache_path = Path(token_cache_path) if token_cache_path else None

    @property
    def device_id(self) -> Optional[str]:
        """Get device ID (hex SHA256 of raw public key)."""
        return self._keypair_manager.device_id

    @property
    def initialized(self) -> bool:
        """Return True if keypair is loaded."""
        return self._keypair_manager.initialized

    def load_or_generate_keypair(self) -> None:
        """Load existing keypair or generate a new one."""
        self._keypair_manager.load_or_generate()

    def public_key_base64url(self) -> str:
        """Return base64url-encoded raw public key (no padding)."""
        return self._keypair_manager.public_key_base64url()

    def sign_payload(
        self,
        client_id: str,
        client_mode: str,
        role: str,
        scopes: list[str],
        auth_token: str,
        nonce: str,
    ) -> tuple[str, int]:
        """Create and sign device authentication payload.

        Payload format (pipe-delimited):
        v2|{deviceId}|{clientId}|{clientMode}|{role}|{scopes}|{signedAtMs}|{token}|{nonce}

        Args:
            client_id: Gateway client ID (e.g., "gateway-client")
            client_mode: Gateway client mode (e.g., "backend")
            role: Access role (e.g., "operator")
            scopes: Permission scopes
            auth_token: Exact token used in connect.params.auth.token
            nonce: Challenge nonce from gateway

        Returns:
            Tuple of (base64url_signature, signed_at_ms)
        """
        private_key = self._keypair_manager.private_key
        if not private_key:
            raise RuntimeError("Keypair not loaded - call load_or_generate_keypair() first")

        signed_at_ms = int(time.time() * 1000)

        payload = "|".join([
            self.SIGNATURE_VERSION,
            self._keypair_manager.device_id,
            client_id,
            client_mode,
            role,
            ",".join(scopes),
            str(signed_at_ms),
            auth_token or "",
            nonce or "",
        ])

        signature = private_key.sign(payload.encode("utf-8"))
        signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        logger.debug(f"Signed payload for device {self._keypair_manager.device_id[:16]}...")
        return signature_b64, signed_at_ms

    def build_connect_params(
        self,
        client_id: str,
        client_version: str,
        platform: str,
        gateway_token: str,
        nonce: str,
        stored_device_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build complete connect request params for handshake.

        Args:
            client_id: Gateway client ID (enum value)
            client_version: Client version string
            platform: Platform identifier
            gateway_token: Gateway auth token from config
            nonce: Challenge nonce from gateway
            stored_device_token: Previously cached device token (optional)

        Returns:
            Full params dict for connect request
        """
        role = self.DEFAULT_ROLE
        scopes = self.DEFAULT_SCOPES
        mode = self.DEFAULT_MODE

        auth_token = stored_device_token or gateway_token

        signature, signed_at_ms = self.sign_payload(
            client_id=client_id,
            client_mode=mode,
            role=role,
            scopes=scopes,
            auth_token=auth_token,
            nonce=nonce,
        )

        return {
            "minProtocol": 3,
            "maxProtocol": 3,
            "client": {
                "id": client_id,
                "displayName": "backend-adapter",
                "version": client_version,
                "platform": platform,
                "mode": mode,
            },
            "role": role,
            "scopes": scopes,
            "auth": {"token": auth_token},
            "device": {
                "id": self._keypair_manager.device_id,
                "publicKey": self.public_key_base64url(),
                "signature": signature,
                "signedAt": signed_at_ms,
                "nonce": nonce,
            },
        }

    # Token cache methods (delegated to TokenCache)

    def get_cached_token(self, role: Optional[str] = None) -> Optional[str]:
        """Get cached device token for this device and role."""
        if not self._keypair_manager.device_id:
            return None
        return self._token_cache.get_token(self._keypair_manager.device_id, role)

    def cache_token(self, token: str, role: Optional[str] = None) -> None:
        """Cache device token for reuse."""
        if not self._keypair_manager.device_id:
            return
        self._token_cache.cache_token(self._keypair_manager.device_id, token, role)

    def clear_cached_token(self, role: Optional[str] = None) -> None:
        """Clear cached token for this device and role."""
        if not self._keypair_manager.device_id:
            return
        self._token_cache.clear_token(self._keypair_manager.device_id, role)
