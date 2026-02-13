"""Video generation configuration defaults."""

from __future__ import annotations

# Global defaults for video flows
DEFAULT_PROVIDER = "gemini"
DEFAULT_DURATION = 5  # seconds
DEFAULT_ASPECT_RATIO = "16:9"

# Duration presets exposed to clients
DURATION_PRESETS = {
    "short": 5,
    "medium": 10,
    "long": 30,
}

# Aspect ratio presets for UI controls
ASPECT_RATIOS = {
    "square": "1:1",
    "landscape": "16:9",
    "portrait": "9:16",
    "cinematic": "21:9",
}

__all__ = [
    "DEFAULT_PROVIDER",
    "DEFAULT_DURATION",
    "DEFAULT_ASPECT_RATIO",
    "DURATION_PRESETS",
    "ASPECT_RATIOS",
]
