"""Chat model definitions for OpenAI provider."""

from __future__ import annotations

from config.batch.defaults import (
    BATCH_MAX_FILE_SIZE_MB_OPENAI,
    BATCH_MAX_REQUESTS_OPENAI,
)
from core.providers.registry.model_config import ModelConfig


BATCH_CONFIG = {
    "supports_batch_api": True,
    "batch_max_requests": BATCH_MAX_REQUESTS_OPENAI,
    "batch_max_file_size_mb": BATCH_MAX_FILE_SIZE_MB_OPENAI,
}


CHAT_MODELS: dict[str, ModelConfig] = {
    "o3": ModelConfig(
        model_name="o3",
        provider_name="openai",
        is_reasoning_model=True,
        support_image_input=True,
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "o3-pro": ModelConfig(
        model_name="o3-pro",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=32768,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "o4-mini": ModelConfig(
        model_name="o4-mini",
        provider_name="openai",
        is_reasoning_model=True,
        support_image_input=True,
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],  # Fixed typo: amedium -> medium
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "o3-mini": ModelConfig(
        model_name="o3-mini",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=False,
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5-pro": ModelConfig(
        model_name="gpt-5.2-pro",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_temperature=False,
        supports_reasoning_effort=True,
        reasoning_effort_values=["high", "high", "high"],  # high only supported
        category="chat",
        supports_code_interpreter=False,
        max_tokens_default=32768,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5": ModelConfig(
        model_name="gpt-5",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_reasoning_effort=True,
        supports_temperature=False,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        is_deprecated=True,
        replacement_model="gpt-5.1",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5.1": ModelConfig(
        model_name="gpt-5.1",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_reasoning_effort=True,
        supports_temperature=False,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5.2": ModelConfig(
        model_name="gpt-5.2-chat-latest",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        supports_reasoning_effort=True,
        supports_temperature=False,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5-mini": ModelConfig(
        model_name="gpt-5-mini",
        provider_name="openai",
        api_type="responses_api",
        is_reasoning_model=True,
        support_image_input=True,
        reasoning_model_counterpart="gpt-5.1",
        supports_reasoning_effort=True,
        supports_temperature=False,
        reasoning_effort_values=["low", "medium", "high"],
        category="chat",
        max_tokens_default=16384,  # Higher limit for reasoning model
        **BATCH_CONFIG,
    ),
    "gpt-5-nano": ModelConfig(
        model_name="gpt-5-nano",
        provider_name="openai",
        api_type="responses_api",
        support_image_input=True,
        supports_temperature=False,
        reasoning_model_counterpart="gpt-5.1",
        category="chat",
        **BATCH_CONFIG,
    ),
    "gpt-4o-mini": ModelConfig(
        model_name="gpt-4o-mini",
        provider_name="openai",
        support_image_input=True,
        reasoning_model_counterpart="gpt-5.1",
        category="chat",
        **BATCH_CONFIG,
    ),
    "gpt-4o": ModelConfig(
        model_name="chatgpt-4o-latest",
        provider_name="openai",
        support_image_input=True,
        reasoning_model_counterpart="gpt-5.1",
        category="chat",
        **BATCH_CONFIG,
    ),
    "gpt-4.1": ModelConfig(
        model_name="gpt-4.1-2025-04-14",
        provider_name="openai",
        support_image_input=True,
        reasoning_model_counterpart="o3",
        category="chat",
        **BATCH_CONFIG,
    ),
    "gpt-4.1-mini": ModelConfig(
        model_name="gpt-4.1-mini-2025-04-14",
        provider_name="openai",
        support_image_input=True,
        reasoning_model_counterpart="o4-mini",
        category="chat",
        **BATCH_CONFIG,
    ),
    "gpt-4.1-nano": ModelConfig(
        model_name="gpt-4.1-nano-2025-04-14",
        provider_name="openai",
        support_image_input=True,
        reasoning_model_counterpart="o4-mini",
        category="chat",
        **BATCH_CONFIG,
    ),
}


__all__ = ["CHAT_MODELS"]
