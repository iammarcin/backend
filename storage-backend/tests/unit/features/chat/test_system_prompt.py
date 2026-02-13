"""Unit tests for system prompt resolution helpers."""

from features.chat.utils.system_prompt import resolve_system_prompt, set_system_prompt


def test_set_system_prompt_defaults_to_assistant():
    prompt = set_system_prompt("")
    assert "capable" in prompt or "thoughtful" in prompt


def test_set_system_prompt_flowstudio_clarification():
    prompt = set_system_prompt("flowstudio_clarification")
    assert "creative consultant" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_resolve_system_prompt_from_settings():
    settings = {"text": {"ai_character": "flowstudio_clarification"}}
    prompt = resolve_system_prompt(settings)
    assert prompt
    assert "clarifying questions" in prompt


def test_resolve_system_prompt_defaults_when_missing():
    prompt = resolve_system_prompt({})
    assert "capable" in prompt or "thoughtful" in prompt
