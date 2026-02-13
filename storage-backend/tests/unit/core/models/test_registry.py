from core.providers.registry import ModelRegistry, get_model_config


def test_get_model_config_case_insensitive() -> None:
    config1 = get_model_config("gpt-4o")
    config2 = get_model_config("GPT-4O")
    config3 = get_model_config("Gpt-4o")

    assert config1.model_name == config2.model_name == config3.model_name


def test_get_model_config_with_alias() -> None:
    config = get_model_config("claude")

    assert config.model_name == "claude-sonnet-4-5"
    assert config.provider_name == "anthropic"


def test_get_model_config_enable_reasoning() -> None:
    base_config = get_model_config("gpt-4o-mini", enable_reasoning=False)
    reasoning_config = get_model_config("gpt-4o-mini", enable_reasoning=True)

    assert base_config.model_name == "gpt-4o-mini"
    assert reasoning_config.model_name == "gpt-5.1"
    assert reasoning_config.is_reasoning_model is True


def test_get_model_config_unknown_model_fallback() -> None:
    config = get_model_config("unknown-model-xyz")

    assert config.model_name == "gpt-5-nano"
    assert config.provider_name == "openai"


def test_model_config_reasoning_capabilities() -> None:
    config = get_model_config("o3")

    assert config.is_reasoning_model is True
    assert config.supports_reasoning_effort is True
    assert config.reasoning_effort_values == ["low", "medium", "high"]
    assert config.supports_temperature is False


def test_model_config_claude_reasoning_effort() -> None:
    config = get_model_config("claude-opus")

    assert config.supports_reasoning_effort is True
    assert config.reasoning_effort_values == [2048, 8000, 16000]


def test_list_models_by_provider() -> None:
    registry = ModelRegistry()
    registry.ensure_initialised()
    openai_models = registry.list_models(provider_name="openai")

    assert "gpt-4o" in openai_models
    assert "o3" in openai_models
    assert "claude-4-sonnet" not in openai_models


def test_list_all_providers() -> None:
    registry = ModelRegistry()
    registry.ensure_initialised()
    providers = registry.list_providers()

    assert "openai" in providers
    assert "anthropic" in providers
    assert "gemini" in providers
    assert "perplexity" in providers
