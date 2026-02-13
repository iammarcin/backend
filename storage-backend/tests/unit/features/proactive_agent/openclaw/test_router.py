"""Unit tests for OpenClaw router."""

from __future__ import annotations

from features.proactive_agent.openclaw.stream_callbacks import _is_tts_enabled


class TestIsTtsEnabled:
    """Test _is_tts_enabled helper function."""

    def test_returns_false_when_none(self):
        """Returns False when tts_settings is None."""
        assert _is_tts_enabled(None) is False

    def test_returns_false_when_empty_dict(self):
        """Returns False when tts_settings is empty dict."""
        assert _is_tts_enabled({}) is False

    def test_returns_false_when_not_dict(self):
        """Returns False when tts_settings is not a dict."""
        assert _is_tts_enabled("not a dict") is False
        assert _is_tts_enabled([]) is False
        assert _is_tts_enabled(123) is False

    def test_returns_false_when_auto_execute_false(self):
        """Returns False when tts_auto_execute is False."""
        assert _is_tts_enabled({"tts_auto_execute": False}) is False

    def test_returns_false_when_auto_execute_missing(self):
        """Returns False when tts_auto_execute is missing."""
        assert _is_tts_enabled({"voice": "alloy"}) is False

    def test_returns_true_when_auto_execute_true(self):
        """Returns True when tts_auto_execute is True."""
        assert _is_tts_enabled({"tts_auto_execute": True}) is True

    def test_returns_true_with_other_settings(self):
        """Returns True when tts_auto_execute is True with other settings."""
        settings = {
            "tts_auto_execute": True,
            "voice": "nova",
            "model": "tts-1-hd",
        }
        assert _is_tts_enabled(settings) is True

