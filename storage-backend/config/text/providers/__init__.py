"""Text provider model configurations.

Previously located at ``config/providers`` – renamed for clarity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .aliases import MODEL_ALIASES
from .anthropic import ANTHROPIC_MODELS
from .deepseek import DEEPSEEK_MODELS
from .gemini import GEMINI_MODELS
from .groq import GROQ_MODELS
from .openai import OPENAI_MODELS
from .perplexity import PERPLEXITY_MODELS
from .xai import XAI_MODELS

if TYPE_CHECKING:
    from core.providers.registry.model_config import ModelConfig

MODEL_CONFIGS: dict[str, "ModelConfig"] = {
    **OPENAI_MODELS,
    **ANTHROPIC_MODELS,
    **GEMINI_MODELS,
    **XAI_MODELS,
    **GROQ_MODELS,
    **PERPLEXITY_MODELS,
    **DEEPSEEK_MODELS,
}

__all__ = ["MODEL_CONFIGS", "MODEL_ALIASES"]
