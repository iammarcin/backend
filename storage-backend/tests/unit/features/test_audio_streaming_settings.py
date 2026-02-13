"""Unit tests for streaming provider configuration helpers."""

from config.audio import StreamingProviderSettings


def test_defaults_target_deepgram() -> None:
    """Default configuration should point at Deepgram."""

    settings = StreamingProviderSettings()

    payload = settings.to_provider_dict()

    assert payload["provider"] == "deepgram"
    assert payload["model"] == "nova-3"


def test_gemini_model_switches_provider() -> None:
    """Supplying a Gemini model should switch provider and normalise alias."""

    settings = StreamingProviderSettings()
    settings.update_from_payload({"model": "gemini-flash"})

    payload = settings.to_provider_dict()

    assert payload["provider"] == "gemini"
    assert payload["model"] == "gemini-2.5-flash"
    assert payload["buffer_duration_seconds"] > 0


def test_optional_prompt_is_preserved() -> None:
    """Gemini specific fields should flow through to the provider payload."""

    settings = StreamingProviderSettings()
    settings.update_from_payload(
        {
            "model": "gemini-flash",
            "optional_prompt": "Custom transcription prompt",
        }
    )

    payload = settings.to_provider_dict()

    assert payload["optional_prompt"] == "Custom transcription prompt"


def test_openai_model_switches_provider() -> None:
    """Supplying an OpenAI transcription model should switch provider."""

    settings = StreamingProviderSettings()
    settings.update_from_payload({"model": "gpt-4o-transcribe"})

    payload = settings.to_provider_dict()

    assert payload["provider"] == "openai"
    assert payload["model"] == "gpt-4o-transcribe"
