"""xAI Grok model definitions for the registry."""

from __future__ import annotations

from core.providers.registry.model_config import ModelConfig

XAI_MODELS: dict[str, ModelConfig] = {
    "grok-4": ModelConfig(
        model_name="grok-4-latest",
        provider_name="xai",
        support_image_input=True,
        supports_function_calling=True,
        max_tokens_default=8192,
    ),
    "grok-4.1-mini": ModelConfig(
        model_name="grok-4-1-fast-reasoning",
        provider_name="xai",
        support_image_input=True,
        supports_function_calling=True,
        max_tokens_default=4096,
    ),
    "grok-4-mini": ModelConfig(
        model_name="grok-4-fast-reasoning-latest",
        provider_name="xai",
        support_image_input=True,
        supports_function_calling=True,
        max_tokens_default=4096,
    ),
}
