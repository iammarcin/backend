"""Groq model definitions for the registry."""

from __future__ import annotations

from core.providers.registry.model_config import ModelConfig

GROQ_MODELS: dict[str, ModelConfig] = {
    "gpt-oss-120b": ModelConfig(
        model_name="openai/gpt-oss-120b",
        provider_name="groq",
        support_image_input=False,
        file_attached_message_limit=0,
    ),
    "llama-3.3-70b": ModelConfig(
        model_name="llama-3.3-70b-versatile",
        provider_name="groq",
        support_image_input=False,
        file_attached_message_limit=0,
    ),
}
