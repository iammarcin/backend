"""Authentication utilities for KlingAI API."""

import time
from typing import Optional

from jose import jwt


class KlingAIAuth:
    """Handles JWT token generation for KlingAI API authentication."""

    def __init__(self, access_key: str, secret_key: str):
        """
        Initialize KlingAI authentication.

        Args:
            access_key: KlingAI access key
            secret_key: KlingAI secret key

        Raises:
            ValueError: If access_key or secret_key is empty
        """
        if not access_key:
            raise ValueError("KLINGAI_ACCESS_KEY is required")
        if not secret_key:
            raise ValueError("KLINGAI_SECRET_KEY is required")

        self.access_key = access_key
        self.secret_key = secret_key
        self._cached_token: Optional[str] = None
        self._token_expiry: int = 0

    def get_token(self, validity_seconds: int = 1800) -> str:
        """
        Generate or retrieve cached JWT token.

        Args:
            validity_seconds: Token validity duration (default: 1800s = 30 min)

        Returns:
            JWT token string

        Note:
            Tokens are cached and reused if still valid (with 60s buffer)
        """
        current_time = int(time.time())

        # Return cached token if still valid (with 60s buffer)
        if self._cached_token and current_time < (self._token_expiry - 60):
            return self._cached_token

        # Generate new token
        headers = {
            "alg": "HS256",
            "typ": "JWT"
        }

        payload = {
            "iss": self.access_key,
            "exp": current_time + validity_seconds,  # Token expiration time
            "nbf": current_time - 5  # Token start time (5s before now)
        }

        token = jwt.encode(payload, self.secret_key, headers=headers)

        # Cache token
        self._cached_token = token
        self._token_expiry = payload["exp"]

        return token

    def get_auth_header(self) -> dict[str, str]:
        """
        Get Authorization header for API requests.

        Returns:
            Dictionary with Authorization header

        Example:
            {"Authorization": "Bearer <token>"}
        """
        token = self.get_token()
        return {"Authorization": f"Bearer {token}"}

    def invalidate_cache(self) -> None:
        """Invalidate cached token (force regeneration on next request)."""
        self._cached_token = None
        self._token_expiry = 0
