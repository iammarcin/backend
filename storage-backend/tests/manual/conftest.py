"""Fixtures for manual Gemini tests.

These helpers intentionally skip the manual suites when the required
environment variables or backend dependencies are missing so that enabling
``RUN_MANUAL_TESTS`` does not turn missing inputs into hard failures.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest


RUN_FLAG = "RUN_MANUAL_TESTS"
AUDIO_ENV_VAR = "GEMINI_MANUAL_AUDIO_PATH"
DEFAULT_AUDIO_PATH = "tests/manual/fixtures/test_audio.wav"
BASE_URL_ENV = "GEMINI_MANUAL_BASE_URL"
BEARER_TOKEN_ENV = "MY_AUTH_BEARER_TOKEN"


def _require_manual_mode() -> None:
    """Skip fixtures when manual Gemini tests are not enabled."""

    if not os.getenv(RUN_FLAG):
        pytest.skip("Manual Gemini tests are disabled")


@pytest.fixture(scope="session")
def audio_path() -> Path:
    """Resolve the manual audio sample path from the environment."""

    _require_manual_mode()
    path_value = os.getenv(AUDIO_ENV_VAR, DEFAULT_AUDIO_PATH)

    resolved_path = Path(path_value).expanduser().resolve()
    if not resolved_path.exists():
        pytest.skip(f"Audio file not found at {resolved_path}. Expected: {DEFAULT_AUDIO_PATH}")

    if resolved_path.suffix.lower() != ".wav":
        pytest.skip("Manual Gemini tests currently support only WAV audio inputs")

    return resolved_path


@pytest.fixture(scope="session")
def audio_file_path(audio_path: Path) -> str:
    """Return the resolved audio path as a string for compatibility tests."""

    return str(audio_path)


@pytest.fixture(scope="session")
def token() -> str:
    """Get JWT token from environment or skip when unavailable."""

    _require_manual_mode()

    token_value = os.getenv(BEARER_TOKEN_ENV)
    if not token_value:
        pytest.skip(f"MY_AUTH_BEARER_TOKEN not set for manual Gemini tests")

    return token_value
