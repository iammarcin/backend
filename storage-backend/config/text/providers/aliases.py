"""Canonical mappings from alias names to model identifiers."""

from __future__ import annotations

MODEL_ALIASES: dict[str, str] = {
    "claude": "claude-sonnet",
    "claude-mini": "claude-haiku",
    "claude-haiku-4.5": "claude-haiku",
    "claude-4-opus": "claude-opus",
    "gemini": "gemini-3-pro-preview",
    "gemini-mini": "gemini-flash",
    "openai": "gpt-4o",
    "gpt-5": "gpt-5.2",
    "grok": "grok-4",
    "grok-mini": "grok-4.1-mini",
    "llama": "llama-3.3-70b",
    "gpt-oss": "gpt-oss-120b",
    "deepseek": "deepseek-chat",
    "perplexity": "sonar-pro",
    "cheapest-perplexity": "sonar",
    "cheapest-openai": "gpt-5-nano",
    "cheapest-gemini": "gemini-flash",
    "cheapest-claude": "claude-haiku",
    "cheapest-grok": "grok-mini",
    "cheapest-model": "gemini-flash",
    "openai-realtime": "gpt-realtime",
    "realtime": "gpt-realtime",
    "realtime-mini": "gpt-realtime-mini",
    "gpt-4o-realtime": "gpt-realtime",
    "gpt-realtime-preview": "gpt-realtime",
    "gpt-4o-realtime-preview": "gpt-realtime",
}

__all__ = ["MODEL_ALIASES"]
