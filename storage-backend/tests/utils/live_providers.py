"""Utilities shared across live provider integration tests.

These helpers keep the pytest modules lightweight while centralising the
logic that decides when we should skip a test because the execution
environment is not configured for real API traffic (missing credentials,
rate limits, etc.).
"""

from __future__ import annotations

import os

import pytest

from core.clients.ai import ai_clients
from core.exceptions import ProviderError, RateLimitError

RUN_MANUAL_TESTS = os.getenv("RUN_MANUAL_TESTS") == "1"


def require_manual_tests(reason: str = "manual/live provider tests") -> None:
    """Skip when the global manual test flag is disabled."""

    if RUN_MANUAL_TESTS:
        return
    pytest.skip(f"Set RUN_MANUAL_TESTS=1 to run {reason}")


def require_live_client(client_key: str, env_var: str) -> None:
    """Skip the calling test when the requested SDK client is unavailable."""

    require_manual_tests("live provider tests")

    if client_key in ai_clients:
        return

    if not os.getenv(env_var):
        pytest.skip(f"{env_var} is not configured; skipping live provider test")

    pytest.skip(
        "Live client '{client_key}' is missing even though {env_var} is set. "
        "Ensure `core.clients.ai` initialised the {client_key} entry before running these tests.".format(
            client_key=client_key, env_var=env_var
        )
    )


def skip_if_transient_provider_error(
    exc: ProviderError | RateLimitError,
    provider_name: str,
) -> None:
    """Convert transient provider failures into pytest skips."""

    message = str(getattr(exc, "message", exc)).lower()

    if isinstance(exc, RateLimitError) or "rate limit" in message:
        pytest.skip(f"{provider_name} rate limited the live test run: {exc}")

    transient_tokens = [
        "api key",
        "authentication",
        "authorization",
        "unauthorized",
        "not initialized",
        "permission",
        "access denied",
        "overloaded",
        "temporarily unavailable",
        "capacity",
    ]
    if any(token in message for token in transient_tokens):
        pytest.skip(f"{provider_name} credentials are not usable in this environment: {exc}")

    # Otherwise, leave the exception untouched so the caller can surface
    # real formatting/contract regressions.
