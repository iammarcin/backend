"""Unit tests for OpenClaw device authentication."""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from features.proactive_agent.openclaw.auth import DeviceAuth


class TestDeviceAuthInit:
    """Test DeviceAuth initialization."""

    def test_init_stores_paths(self, tmp_path: Path):
        """Constructor stores keypair and token cache paths."""
        keypair_path = tmp_path / "device.json"
        token_path = tmp_path / "tokens.json"

        auth = DeviceAuth(
            keypair_path=str(keypair_path),
            token_cache_path=str(token_path),
        )

        assert auth._keypair_path == keypair_path
        assert auth._token_cache_path == token_path

    def test_init_token_cache_optional(self, tmp_path: Path):
        """Token cache path is optional."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        assert auth._token_cache_path is None

    def test_init_not_initialized(self, tmp_path: Path):
        """DeviceAuth starts uninitialized."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        assert auth.initialized is False
        assert auth.device_id is None


class TestKeypairGeneration:
    """Test keypair generation and loading."""

    def test_generate_new_keypair(self, tmp_path: Path):
        """Generates new keypair when file doesn't exist."""
        keypair_path = tmp_path / "device.json"
        auth = DeviceAuth(keypair_path=str(keypair_path))

        auth.load_or_generate_keypair()

        assert auth.initialized
        assert auth.device_id is not None
        assert keypair_path.exists()

    def test_device_id_is_64_hex_chars(self, tmp_path: Path):
        """Device ID is 64 hex characters (SHA256)."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        assert len(auth.device_id) == 64
        assert re.match(r"^[0-9a-f]{64}$", auth.device_id)

    def test_keypair_file_format(self, tmp_path: Path):
        """Keypair file contains PEM keys and device ID."""
        keypair_path = tmp_path / "device.json"
        auth = DeviceAuth(keypair_path=str(keypair_path))
        auth.load_or_generate_keypair()

        data = json.loads(keypair_path.read_text())

        assert "privateKeyPem" in data
        assert "publicKeyPem" in data
        assert "deviceId" in data
        assert data["privateKeyPem"].startswith("-----BEGIN PRIVATE KEY-----")
        assert data["publicKeyPem"].startswith("-----BEGIN PUBLIC KEY-----")
        assert data["deviceId"] == auth.device_id

    def test_keypair_file_permissions(self, tmp_path: Path):
        """Keypair file has restrictive permissions (0600)."""
        keypair_path = tmp_path / "device.json"
        auth = DeviceAuth(keypair_path=str(keypair_path))
        auth.load_or_generate_keypair()

        # Check permissions (owner read/write only)
        mode = keypair_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_load_existing_keypair(self, tmp_path: Path):
        """Loads existing keypair from file."""
        keypair_path = tmp_path / "device.json"

        # Generate first
        auth1 = DeviceAuth(keypair_path=str(keypair_path))
        auth1.load_or_generate_keypair()
        original_id = auth1.device_id

        # Load into new instance
        auth2 = DeviceAuth(keypair_path=str(keypair_path))
        auth2.load_or_generate_keypair()

        assert auth2.device_id == original_id
        assert auth2.initialized

    def test_creates_parent_directories(self, tmp_path: Path):
        """Creates parent directories for keypair file."""
        keypair_path = tmp_path / "deep" / "nested" / "device.json"
        auth = DeviceAuth(keypair_path=str(keypair_path))
        auth.load_or_generate_keypair()

        assert keypair_path.exists()

    def test_device_id_mismatch_raises(self, tmp_path: Path):
        """Raises error if stored device ID doesn't match computed."""
        keypair_path = tmp_path / "device.json"

        # Generate keypair
        auth = DeviceAuth(keypair_path=str(keypair_path))
        auth.load_or_generate_keypair()

        # Tamper with device ID
        data = json.loads(keypair_path.read_text())
        data["deviceId"] = "0" * 64
        keypair_path.write_text(json.dumps(data))

        # Load should fail
        auth2 = DeviceAuth(keypair_path=str(keypair_path))
        with pytest.raises(ValueError, match="Device ID mismatch"):
            auth2.load_or_generate_keypair()


class TestPublicKeyBase64url:
    """Test public key encoding."""

    def test_public_key_base64url_format(self, tmp_path: Path):
        """Public key is base64url encoded without padding."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        pub_key = auth.public_key_base64url()

        # Ed25519 public key is 32 bytes = 43 base64 chars (without padding)
        assert len(pub_key) == 43
        # No padding
        assert "=" not in pub_key
        # Valid base64url chars only
        assert re.match(r"^[A-Za-z0-9_-]+$", pub_key)

    def test_public_key_decodes_to_valid_key(self, tmp_path: Path):
        """Base64url can be decoded back to valid public key."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        pub_key_b64 = auth.public_key_base64url()

        # Add padding for decoding
        padded = pub_key_b64 + "=" * (4 - len(pub_key_b64) % 4)
        raw_bytes = base64.urlsafe_b64decode(padded)

        # Should be 32 bytes (Ed25519 public key size)
        assert len(raw_bytes) == 32

        # Should be loadable as Ed25519 public key
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        pub_key = Ed25519PublicKey.from_public_bytes(raw_bytes)
        assert pub_key is not None

    def test_public_key_not_loaded_raises(self, tmp_path: Path):
        """Raises if keypair not loaded."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))

        with pytest.raises(RuntimeError, match="Keypair not loaded"):
            auth.public_key_base64url()


class TestSignPayload:
    """Test payload signing."""

    def test_sign_payload_returns_signature_and_timestamp(self, tmp_path: Path):
        """sign_payload returns signature and timestamp."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        signature, signed_at = auth.sign_payload(
            client_id="gateway-client",
            client_mode="backend",
            role="operator",
            scopes=["operator.read", "operator.write"],
            auth_token="test-token",
            nonce="test-nonce",
        )

        # Signature is base64url
        assert re.match(r"^[A-Za-z0-9_-]+$", signature)
        # Timestamp is reasonable (within last minute)
        import time

        now_ms = int(time.time() * 1000)
        assert now_ms - 60000 < signed_at < now_ms + 1000

    def test_signature_is_valid_ed25519(self, tmp_path: Path):
        """Signature can be verified with public key."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        signature_b64, signed_at = auth.sign_payload(
            client_id="gateway-client",
            client_mode="backend",
            role="operator",
            scopes=["operator.read", "operator.write"],
            auth_token="test-token",
            nonce="test-nonce",
        )

        # Reconstruct payload
        payload = "|".join([
            "v2",
            auth.device_id,
            "gateway-client",
            "backend",
            "operator",
            "operator.read,operator.write",
            str(signed_at),
            "test-token",
            "test-nonce",
        ])

        # Decode signature (add padding)
        padded = signature_b64 + "=" * (4 - len(signature_b64) % 4)
        signature = base64.urlsafe_b64decode(padded)

        # Verify with public key
        pub_key_b64 = auth.public_key_base64url()
        padded_pub = pub_key_b64 + "=" * (4 - len(pub_key_b64) % 4)
        pub_bytes = base64.urlsafe_b64decode(padded_pub)
        pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

        # Should not raise
        pub_key.verify(signature, payload.encode("utf-8"))

    def test_signature_uses_exact_token(self, tmp_path: Path):
        """Signature payload includes exact auth token."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        # Different tokens should produce different signatures
        sig1, _ = auth.sign_payload(
            client_id="gc",
            client_mode="backend",
            role="op",
            scopes=["s"],
            auth_token="token-A",
            nonce="nonce",
        )
        sig2, _ = auth.sign_payload(
            client_id="gc",
            client_mode="backend",
            role="op",
            scopes=["s"],
            auth_token="token-B",
            nonce="nonce",
        )

        assert sig1 != sig2

    def test_sign_payload_not_loaded_raises(self, tmp_path: Path):
        """Raises if keypair not loaded."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))

        with pytest.raises(RuntimeError, match="Keypair not loaded"):
            auth.sign_payload(
                client_id="gc",
                client_mode="backend",
                role="op",
                scopes=["s"],
                auth_token="t",
                nonce="n",
            )


class TestBuildConnectParams:
    """Test connect params building."""

    def test_build_connect_params_structure(self, tmp_path: Path):
        """build_connect_params returns correct structure."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        params = auth.build_connect_params(
            client_id="gateway-client",
            client_version="0.1.0",
            platform="backend",
            gateway_token="gw-token",
            nonce="challenge-nonce",
        )

        # Check top-level keys
        assert params["minProtocol"] == 3
        assert params["maxProtocol"] == 3
        assert params["role"] == "operator"
        assert params["scopes"] == ["operator.read", "operator.write"]

        # Check client
        assert params["client"]["id"] == "gateway-client"
        assert params["client"]["displayName"] == "backend-adapter"
        assert params["client"]["version"] == "0.1.0"
        assert params["client"]["platform"] == "backend"
        assert params["client"]["mode"] == "backend"

        # Check auth
        assert params["auth"]["token"] == "gw-token"

        # Check device
        assert params["device"]["id"] == auth.device_id
        assert params["device"]["publicKey"] == auth.public_key_base64url()
        assert "signature" in params["device"]
        assert "signedAt" in params["device"]
        assert params["device"]["nonce"] == "challenge-nonce"

    def test_uses_stored_token_if_provided(self, tmp_path: Path):
        """Uses stored device token over gateway token."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        params = auth.build_connect_params(
            client_id="gc",
            client_version="1.0",
            platform="backend",
            gateway_token="gw-token",
            nonce="nonce",
            stored_device_token="device-token",
        )

        assert params["auth"]["token"] == "device-token"

    def test_uses_gateway_token_when_no_stored_token(self, tmp_path: Path):
        """Falls back to gateway token when no stored token."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        params = auth.build_connect_params(
            client_id="gc",
            client_version="1.0",
            platform="backend",
            gateway_token="gw-token",
            nonce="nonce",
        )

        assert params["auth"]["token"] == "gw-token"


class TestTokenCache:
    """Test device token caching."""

    def test_cache_and_retrieve_token(self, tmp_path: Path):
        """Can cache and retrieve device token."""
        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(tmp_path / "tokens.json"),
        )
        auth.load_or_generate_keypair()

        auth.cache_token("my-device-token")
        retrieved = auth.get_cached_token()

        assert retrieved == "my-device-token"

    def test_get_cached_token_returns_none_if_not_cached(self, tmp_path: Path):
        """Returns None if no token cached."""
        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(tmp_path / "tokens.json"),
        )
        auth.load_or_generate_keypair()

        assert auth.get_cached_token() is None

    def test_get_cached_token_returns_none_without_cache_path(self, tmp_path: Path):
        """Returns None if no cache path configured."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        assert auth.get_cached_token() is None

    def test_cache_token_noop_without_cache_path(self, tmp_path: Path):
        """cache_token is no-op without cache path."""
        auth = DeviceAuth(keypair_path=str(tmp_path / "device.json"))
        auth.load_or_generate_keypair()

        # Should not raise
        auth.cache_token("token")

    def test_clear_cached_token(self, tmp_path: Path):
        """Can clear cached token."""
        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(tmp_path / "tokens.json"),
        )
        auth.load_or_generate_keypair()

        auth.cache_token("my-token")
        assert auth.get_cached_token() == "my-token"

        auth.clear_cached_token()
        assert auth.get_cached_token() is None

    def test_token_cache_is_role_specific(self, tmp_path: Path):
        """Tokens are cached per role."""
        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(tmp_path / "tokens.json"),
        )
        auth.load_or_generate_keypair()

        auth.cache_token("operator-token", role="operator")
        auth.cache_token("viewer-token", role="viewer")

        assert auth.get_cached_token(role="operator") == "operator-token"
        assert auth.get_cached_token(role="viewer") == "viewer-token"

    def test_token_cache_file_permissions(self, tmp_path: Path):
        """Token cache file has restrictive permissions."""
        cache_path = tmp_path / "tokens.json"
        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(cache_path),
        )
        auth.load_or_generate_keypair()
        auth.cache_token("token")

        mode = cache_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_multiple_devices_in_cache(self, tmp_path: Path):
        """Multiple devices can store tokens in same cache file."""
        cache_path = tmp_path / "tokens.json"

        # Device 1
        auth1 = DeviceAuth(
            keypair_path=str(tmp_path / "device1.json"),
            token_cache_path=str(cache_path),
        )
        auth1.load_or_generate_keypair()
        auth1.cache_token("token1")

        # Device 2
        auth2 = DeviceAuth(
            keypair_path=str(tmp_path / "device2.json"),
            token_cache_path=str(cache_path),
        )
        auth2.load_or_generate_keypair()
        auth2.cache_token("token2")

        # Both should work
        assert auth1.get_cached_token() == "token1"
        assert auth2.get_cached_token() == "token2"

    def test_handles_corrupted_cache_file(self, tmp_path: Path):
        """Handles corrupted cache file gracefully."""
        cache_path = tmp_path / "tokens.json"
        cache_path.write_text("not valid json{{{")

        auth = DeviceAuth(
            keypair_path=str(tmp_path / "device.json"),
            token_cache_path=str(cache_path),
        )
        auth.load_or_generate_keypair()

        # Should return None, not raise
        assert auth.get_cached_token() is None

        # Should be able to overwrite
        auth.cache_token("new-token")
        assert auth.get_cached_token() == "new-token"
