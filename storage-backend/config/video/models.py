"""Video model mappings."""

from __future__ import annotations

from typing import Dict, List

VIDEO_MODEL_MAPPING: Dict[str, str] = {
    "veo": "veo-3.1-fast",
    "sora": "sora-2",
}

VIDEO_AVAILABLE_MODELS: List[str] = ["veo", "sora"]
VIDEO_DEFAULT_MODEL = "veo"

VIDEO_MIN_DURATION = 3
VIDEO_MAX_DURATION = 8
VIDEO_DEFAULT_DURATION = 5
VIDEO_DEFAULT_ASPECT_RATIO = "16:9"
VIDEO_POLL_TIMEOUT_SECONDS = 240

VIDEO_MODEL_DESCRIPTIONS = (
    "AI model to use for generation:\\n"
    "- veo: Google Veo 3.1, fast and reliable\\n"
    "- sora: OpenAI Sora 2, highly creative and realistic"
)

__all__ = [
    "VIDEO_MODEL_MAPPING",
    "VIDEO_AVAILABLE_MODELS",
    "VIDEO_DEFAULT_MODEL",
    "VIDEO_MIN_DURATION",
    "VIDEO_MAX_DURATION",
    "VIDEO_DEFAULT_DURATION",
    "VIDEO_DEFAULT_ASPECT_RATIO",
    "VIDEO_POLL_TIMEOUT_SECONDS",
    "VIDEO_MODEL_DESCRIPTIONS",
]
