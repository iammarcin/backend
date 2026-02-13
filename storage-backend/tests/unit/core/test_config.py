"""Tests for configuration helpers."""

import importlib

import pytest

import core.config as config
from config.tts.providers import elevenlabs as tts_elevenlabs
from config.tts.providers import openai as tts_openai
from core.utils.env import get_env, get_node_env, is_local, is_production
from core.exceptions import ConfigurationError


def test_get_env_returns_default(monkeypatch):
    """get_env should return provided default when variable missing."""

    monkeypatch.delenv("NON_EXISTENT", raising=False)
    assert get_env("NON_EXISTENT", default="value") == "value"


def test_get_env_required(monkeypatch):
    """get_env should raise when required env missing."""

    monkeypatch.delenv("REQUIRED_KEY", raising=False)
    with pytest.raises(ConfigurationError):
        get_env("REQUIRED_KEY", required=True)


def test_environment_helpers(monkeypatch):
    """Environment helpers should respect NODE_ENV."""

    monkeypatch.setenv("NODE_ENV", "production")
    assert get_node_env() == "production"
    assert is_production() is True
    assert is_local() is False

    monkeypatch.setenv("NODE_ENV", "local")
    assert is_local() is True


def test_tts_configuration_defaults(monkeypatch):
    """TTS defaults should resolve to sensible fallback values."""

    monkeypatch.delenv("ELEVENLABS_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("OPENAI_TTS_MODEL_DEFAULT", raising=False)

    reloaded_elevenlabs = importlib.reload(tts_elevenlabs)
    reloaded_openai = importlib.reload(tts_openai)

    assert reloaded_elevenlabs.DEFAULT_MODEL == "eleven_monolingual_v1"
    assert reloaded_openai.DEFAULT_MODEL == "gpt-4o-mini-tts"

    importlib.reload(tts_elevenlabs)
    importlib.reload(tts_openai)


def test_tts_configuration_reads_env(monkeypatch):
    """Reloading the module should pick up overridden environment variables."""

    monkeypatch.setenv("ELEVENLABS_MODEL_DEFAULT", "eleven_multilingual_v2")
    monkeypatch.setenv("OPENAI_TTS_MODEL_DEFAULT", "gpt-4o-test")

    reloaded_elevenlabs = importlib.reload(tts_elevenlabs)
    reloaded_openai = importlib.reload(tts_openai)

    assert reloaded_elevenlabs.DEFAULT_MODEL == "eleven_multilingual_v2"
    assert reloaded_openai.DEFAULT_MODEL == "gpt-4o-test"

    monkeypatch.delenv("ELEVENLABS_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("OPENAI_TTS_MODEL_DEFAULT", raising=False)
    importlib.reload(tts_elevenlabs)
    importlib.reload(tts_openai)


def test_get_collection_for_mode_semantic() -> None:
    assert (
        config.get_collection_for_mode("semantic")
        == config.SEMANTIC_COLLECTION_MAPPING["semantic"]
    )


def test_get_collection_for_mode_hybrid() -> None:
    assert (
        config.get_collection_for_mode("hybrid")
        == config.SEMANTIC_COLLECTION_MAPPING["hybrid"]
    )


def test_get_collection_for_mode_keyword() -> None:
    assert (
        config.get_collection_for_mode("keyword")
        == config.SEMANTIC_COLLECTION_MAPPING["keyword"]
    )


def test_get_collection_for_mode_invalid() -> None:
    with pytest.raises(ValueError):
        config.get_collection_for_mode("invalid-mode")
