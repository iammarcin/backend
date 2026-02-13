"""xAI Grok image configuration."""

from __future__ import annotations

DEFAULT_MODEL = "grok-2-image"
SUPPORTED_MODELS = ["grok-2-image"]

DEFAULT_BASE_URL = "https://api.x.ai/v1"
IMAGES_ENDPOINT = "/images/generations"

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024

SUPPORTED_RESPONSE_FORMATS = ["b64_json", "url"]

__all__ = [
    "DEFAULT_MODEL",
    "SUPPORTED_MODELS",
    "DEFAULT_BASE_URL",
    "IMAGES_ENDPOINT",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "SUPPORTED_RESPONSE_FORMATS",
]
