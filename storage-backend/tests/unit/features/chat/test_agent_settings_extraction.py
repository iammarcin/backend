"""Tests for agent settings extraction.

Note: Agentic workflow has been removed. The extract_agent_settings function
now always returns enabled=False for backward compatibility.
"""

from features.chat.utils.websocket_request import extract_agent_settings


def test_extract_agent_settings_always_disabled():
    """Test that agentic mode is always disabled after removal."""

    # Even with ai_agent_enabled=True, function returns False
    data = {
        "user_settings": {
            "general": {
                "ai_agent_enabled": True,
                "ai_agent_profile": "media",
            }
        }
    }

    result = extract_agent_settings(data)
    assert result["enabled"] is False
    assert result["profile"] == "general"


def test_extract_agent_settings_defaults():
    """Test default values when settings missing."""

    result = extract_agent_settings({})
    assert result["enabled"] is False
    assert result["profile"] == "general"
