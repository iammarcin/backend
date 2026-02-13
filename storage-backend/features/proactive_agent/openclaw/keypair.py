"""Ed25519 keypair management for OpenClaw device authentication.

This module handles keypair generation, persistence, and loading:
- Ed25519 keypair generation
- PEM format serialization
- Device ID computation (SHA256 of raw public key)
- Secure file permissions
"""

import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

logger = logging.getLogger(__name__)


class KeypairManager:
    """Manages Ed25519 keypair generation and persistence.

    This class handles:
    - Generating new Ed25519 keypairs
    - Loading existing keypairs from JSON files
    - Computing device IDs from public keys
    - Encoding public keys for authentication
    """

    def __init__(self, keypair_path: str):
        """Initialize keypair manager.

        Args:
            keypair_path: Path to keypair JSON file (created if not exists)
        """
        self._keypair_path = Path(keypair_path)
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._device_id: Optional[str] = None

    @property
    def device_id(self) -> Optional[str]:
        """Get device ID (hex SHA256 of raw public key)."""
        return self._device_id

    @property
    def initialized(self) -> bool:
        """Return True if keypair is loaded."""
        return self._private_key is not None

    @property
    def private_key(self) -> Optional[Ed25519PrivateKey]:
        """Get the private key (for signing)."""
        return self._private_key

    def load_or_generate(self) -> None:
        """Load existing keypair or generate a new one.

        Creates parent directories if needed.
        Sets file permissions to 0600 for security.
        """
        if self._keypair_path.exists():
            self._load_existing()
        else:
            self._generate_new()

    def _load_existing(self) -> None:
        """Load keypair from existing file."""
        logger.info(f"Loading keypair from {self._keypair_path}")

        data = json.loads(self._keypair_path.read_text())
        self._private_key = serialization.load_pem_private_key(
            data["privateKeyPem"].encode(),
            password=None,
        )
        self._device_id = data["deviceId"]

        # Verify device ID matches
        computed_id = self._compute_device_id()
        if computed_id != self._device_id:
            raise ValueError(
                f"Device ID mismatch: stored={self._device_id}, computed={computed_id}"
            )

        logger.info(f"Loaded device: {self._device_id[:16]}...")

    def _generate_new(self) -> None:
        """Generate new Ed25519 keypair and save to file."""
        logger.info(f"Generating new keypair at {self._keypair_path}")

        self._private_key = Ed25519PrivateKey.generate()
        self._device_id = self._compute_device_id()

        # Serialize keys to PEM
        private_pem = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_key = self._private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

        data = {
            "privateKeyPem": private_pem,
            "publicKeyPem": public_pem,
            "deviceId": self._device_id,
        }

        # Create directory and write file
        self._keypair_path.parent.mkdir(parents=True, exist_ok=True)
        self._keypair_path.write_text(json.dumps(data, indent=2))
        self._keypair_path.chmod(0o600)

        logger.info(f"Generated new device: {self._device_id[:16]}...")

    def _compute_device_id(self) -> str:
        """Compute device ID from raw public key bytes.

        Returns:
            Hex SHA256 of raw public key (64 hex characters)
        """
        public_key = self._private_key.public_key()
        public_raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return hashlib.sha256(public_raw).hexdigest()

    def public_key_base64url(self) -> str:
        """Return base64url-encoded raw public key (no padding).

        Returns:
            Base64url string without padding

        Raises:
            RuntimeError: If keypair not loaded
        """
        if not self._private_key:
            raise RuntimeError("Keypair not loaded - call load_or_generate() first")

        public_key = self._private_key.public_key()
        public_raw = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return base64.urlsafe_b64encode(public_raw).decode().rstrip("=")
