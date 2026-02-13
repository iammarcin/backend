"""Stability AI image configuration."""

from __future__ import annotations

DEFAULT_MODEL = "core"
SUPPORTED_MODELS = ["core", "sd3", "sd3.5", "sdxl", "core-night"]

DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024

OPTIONAL_FIELDS = [
    "negative_prompt",
    "seed",
    "cfg_scale",
    "style_preset",
    "mode",
]

__all__ = [
    "DEFAULT_MODEL",
    "SUPPORTED_MODELS",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "OPTIONAL_FIELDS",
]
