from __future__ import annotations

import pytest

from features.audio.streaming_workflow import transcribe_streaming_audio


pytestmark = pytest.mark.anyio


class DummyManager:
    def __init__(self):
        self.tokens: list[str] = []

    async def signal_completion(self, *, token: str) -> None:
        self.tokens.append(token)


class DummyProvider:
    name = "dummy"

    async def transcribe_stream(self, *, audio_source, manager, mode):
        return "cloud code sample"


async def test_transcribe_streaming_audio_applies_transcript_rewriter(monkeypatch):
    provider = DummyProvider()
    monkeypatch.setattr(
        "features.audio.streaming_workflow.get_audio_provider",
        lambda settings, action=None: provider,
    )

    async def audio_source():
        yield b"chunk"
        yield None

    captured_context: dict[str, object] = {}

    def rewriter(text: str, context):
        captured_context.update(context or {})
        return text.replace("cloud code", "Claude Code")

    manager = DummyManager()
    transcript = await transcribe_streaming_audio(
        {"provider": "dummy", "model": "demo"},
        audio_source=audio_source(),
        manager=manager,
        mode="non-realtime",
        transcript_rewriter=rewriter,
    )

    assert transcript == "Claude Code sample"
    assert captured_context == {
        "provider": "dummy",
        "model": "demo",
        "action": "stream",
        "mode": "non-realtime",
    }
