"""Tests for provider factory registration and lookup."""

import pytest

from core.exceptions import ConfigurationError
from core.providers.capabilities import ProviderCapabilities
from core.pydantic_schemas import ProviderResponse
from core.providers.base import (
    BaseImageProvider,
    BaseTextProvider,
)
from core.providers.tts_base import (
    BaseTTSProvider,
    TTSRequest,
    TTSResult,
)
from core.providers.registries import (
    _image_providers,
    _text_providers,
    _tts_providers,
)
from core.providers.factory import (
    get_image_provider,
    get_text_provider,
    get_tts_provider,
    register_image_provider,
    register_text_provider,
    register_tts_provider,
)


class FakeOpenAITextProvider(BaseTextProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        return ProviderResponse(text="fake", model="fake", provider="openai")


class FakeAnthropicTextProvider(BaseTextProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, prompt: str, **kwargs) -> ProviderResponse:
        return ProviderResponse(text="anthropic", model="fake", provider="anthropic")


class FakeOpenAIImageProvider(BaseImageProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, prompt: str, **kwargs) -> bytes:
        return b"openai-image"


class FakeStabilityImageProvider(BaseImageProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, prompt: str, **kwargs) -> bytes:
        return b"stability-image"


class FakeOpenAITTSProvider(BaseTTSProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()
        self.last_settings: dict[str, object] = {}

    def configure(self, settings):
        self.last_settings = dict(settings)

    async def generate(self, request: TTSRequest) -> TTSResult:
        return TTSResult(
            audio_bytes=b"openai-tts",
            provider="openai",
            model=request.model or "gpt-4o-mini-tts",
            format=request.format or "mp3",
            voice=request.voice,
        )


class FakeElevenLabsTTSProvider(BaseTTSProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities()

    async def generate(self, request: TTSRequest) -> TTSResult:
        return TTSResult(
            audio_bytes=b"eleven-tts",
            provider="elevenlabs",
            model=request.model or "eleven",
            format=request.format or "mp3",
            voice=request.voice,
        )


@pytest.fixture(autouse=True)
def setup_providers():
    original_text = _text_providers.copy()
    original_image = _image_providers.copy()
    original_tts = _tts_providers.copy()

    _text_providers.clear()
    _image_providers.clear()
    _tts_providers.clear()

    register_text_provider("openai", FakeOpenAITextProvider)
    register_text_provider("anthropic", FakeAnthropicTextProvider)
    register_image_provider("openai", FakeOpenAIImageProvider)
    register_image_provider("stability", FakeStabilityImageProvider)
    register_tts_provider("openai", FakeOpenAITTSProvider)
    register_tts_provider("elevenlabs", FakeElevenLabsTTSProvider)

    try:
        yield
    finally:
        _text_providers.clear()
        _text_providers.update(original_text)
        _image_providers.clear()
        _image_providers.update(original_image)
        _tts_providers.clear()
        _tts_providers.update(original_tts)


def test_get_text_provider_openai() -> None:
    settings = {"text": {"model": "gpt-4o-mini"}}
    provider = get_text_provider(settings)

    assert isinstance(provider, FakeOpenAITextProvider)
    config = provider.get_model_config()
    assert config is not None
    assert config.model_name == "gpt-4o-mini"
    assert config.provider_name == "openai"


def test_get_text_provider_unknown_model() -> None:
    settings = {"text": {"model": "unknown-model-xyz"}}
    provider = get_text_provider(settings)

    assert isinstance(provider, FakeOpenAITextProvider)
    config = provider.get_model_config()
    assert config is not None
    assert config.model_name == "gpt-5-nano"
    assert config.provider_name == "openai"


def test_get_text_provider_not_registered() -> None:
    settings = {"text": {"model": "sonar-pro"}}

    with pytest.raises(ConfigurationError) as exc:
        get_text_provider(settings)

    assert "not registered" in str(exc.value)


def test_get_text_provider_alias_and_reasoning() -> None:
    settings = {"text": {"model": "CLAUDE", "enable_reasoning": True}}
    provider = get_text_provider(settings)

    assert isinstance(provider, FakeAnthropicTextProvider)
    config = provider.get_model_config()
    assert config is not None
    assert config.model_name == "claude-opus-4-6"
    assert config.is_reasoning_model is True
    assert config.provider_name == "anthropic"


def test_get_image_provider_openai() -> None:
    settings = {"image": {"model": "dall-e"}}
    provider = get_image_provider(settings)

    assert isinstance(provider, FakeOpenAIImageProvider)


def test_get_image_provider_openai_alias() -> None:
    settings = {"image": {"model": "gpt-image-1"}}
    provider = get_image_provider(settings)

    assert isinstance(provider, FakeOpenAIImageProvider)


def test_get_image_provider_resolves_friendly_alias() -> None:
    settings = {"image": {"model": "openai mini"}}
    provider = get_image_provider(settings)

    assert isinstance(provider, FakeOpenAIImageProvider)


def test_get_image_provider_unknown_model() -> None:
    settings = {"image": {"model": "unknown"}}

    with pytest.raises(ConfigurationError):
        get_image_provider(settings)


def test_get_image_provider_not_registered() -> None:
    settings = {"image": {"model": "flux-pro"}}

    with pytest.raises(ConfigurationError) as exc:
        get_image_provider(settings)

    assert "not registered" in str(exc.value)


def test_get_image_provider_stability_core() -> None:
    settings = {"image": {"model": "core"}}
    provider = get_image_provider(settings)

    assert isinstance(provider, FakeStabilityImageProvider)


def test_get_tts_provider_openai_default() -> None:
    settings = {"tts": {"model": "gpt-4o-mini-tts"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeOpenAITTSProvider)
    assert provider.last_settings["model"] == "gpt-4o-mini-tts"


def test_get_tts_provider_elevenlabs_inference() -> None:
    settings = {"tts": {"model": "eleven_monolingual_v1"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeElevenLabsTTSProvider)


def test_get_tts_provider_unknown_provider() -> None:
    with pytest.raises(ConfigurationError):
        get_tts_provider({"tts": {"provider": "unknown"}})


def test_get_tts_provider_elevenlabs_voice_takes_precedence_over_model() -> None:
    """Voice-based provider selection should take precedence over model-based.

    This test verifies the fix for the regression where voice selection was ignored.
    When a user selects an ElevenLabs voice (like 'naval') but has an OpenAI model
    (like 'gpt-4o-mini-tts'), the system should use ElevenLabs provider.
    """
    settings = {"tts": {"model": "gpt-4o-mini-tts", "voice": "naval"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeElevenLabsTTSProvider)


def test_get_tts_provider_elevenlabs_voice_case_insensitive() -> None:
    """Voice name lookup should be case-insensitive."""
    settings = {"tts": {"model": "gpt-4o-mini-tts", "voice": "Naval"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeElevenLabsTTSProvider)


def test_get_tts_provider_elevenlabs_voice_id() -> None:
    """Should also work with ElevenLabs voice IDs."""
    # Naval's voice ID
    settings = {"tts": {"model": "gpt-4o-mini-tts", "voice": "30zc5PfKKHzfXQfjXbLU"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeElevenLabsTTSProvider)


def test_get_tts_provider_unknown_voice_uses_model_inference() -> None:
    """Unknown voice should fall back to model-based inference."""
    # 'alloy' is an OpenAI voice, not in ElevenLabs list
    settings = {"tts": {"model": "gpt-4o-mini-tts", "voice": "alloy"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeOpenAITTSProvider)


def test_get_tts_provider_explicit_provider_takes_precedence() -> None:
    """Explicit provider should take precedence over both voice and model."""
    settings = {"tts": {"provider": "openai", "model": "eleven_turbo", "voice": "naval"}}
    provider = get_tts_provider(settings)

    assert isinstance(provider, FakeOpenAITTSProvider)
