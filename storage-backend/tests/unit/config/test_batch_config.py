from config.batch import (
    BATCH_INITIAL_POLLING_DELAY_SECONDS,
    BATCH_MAX_FILE_SIZE_MB_ANTHROPIC,
    BATCH_MAX_FILE_SIZE_MB_GEMINI,
    BATCH_MAX_FILE_SIZE_MB_OPENAI,
    BATCH_MAX_POLLING_ATTEMPTS,
    BATCH_MAX_REQUESTS_ANTHROPIC,
    BATCH_MAX_REQUESTS_GEMINI,
    BATCH_MAX_REQUESTS_OPENAI,
    BATCH_POLLING_INTERVAL_SECONDS,
    BATCH_TIMEOUT_SECONDS,
)
from config.batch.utils import (
    get_batch_max_file_size_mb,
    get_batch_max_requests,
    validate_batch_size,
)
from core.providers.registry import get_model_config


def test_batch_defaults():
    assert BATCH_POLLING_INTERVAL_SECONDS == 10
    assert BATCH_INITIAL_POLLING_DELAY_SECONDS == 5
    assert BATCH_TIMEOUT_SECONDS == 86400
    assert BATCH_MAX_POLLING_ATTEMPTS == 8640
    assert BATCH_MAX_REQUESTS_OPENAI == 50000
    assert BATCH_MAX_REQUESTS_ANTHROPIC == 100000
    assert BATCH_MAX_REQUESTS_GEMINI == 50000
    assert BATCH_MAX_FILE_SIZE_MB_OPENAI == 200
    assert BATCH_MAX_FILE_SIZE_MB_ANTHROPIC == 256
    assert BATCH_MAX_FILE_SIZE_MB_GEMINI == 2048


def test_get_batch_max_requests():
    assert get_batch_max_requests("openai") == 50000
    assert get_batch_max_requests("anthropic") == 100000
    assert get_batch_max_requests("google") == 50000
    assert get_batch_max_requests("gemini") == 50000
    assert get_batch_max_requests("unknown") == 0


def test_get_batch_max_file_size():
    assert get_batch_max_file_size_mb("openai") == 200
    assert get_batch_max_file_size_mb("anthropic") == 256
    assert get_batch_max_file_size_mb("google") == 2048
    assert get_batch_max_file_size_mb("gemini") == 2048
    assert get_batch_max_file_size_mb("unknown") == 0


def test_validate_batch_size():
    assert validate_batch_size("openai", 1000) is True
    assert validate_batch_size("openai", 50000) is True
    assert validate_batch_size("openai", 50001) is False
    assert validate_batch_size("anthropic", 100000) is True
    assert validate_batch_size("anthropic", 100001) is False
    assert validate_batch_size("unknown", 999999) is True


def test_model_batch_capabilities():
    gpt4o_config = get_model_config("gpt-4o")
    assert gpt4o_config.supports_batch_api is True
    assert gpt4o_config.batch_max_requests == 50000

    claude_config = get_model_config("claude-sonnet")
    assert claude_config.supports_batch_api is True
    assert claude_config.batch_max_requests == 100000

    gemini_config = get_model_config("gemini-2.5-flash")
    assert gemini_config.supports_batch_api is True
    assert gemini_config.batch_max_requests == 50000
