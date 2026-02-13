"""Alias mapping for image generation models."""

from __future__ import annotations

IMAGE_MODEL_ALIASES: dict[str, str] = {
    # OpenAI - GPT Image 1.5 as new default (December 2025)
    "openai": "gpt-image-1.5",
    "openai-1.5": "gpt-image-1.5",
    "openai-1": "gpt-image-1",
    "openai mini": "gpt-image-1-mini",
    "openai-mini": "gpt-image-1-mini",
    # Gemini - Nano Banana aliases (November 2025)
    "gemini": "gemini-2.5-flash-image",
    "gemini-pro": "gemini-3-pro-image-preview",
    "gemini_flash": "gemini-2.5-flash-image",
    "gemini-flash": "gemini-2.5-flash-image",
    "gemini-imagen": "imagen-4.0-generate-001",
    "nano-banana": "gemini-2.5-flash-image",
    "nano-banana-pro": "gemini-3-pro-image-preview",
    # Flux - FLUX.2 models with flux-2-pro as default (November 2025)
    "flux": "flux-2-pro",
    "flux-pro": "flux-2-pro",
    "flux-max": "flux-2-max",
    "flux-flex": "flux-2-flex",
    "flux-dev": "flux-dev",
    "flux-1": "flux-dev",
    "flux-kontext": "flux-kontext-pro",
}

# Backwards-compatible name referenced by documentation
IMAGE_ALIASES = IMAGE_MODEL_ALIASES


def resolve_image_model_alias(model: str | None) -> str:
    """Return the canonical model name for a requested image model alias."""

    if not model:
        return "gpt-image-1.5"

    normalized = model.strip().lower()
    return IMAGE_MODEL_ALIASES.get(normalized, normalized)


__all__ = ["IMAGE_MODEL_ALIASES", "IMAGE_ALIASES", "resolve_image_model_alias"]
