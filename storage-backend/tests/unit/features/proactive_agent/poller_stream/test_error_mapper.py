"""Tests for error_mapper module."""

import pytest

from features.proactive_agent.poller_stream.error_mapper import (
    ERROR_MESSAGES,
    get_user_friendly_error,
)


class TestErrorMessages:
    """Tests for ERROR_MESSAGES constant."""

    def test_all_codes_have_messages(self):
        """All expected error codes have messages."""
        expected_codes = [
            "rate_limit",
            "auth_expired",
            "context_too_long",
            "resume_not_found",
            "backpressure",
            "connection_lost",
            "unknown",
        ]
        for code in expected_codes:
            assert code in ERROR_MESSAGES
            assert len(ERROR_MESSAGES[code]) > 0

    def test_messages_are_user_friendly(self):
        """Messages don't contain technical jargon."""
        technical_terms = ["429", "500", "exception", "traceback", "stacktrace"]
        for message in ERROR_MESSAGES.values():
            for term in technical_terms:
                assert term.lower() not in message.lower()


class TestGetUserFriendlyError:
    """Tests for get_user_friendly_error function."""

    def test_known_code_returns_mapped_message(self):
        """Known error code returns mapped message."""
        result = get_user_friendly_error("rate_limit", "429 Too Many Requests")
        assert result == ERROR_MESSAGES["rate_limit"]

    def test_unknown_code_returns_default(self):
        """Unknown error code returns default message."""
        result = get_user_friendly_error("some_unknown_code", "Internal error")
        assert result == ERROR_MESSAGES["unknown"]

    def test_raw_message_not_exposed(self):
        """Raw technical message is not returned."""
        raw_message = "Traceback (most recent call last): ..."
        result = get_user_friendly_error("unknown", raw_message)
        assert "Traceback" not in result

    def test_all_known_codes(self):
        """All known codes return correct messages."""
        codes = [
            "rate_limit",
            "auth_expired",
            "context_too_long",
            "resume_not_found",
            "backpressure",
            "connection_lost",
        ]
        for code in codes:
            result = get_user_friendly_error(code)
            assert result == ERROR_MESSAGES[code]

    def test_none_raw_message_works(self):
        """Function works when raw_message is None."""
        result = get_user_friendly_error("rate_limit", None)
        assert result == ERROR_MESSAGES["rate_limit"]
