"""Exception classes for OpenClaw Gateway client.

This module defines the exception hierarchy for OpenClaw client errors:
- OpenClawError: Base exception for all OpenClaw errors
- ProtocolError: Protocol-level errors (handshake, version mismatch)
- RequestError: Request failures with error codes from gateway
"""


class OpenClawError(Exception):
    """Base exception for OpenClaw client errors."""

    pass


class ProtocolError(OpenClawError):
    """Protocol-level error (handshake failed, version mismatch)."""

    pass


class RequestError(OpenClawError):
    """Request failed with ok=false response from gateway.

    Attributes:
        code: Error code from gateway (e.g., "UNAVAILABLE", "INVALID_REQUEST")
        message: Human-readable error message
        retryable: Whether the request can be retried
    """

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.retryable = retryable
