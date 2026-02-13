"""Provider Factory - Dynamic Resolution of AI Providers
This module implements the factory pattern for resolving AI providers at runtime.
It maintains registries of available providers and provides factory functions
that select the appropriate provider based on model names and settings.
Architecture Overview:
    1. Registries store provider name → provider class mappings
    2. Factory functions (get_*_provider) resolve providers from settings
    3. For text providers: Model registry maps model name → provider + config
    4. For image/video/TTS: Pattern matching on model names
Provider Resolution Strategies:
    TEXT PROVIDERS:
        - Uses model registry (core/providers/registry/)
        - Model name → ModelConfig with provider_name, capabilities, etc.
        - Supports reasoning models 
        - Example: "gpt-4o" → OpenAI provider
    IMAGE PROVIDERS:
        - Pattern matching on model name prefixes
        - "dall-e" / "openai" → OpenAI
        - "flux" → Flux
        - "sd" / "stability" → Stability AI
        - "gemini" / "imagen" → Gemini
        - "grok" → xAI
    VIDEO PROVIDERS:
        - Pattern matching on model name
        - "veo" / "gemini" → Gemini
        - "sora" / "openai" → OpenAI
    TTS PROVIDERS:
        - Explicit provider name if specified, OR:
        - Voice-based selection (known ElevenLabs voice → ElevenLabs)
        - Model-based inference ("eleven" / "xi-" → ElevenLabs)
        - Default → OpenAI
        NOTE: Voice takes precedence over model
Registration Pattern:
    # In core/providers/__init__.py
    register_text_provider("openai", OpenAITextProvider)
    # In service code
    provider = get_text_provider({"text": {"model": "gpt-4o"}})
    response = await provider.generate("Hello")
Design Benefits:
    - Loose coupling: Services don't depend on specific provider implementations
    - Easy to add new providers: Register and implement interface
    - Model-agnostic: Switch providers by changing model name
    - Type-safe: All providers implement base interfaces
See Also:
    - core/providers/__init__.py: Provider registration
    - core/providers/base.py: Provider interfaces
    - core/providers/registry/: Model registry for text providers
"""

from __future__ import annotations

import logging

from core.providers.registries import (
    register_image_provider,
    register_text_provider,
    register_tts_provider,
    register_video_provider,
)
from core.providers.resolvers import (
    get_image_provider,
    get_text_provider,
    get_tts_provider,
    get_video_provider,
)

logger = logging.getLogger(__name__)
