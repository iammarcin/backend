"""Google Gemini image configuration."""

from __future__ import annotations

DEFAULT_IMAGEN_MODEL = "imagen-4.0-generate-001"
DEFAULT_FLASH_MODEL = "gemini-2.5-flash-image"

SUPPORTED_IMAGEN_MODELS = [
    "imagen-4.0-generate-001",
]

SUPPORTED_FLASH_MODELS = [
    "gemini-3-pro-image-preview",  # Nano Banana Pro
    "gemini-2.5-flash-image",  # Nano Banana
    "gemini-2.0-flash",
]

DEFAULT_ASPECT_RATIO = "1:1"
SUPPORTED_ASPECT_RATIOS = ["1:1", "16:9", "9:16"]

__all__ = [
    "DEFAULT_IMAGEN_MODEL",
    "DEFAULT_FLASH_MODEL",
    "SUPPORTED_IMAGEN_MODELS",
    "SUPPORTED_FLASH_MODELS",
    "DEFAULT_ASPECT_RATIO",
    "SUPPORTED_ASPECT_RATIOS",
]
