"""Audio provider implementations and factory registration."""

from .base import BaseAudioProvider, SpeechProviderRequest, SpeechTranscriptionResult
from .deepgram import DeepgramSpeechProvider
from .factory import get_audio_provider, register_audio_provider
from .gemini import GeminiSpeechProvider
from .gemini_streaming import GeminiStreamingSpeechProvider
from .openai import OpenAISpeechProvider
from .openai_streaming import OpenAIStreamingSpeechProvider

__all__ = [
    "BaseAudioProvider",
    "SpeechProviderRequest",
    "SpeechTranscriptionResult",
    "get_audio_provider",
    "register_audio_provider",
    "DeepgramSpeechProvider",
    "OpenAISpeechProvider",
    "OpenAIStreamingSpeechProvider",
    "GeminiSpeechProvider",
    "GeminiStreamingSpeechProvider",
]

