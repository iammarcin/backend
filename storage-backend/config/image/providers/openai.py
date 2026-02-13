"""OpenAI image generation configuration."""

from __future__ import annotations

DEFAULT_MODEL = "gpt-image-1.5"
SUPPORTED_MODELS = ["gpt-image-1.5", "gpt-image-1", "gpt-image-1-mini", "dall-e-2", "dall-e-3"]

DEFAULT_SIZE = "1024x1024"
SUPPORTED_SIZES = ["256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"]

DEFAULT_QUALITY = "standard"
SUPPORTED_QUALITIES = ["standard", "hd"]

__all__ = [
    "DEFAULT_MODEL",
    "SUPPORTED_MODELS",
    "DEFAULT_SIZE",
    "SUPPORTED_SIZES",
    "DEFAULT_QUALITY",
    "SUPPORTED_QUALITIES",
]
