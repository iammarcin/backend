"""Custom Exception Hierarchy for BetterAI Backend
This module defines a typed exception hierarchy that enables precise error
handling and structured error responses across the application.

Exception Handling Flow:
    1. Service layer raises typed exception
    2. FastAPI exception handler catches it (see main.py)
    3. Handler converts to structured JSON response
    4. Client receives error envelope with code, message, and context
"""

from __future__ import annotations


class ServiceError(Exception):
    """Base exception for all service layer errors."""


class ValidationError(ServiceError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class NotFoundError(ServiceError):
    """Raised when a requested resource cannot be located."""

    def __init__(self, message: str, resource: str | None = None):
        self.message = message
        self.resource = resource
        super().__init__(self.message)


class ProviderError(ServiceError):
    """Raised when an external provider (AI API) fails."""

    def __init__(self, message: str, provider: str | None = None, original_error: Exception | None = None):
        self.message = message
        self.provider = provider
        self.original_error = original_error
        super().__init__(self.message)


class ConfigurationError(ServiceError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str, key: str | None = None):
        self.message = message
        self.key = key
        super().__init__(self.message)


class StreamingError(ServiceError):
    """Raised when a streaming operation fails."""

    def __init__(self, message: str, stage: str | None = None):
        self.message = message
        self.stage = stage
        super().__init__(self.message)


class CompletionOwnershipError(StreamingError):
    """Raised when streaming completion ownership rules are violated."""

    def __init__(self, message: str):
        super().__init__(message, stage="completion")


class DatabaseError(ServiceError):
    """Raised when database operations fail."""

    def __init__(self, message: str, operation: str | None = None):
        self.message = message
        self.operation = operation
        super().__init__(self.message)


class AuthenticationError(ServiceError):
    """Raised when authentication fails."""


class RateLimitError(ProviderError):
    """Raised when a provider rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after
