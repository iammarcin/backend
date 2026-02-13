"""Image generation configuration defaults."""

from __future__ import annotations

# Global defaults used by image flows
DEFAULT_PROVIDER = "openai"
DEFAULT_SIZE = "1024x1024"
DEFAULT_QUALITY = "standard"
DEFAULT_STYLE = "vivid"

# Common size presets for convenience
COMMON_SIZES = {
    "square": "1024x1024",
    "landscape": "1792x1024",
    "portrait": "1024x1792",
}

__all__ = [
    "DEFAULT_PROVIDER",
    "DEFAULT_SIZE",
    "DEFAULT_QUALITY",
    "DEFAULT_STYLE",
    "COMMON_SIZES",
]
