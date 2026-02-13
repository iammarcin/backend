"""Provider Registry - Import-Time Registration of All AI Providers
This module is the central registration point for all AI providers in the application.
It implements an import-time registration pattern where all providers are registered
automatically when this module is imported.
Architecture Pattern:
    1. Import provider classes from their implementation modules
    2. Call register_*_provider() functions to add them to registries
    3. Provider factories use these registries to resolve models dynamically
Registration Flow:
    1. main.py imports FastAPI routes
    2. Routes import services
    3. Services import from core.providers
    4. This __init__.py runs, registering all providers
    5. Factory functions can now resolve any registered provider
Why Import-Time Registration?:
    - Ensures all providers are available before any request
    - Fails fast if provider classes have syntax errors
    - Centralizes provider availability in one file
    - No need for lazy loading or dynamic imports
Usage Example:
    # In a service
    from core.providers.factory import get_text_provider
    def generate_text(settings):
        provider = get_text_provider(settings)  # Resolves from registry
        response = await provider.generate(prompt="Hello")
        return response
See Also:
    - core/providers/factory.py: Factory functions that use these registries
    - core/providers/registry/: Model registry for model name → provider mapping
    - config/providers/: Model configurations by provider
"""

import logging

from core.providers import factory  # re-export for convenience
from core.providers.audio.factory import (
    get_audio_provider,
    register_audio_provider,
)
from core.providers.audio.deepgram import DeepgramSpeechProvider
from core.providers.audio.gemini import GeminiSpeechProvider
from core.providers.audio.gemini_streaming import GeminiStreamingSpeechProvider
from core.providers.audio.openai import OpenAISpeechProvider
from core.providers.audio.openai_streaming import OpenAIStreamingSpeechProvider
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
from core.providers.realtime.factory import (
    get_realtime_provider,
    list_realtime_providers,
    register_realtime_provider,
)
from core.providers.semantic import (
    QdrantSemanticProvider,
    get_semantic_provider,
    register_semantic_provider,
)
from core.providers.image.flux import FluxImageProvider
from core.providers.image.gemini import GeminiImageProvider
from core.providers.image.openai import OpenAIImageProvider
from core.providers.image.stability import StabilityImageProvider
from core.providers.image.xai import XaiImageProvider
from core.providers.text.anthropic import AnthropicTextProvider
from core.providers.text.deepseek import DeepSeekTextProvider
from core.providers.text.gemini import GeminiTextProvider
from core.providers.text.groq import GroqTextProvider
from core.providers.text.openai import OpenAITextProvider
from core.providers.text.perplexity import PerplexityTextProvider
from core.providers.text.xai import XaiTextProvider
from core.providers.video.gemini import GeminiVideoProvider
from core.providers.video.klingai import KlingAIVideoProvider
from core.providers.video.openai import OpenAIVideoProvider
from core.providers.tts.elevenlabs import ElevenLabsTTSProvider
from core.providers.tts.openai import OpenAITTSProvider

register_text_provider("openai", OpenAITextProvider)
register_text_provider("gemini", GeminiTextProvider)
register_text_provider("anthropic", AnthropicTextProvider)
register_text_provider("groq", GroqTextProvider)
register_text_provider("perplexity", PerplexityTextProvider)
register_text_provider("deepseek", DeepSeekTextProvider)
register_text_provider("xai", XaiTextProvider)

register_image_provider("openai", OpenAIImageProvider)
register_image_provider("stability", StabilityImageProvider)
register_image_provider("flux", FluxImageProvider)
register_image_provider("gemini", GeminiImageProvider)
register_image_provider("xai", XaiImageProvider)

register_video_provider("gemini", GeminiVideoProvider)
register_video_provider("klingai", KlingAIVideoProvider)
register_video_provider("openai", OpenAIVideoProvider)

register_audio_provider("deepgram", DeepgramSpeechProvider)
register_audio_provider("openai", OpenAISpeechProvider)
register_audio_provider("gemini", GeminiSpeechProvider)
register_audio_provider("gemini_streaming", GeminiStreamingSpeechProvider)
register_audio_provider("openai_streaming", OpenAIStreamingSpeechProvider)

register_tts_provider("openai", OpenAITTSProvider)
register_tts_provider("elevenlabs", ElevenLabsTTSProvider)

if QdrantSemanticProvider is not None:
    register_semantic_provider("qdrant", QdrantSemanticProvider)

# Ensure realtime placeholder providers are registered on import.
from core.providers import realtime as _realtime_providers  # noqa: E402,F401

logger = logging.getLogger(__name__)
logger.info(
    "Provider registry initialised",
    extra={"realtime_providers": list_realtime_providers()},
)

__all__ = [
    "OpenAITextProvider",
    "OpenAIImageProvider",
    "GeminiTextProvider",
    "AnthropicTextProvider",
    "GroqTextProvider",
    "PerplexityTextProvider",
    "DeepSeekTextProvider",
    "XaiTextProvider",
    "StabilityImageProvider",
    "FluxImageProvider",
    "GeminiImageProvider",
    "XaiImageProvider",
    "GeminiVideoProvider",
    "KlingAIVideoProvider",
    "OpenAIVideoProvider",
    "OpenAISpeechProvider",
    "OpenAIStreamingSpeechProvider",
    "GeminiSpeechProvider",
    "DeepgramSpeechProvider",
    "GeminiStreamingSpeechProvider",
    "OpenAITTSProvider",
    "ElevenLabsTTSProvider",
    "get_realtime_provider",
    "list_realtime_providers",
    "register_realtime_provider",
    "get_semantic_provider",
    "register_semantic_provider",
    "QdrantSemanticProvider",
    "factory",
    "get_audio_provider",
    "register_audio_provider",
    "get_text_provider",
    "get_image_provider",
    "get_tts_provider",
    "get_video_provider",
]
