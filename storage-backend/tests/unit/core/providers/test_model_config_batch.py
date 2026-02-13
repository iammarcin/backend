from core.providers.registry import get_model_config


def test_openai_models_batch_support():
    config = get_model_config("gpt-4o")
    assert config.supports_batch_api is True
    assert config.batch_max_requests == 50000
    assert config.batch_max_file_size_mb == 200


def test_anthropic_models_batch_support():
    config = get_model_config("claude-sonnet")
    assert config.supports_batch_api is True
    assert config.batch_max_requests == 100000
    assert config.batch_max_file_size_mb == 256


def test_gemini_models_batch_support():
    config = get_model_config("gemini-flash")
    assert config.supports_batch_api is True
    assert config.batch_max_requests == 50000
    assert config.batch_max_file_size_mb == 2048


def test_non_batch_provider_has_defaults():
    config = get_model_config("llama-3.3-70b")
    assert config.supports_batch_api is False
    assert config.batch_max_requests == 0
