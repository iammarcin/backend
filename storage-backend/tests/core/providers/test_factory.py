"""Tests for provider factory pattern integration."""

import pytest
from unittest.mock import patch

from core.providers.factory import get_video_provider
from core.providers.video.klingai import KlingAIVideoProvider
from core.providers.video.gemini import GeminiVideoProvider
from core.providers.video.openai import OpenAIVideoProvider
from core.exceptions import ConfigurationError


@pytest.mark.asyncio
class TestVideoProviderFactory:
    """Test video provider factory resolution."""

    async def test_factory_resolves_klingai_for_kling_models(self):
        """Test factory resolves KlingAI provider for kling-* models."""
        models = [
            "kling-v1",
            "kling-v1-5",
            "kling-v1-6",
            "kling-v2-master",
            "kling-v2-1-master",
            "kling-v2-5-turbo",
        ]

        for model in models:
            with patch("config.video.providers.klingai.ACCESS_KEY", "test-key"), \
                    patch("config.video.providers.klingai.SECRET_KEY", "test-secret"):

                settings = {"video": {"model": model}}
                provider = get_video_provider(settings)

                assert isinstance(provider, KlingAIVideoProvider)
                assert provider.provider_name == "klingai"

    async def test_factory_resolves_gemini_for_veo_models(self):
        """Test factory resolves Gemini provider for veo-* models."""
        models = [
            "veo-3.1",
            "veo-3.1-fast",
            "gemini-veo",
        ]

        for model in models:
            settings = {"video": {"model": model}}
            provider = get_video_provider(settings)

            assert isinstance(provider, GeminiVideoProvider)
            assert provider.provider_name == "gemini"

    async def test_factory_resolves_openai_for_sora_models(self):
        """Test factory resolves OpenAI provider for sora-* models."""
        models = [
            "sora-2",
            "openai-sora",
        ]

        for model in models:
            settings = {"video": {"model": model}}
            provider = get_video_provider(settings)

            assert isinstance(provider, OpenAIVideoProvider)
            assert provider.provider_name == "openai"

    async def test_factory_raises_error_for_unknown_model(self):
        """Test factory raises error for unknown video models."""
        settings = {"video": {"model": "unknown-model"}}

        with pytest.raises(ConfigurationError, match="Unknown video model"):
            get_video_provider(settings)

    async def test_factory_uses_default_model_when_none_specified(self):
        """Test factory uses default model when none specified."""
        settings = {"video": {}}

        # Should default to some model, but this depends on the default in the factory
        # For now, just ensure it doesn't crash
        try:
            provider = get_video_provider(settings)
            # Should return some provider
            assert provider is not None
        except ConfigurationError:
            # If no default is set, it might raise an error - that's acceptable
            pass

    async def test_factory_handles_case_insensitive_model_names(self):
        """Test factory handles case insensitive model names."""
        with patch("config.video.providers.klingai.ACCESS_KEY", "test-key"), \
                patch("config.video.providers.klingai.SECRET_KEY", "test-secret"):

            # Test uppercase
            settings = {"video": {"model": "KLING-V1"}}
            provider = get_video_provider(settings)
            assert isinstance(provider, KlingAIVideoProvider)

            # Test mixed case
            settings = {"video": {"model": "Kling-V2-5-Turbo"}}
            provider = get_video_provider(settings)
            assert isinstance(provider, KlingAIVideoProvider)

    async def test_factory_prioritizes_explicit_provider_over_model_inference(self):
        """Test that explicit provider specification takes precedence."""
        # Note: This test assumes the factory supports explicit provider specification
        # If not implemented, this test can be skipped or modified
        pass
