"""DeepSeek model definitions for the registry."""

from __future__ import annotations

from core.providers.registry.model_config import ModelConfig

DEEPSEEK_MODELS: dict[str, ModelConfig] = {
    "deepseek-chat": ModelConfig(
        model_name="deepseek-chat",
        provider_name="deepseek",
        support_image_input=True,
        reasoning_model_counterpart="deepseek-reason",
    ),
    "deepseek-reason": ModelConfig(
        model_name="deepseek-reasoner",
        provider_name="deepseek",
        is_reasoning_model=True,
        support_image_input=False,
    ),
}
