"""Unit tests for Gemini tool configuration helpers."""

from __future__ import annotations

from core.providers.text.gemini.config import (
    has_custom_function_declarations,
    prepare_tool_settings,
)


def test_has_custom_function_declarations_detects_gemini_payload():
    tools = [{"function_declarations": [{"name": "alpha"}]}]
    assert has_custom_function_declarations(tools) is True


def test_has_custom_function_declarations_detects_internal_tools():
    tools = [
        {
            "name": "generate_image",
            "description": "",
            "parameters": {"type": "object"},
        }
    ]
    assert has_custom_function_declarations(tools) is True


def test_has_custom_function_declarations_handles_empty_entries():
    assert has_custom_function_declarations(None) is False
    assert has_custom_function_declarations([]) is False
    assert has_custom_function_declarations([{"name": ""}]) is False


def test_prepare_tool_settings_disables_native_tools_when_custom_present():
    settings = prepare_tool_settings(
        {"functions": [{"name": "generate_image", "parameters": {"type": "object"}}]}
    )
    assert settings["google_search"].get("enabled") is False
    assert settings["code_execution"] is False


def test_prepare_tool_settings_retains_native_tools_without_functions():
    settings = prepare_tool_settings({})
    assert settings["google_search"].get("enabled") is True
    assert settings["code_execution"] is True
