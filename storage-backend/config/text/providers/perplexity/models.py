"""Perplexity Sonar model definitions for the registry."""

from __future__ import annotations

from core.providers.registry.model_config import ModelConfig

PERPLEXITY_MODELS: dict[str, ModelConfig] = {
    "sonar-deep-research": ModelConfig(
        model_name="sonar-deep-research",
        provider_name="perplexity",
        support_image_input=True,
        is_reasoning_model=True,
        supports_citations=True,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
    ),
    "sonar-reason-pro": ModelConfig(
        model_name="sonar-reasoning-pro",
        provider_name="perplexity",
        support_image_input=False,
        is_reasoning_model=True,
        supports_citations=True,
    ),
    "sonar-reason": ModelConfig(
        model_name="sonar-reasoning",
        provider_name="perplexity",
        support_image_input=True,
        is_reasoning_model=True,
        supports_citations=True,
    ),
    "sonar-pro": ModelConfig(
        model_name="sonar-pro",
        provider_name="perplexity",
        support_image_input=True,
        reasoning_model_counterpart="sonar-reason-pro",
        supports_citations=True,
    ),
    "sonar": ModelConfig(
        model_name="sonar",
        provider_name="perplexity",
        support_image_input=True,
        reasoning_model_counterpart="sonar-reason",
        supports_citations=True,
    ),
}
