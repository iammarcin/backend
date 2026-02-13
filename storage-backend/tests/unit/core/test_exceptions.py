"""Unit tests for custom exception hierarchy."""

from core.exceptions import (
    ConfigurationError,
    DatabaseError,
    ProviderError,
    RateLimitError,
    ServiceError,
    StreamingError,
    ValidationError,
)


def test_validation_error():
    """ValidationError should capture message and field."""

    error = ValidationError("Invalid email", field="email")
    assert error.message == "Invalid email"
    assert error.field == "email"
    assert isinstance(error, ServiceError)


def test_provider_error():
    """ProviderError should retain provider and original exception."""

    original = ValueError("API failed")
    error = ProviderError("OpenAI error", provider="openai", original_error=original)

    assert error.message == "OpenAI error"
    assert error.provider == "openai"
    assert error.original_error is original
    assert isinstance(error, ServiceError)


def test_database_error():
    """DatabaseError should include the failing operation."""

    error = DatabaseError("Save failed", operation="save")
    assert error.operation == "save"


def test_streaming_error():
    """StreamingError should capture the stage information."""

    error = StreamingError("Fan out failed", stage="fan-out")
    assert error.stage == "fan-out"


def test_configuration_error_required_key():
    """ConfigurationError should store the missing key."""

    error = ConfigurationError("Missing key", key="API_KEY")
    assert error.key == "API_KEY"


def test_rate_limit_error():
    """RateLimitError should include retry interval."""

    error = RateLimitError("Too many requests", retry_after=30)
    assert error.retry_after == 30
    assert isinstance(error, ProviderError)
