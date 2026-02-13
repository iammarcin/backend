"""Google Gemini Veo configuration."""

from __future__ import annotations

DEFAULT_MODEL = "veo-3.1-fast-generate-preview"
MODEL_ALIASES = {
    "veo-3.1-fast": DEFAULT_MODEL,
    "veo-3.1-fast-generate-preview": DEFAULT_MODEL,
    "veo-3.1": "veo-3.1-generate-preview",
}

AVAILABLE_ASPECT_RATIOS = {"16:9", "9:16"}
AVAILABLE_PERSON_GENERATION = {"dont_allow", "allow_adult"}
AVAILABLE_RESOLUTIONS = {"720p", "1080p"}

REFERENCE_TYPES = {
    "asset": "asset",
    "style": "style",
}

POLL_INTERVAL_SECONDS = 20
TIMEOUT_SECONDS = 600

__all__ = [
    "DEFAULT_MODEL",
    "MODEL_ALIASES",
    "AVAILABLE_ASPECT_RATIOS",
    "AVAILABLE_PERSON_GENERATION",
    "AVAILABLE_RESOLUTIONS",
    "REFERENCE_TYPES",
    "POLL_INTERVAL_SECONDS",
    "TIMEOUT_SECONDS",
]
