"""KlingAI video generation configuration."""

from __future__ import annotations

import os

# API credentials
ACCESS_KEY = os.getenv("KLINGAI_ACCESS_KEY", "")
SECRET_KEY = os.getenv("KLINGAI_SECRET_KEY", "")
API_BASE_URL = os.getenv("KLINGAI_API_BASE_URL", "https://api-singapore.klingai.com")

# Model defaults
DEFAULT_MODEL = os.getenv("KLINGAI_DEFAULT_MODEL", "kling-v1")
DEFAULT_MODE = os.getenv("KLINGAI_DEFAULT_MODE", "std")
DEFAULT_DURATION = int(os.getenv("KLINGAI_DEFAULT_DURATION", "5"))
DEFAULT_ASPECT_RATIO = os.getenv("KLINGAI_DEFAULT_ASPECT_RATIO", "16:9")

# Polling settings
POLL_INTERVAL = float(os.getenv("KLINGAI_POLL_INTERVAL", "5.0"))
TIMEOUT = float(os.getenv("KLINGAI_TIMEOUT", "300.0"))
MAX_POLL_ATTEMPTS = int(os.getenv("KLINGAI_MAX_POLL_ATTEMPTS", "60"))

__all__ = [
    "ACCESS_KEY",
    "SECRET_KEY",
    "API_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_MODE",
    "DEFAULT_DURATION",
    "DEFAULT_ASPECT_RATIO",
    "POLL_INTERVAL",
    "TIMEOUT",
    "MAX_POLL_ATTEMPTS",
]
