"""Error mapping for poller stream errors.

Maps error codes from the poller to user-friendly messages.
"""

ERROR_MESSAGES: dict[str, str] = {
    "rate_limit": "Rate limit exceeded. Please wait a moment.",
    "auth_expired": "Session expired. Please start a new conversation.",
    "context_too_long": "Conversation too long. Please start a new session.",
    "resume_not_found": "Previous session not found. Starting fresh.",
    "backpressure": "Server is busy. Please try again.",
    "connection_lost": "Connection lost. Please resend your message.",
    # SDK daemon capacity/resource errors
    "capacity_exhausted": "Sherlock is busy with another task. Please try again in a moment.",
    "insufficient_memory": "Server resources are limited. Please try again shortly.",
    "sdk_error": "Connection to Sherlock failed. Please try again.",
    "unknown": "An error occurred. Please try again.",
}


def get_user_friendly_error(code: str, raw_message: str | None = None) -> str:
    """Get user-friendly error message for error code.

    Args:
        code: Error code from poller or internal error.
        raw_message: Optional raw message (used for logging, not exposed).

    Returns:
        User-friendly error message.
    """
    return ERROR_MESSAGES.get(code, ERROR_MESSAGES["unknown"])


__all__ = ["ERROR_MESSAGES", "get_user_friendly_error"]
