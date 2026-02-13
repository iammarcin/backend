"""Tests for AI client initialisation module."""

import importlib
import sys


def reload_module():
    if "core.clients.ai" in sys.modules:
        del sys.modules["core.clients.ai"]
    return importlib.import_module("core.clients.ai")


def test_ai_clients_without_env(monkeypatch):
    """When no environment variables set, no clients should be created."""

    for key in [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "CLAUDE_KEY",  # This is the actual key used for Anthropic clients
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "PERPLEXITY_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAI_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    module = reload_module()
    assert module.ai_clients == {}


def test_ai_clients_with_env(monkeypatch):
    """Setting env variables should register corresponding clients."""

    import openai
    import anthropic
    from google import genai
    import xai_sdk

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    class DummyGenClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("GOOGLE_API_KEY", "test")
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test")
    monkeypatch.setenv("XAI_API_KEY", "test")

    monkeypatch.setattr(openai, "OpenAI", DummyClient)
    monkeypatch.setattr(openai, "AsyncOpenAI", DummyClient)
    monkeypatch.setattr(anthropic, "Anthropic", DummyClient)
    monkeypatch.setattr(anthropic, "AsyncAnthropic", DummyClient)
    class DummyXaiChat:
        def create(self, *args, **kwargs):
            class DummyRequest:
                def stream(self):
                    return iter(())

                def sample(self):
                    class DummyResponse:
                        id = "dummy"
                        role = "assistant"
                        content = ""
                        finish_reason = "stop"
                        usage = None
                        request_settings = type("R", (), {"model": "grok"})()

                    return DummyResponse()

            return DummyRequest()

    class DummyXaiClient:
        def __init__(self, *args, **kwargs):
            self.chat = DummyXaiChat()

        def close(self):
            return None

    class DummyXaiAsyncClient(DummyXaiClient):
        async def close(self):
            return None

    monkeypatch.setattr(genai, "Client", DummyGenClient)
    monkeypatch.setattr(xai_sdk, "Client", DummyXaiClient)
    monkeypatch.setattr(xai_sdk, "AsyncClient", DummyXaiAsyncClient)

    module = reload_module()

    assert {"openai", "anthropic", "gemini", "groq", "perplexity", "deepseek", "xai"}.issubset(module.ai_clients.keys())
