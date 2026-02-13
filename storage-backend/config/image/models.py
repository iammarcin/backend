"""Image model mappings and descriptions."""

from __future__ import annotations

from typing import Dict, List

# Maps user-friendly agent tool names to provider-specific model IDs
IMAGE_MODEL_MAPPING: Dict[str, str] = {
    # Flux
    "flux": "flux-2-pro",
    "flux-pro": "flux-2-pro",
    "flux-max": "flux-2-max",
    "flux-flex": "flux-2-flex",
    "flux-dev": "flux-dev",
    # OpenAI
    "openai": "gpt-image-1.5",
    "openai-mini": "gpt-image-1-mini",
    # Gemini
    "gemini": "gemini-2.5-flash-image",
    "gemini-pro": "gemini-3-pro-image-preview",
    "gemini-flash": "gemini-2.5-flash-image",
}

# Available models exposed to agentic tools
IMAGE_AVAILABLE_MODELS: List[str] = ["flux", "flux-max", "openai", "gemini", "gemini-pro"]

# Default selection when no model is provided
IMAGE_DEFAULT_MODEL = "flux"

# Description shown in tool schemas
IMAGE_MODEL_DESCRIPTIONS = (
    "AI model to use for image generation:\\n"
    "- flux: Flux 2 Pro, photorealistic up to 4MP\\n"
    "- flux-max: Flux 2 Max, highest quality with real-time grounding\\n"
    "- openai: GPT-Image-1.5, fast and high-quality (4x faster)\\n"
    "- gemini: Gemini Flash Image (Nano Banana), fast generator\\n"
    "- gemini-pro: Gemini 3 Pro Image (Nano Banana Pro), up to 4K resolution"
)

__all__ = [
    "IMAGE_MODEL_MAPPING",
    "IMAGE_AVAILABLE_MODELS",
    "IMAGE_DEFAULT_MODEL",
    "IMAGE_MODEL_DESCRIPTIONS",
]
