"""Model registry definitions for AI providers."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from .model_config import ModelConfig

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry of all supported AI models with their configurations."""

    def __init__(self) -> None:
        self._models: Dict[str, ModelConfig] = {}
        self._aliases: Dict[str, str] = {}
        self._initialised = False

    def _register_model(self, key: str, config: ModelConfig) -> None:
        """Register a model configuration."""

        normalized = key.lower().strip()
        self._models[normalized] = config

    def _initialize_models(self) -> None:
        """Populate the registry with known model configurations."""

        if self._initialised:
            return

        from config.text.providers import MODEL_ALIASES, MODEL_CONFIGS

        for key, config in MODEL_CONFIGS.items():
            self._register_model(key, config)

        self._aliases.update(MODEL_ALIASES)
        self._initialised = True

    def ensure_initialised(self) -> None:
        """Ensure the registry is populated before use."""

        if not self._initialised:
            self._initialize_models()

    def get_model_config(self, model_name: str, enable_reasoning: bool = False) -> ModelConfig:
        """Resolve a model configuration by name, handling aliases and reasoning modes.

        Parameters
        ----------
        model_name:
            Name or alias of the model requested by the caller.
        enable_reasoning:
            When ``True`` prefer the reasoning counterpart if configured.

        Returns
        -------
        ModelConfig
            Configuration describing the resolved model.
        """

        self.ensure_initialised()

        lookup_key = model_name.lower().strip()
        if lookup_key in self._aliases:
            lookup_key = self._aliases[lookup_key].lower().strip()

        config = self._models.get(lookup_key)
        if not config:
            logger.warning("Model %s not found, falling back to gpt-5-nano", model_name)
            config = self._models.get("gpt-5-nano")
            if not config:
                raise ValueError(f"Model {model_name} not found and no fallback available")

        if enable_reasoning and config.reasoning_model_counterpart:
            reasoning_key = config.reasoning_model_counterpart.lower().strip()
            reasoning_config = self._models.get(reasoning_key)
            if not reasoning_config:
                alias_target = self._aliases.get(reasoning_key)
                if alias_target:
                    reasoning_config = self._models.get(alias_target.lower().strip())
            if reasoning_config:
                logger.info(
                    "Switching from %s to reasoning model %s",
                    config.model_name,
                    reasoning_config.model_name,
                )
                return reasoning_config

        return config

    def list_models(self, provider_name: Optional[str] = None) -> list[str]:
        """List all registered model keys, optionally filtered by provider.

        Parameters
        ----------
        provider_name:
            Optional provider identifier to limit the results.

        Returns
        -------
        list[str]
            Sorted list of model keys registered in the registry.
        """

        if provider_name:
            provider_name = provider_name.lower()
            return [
                key for key, cfg in self._models.items() if cfg.provider_name == provider_name
            ]
        return list(self._models.keys())

    def list_providers(self) -> list[str]:
        """List the unique provider names represented in the registry."""

        return sorted({cfg.provider_name for cfg in self._models.values()})


def get_model_config(model_name: str, enable_reasoning: bool = False) -> ModelConfig:
    """Return the model configuration for the supplied model name.

    Parameters
    ----------
    model_name:
        Public model name or alias.
    enable_reasoning:
        When ``True`` attempt to resolve the reasoning variant.

    Returns
    -------
    ModelConfig
        Configuration object describing the target model.
    """

    return get_registry().get_model_config(model_name, enable_reasoning=enable_reasoning)


def get_registry() -> ModelRegistry:
    """Return the global model registry instance."""

    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ModelRegistry()
    return _REGISTRY


_REGISTRY: ModelRegistry | None = None

__all__ = ["ModelRegistry", "ModelConfig", "get_model_config", "get_registry"]
