"""Tests for realtime audio handler VAD and buffer commit behaviour."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.providers.realtime.audio_handler import AudioQueueHandler


@pytest.mark.asyncio
async def test_vad_mode_skips_commit_on_recording_finished() -> None:
    """When VAD is enabled, the handler should not commit an empty buffer."""

    handler = AudioQueueHandler()

    mock_client = AsyncMock()
    mock_client.send = AsyncMock()
    mock_config = MagicMock()
    mock_config.vad_enabled = True
    mock_config.output_modalities.return_value = ["text"]

    handler.set_client(mock_client)
    handler.set_session_config(mock_config)

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await queue.put(None)
    await handler.set_input_audio_queue(queue)

    handler.start_audio_sender()
    await asyncio.sleep(0.05)
    await handler.stop_audio_sender()

    sent_payloads = [json.loads(call.args[0]) for call in mock_client.send.await_args_list]
    commit_events = [payload for payload in sent_payloads if payload.get("type") == "input_audio_buffer.commit"]

    assert not commit_events, "VAD mode should not commit an empty audio buffer"


@pytest.mark.asyncio
async def test_non_vad_mode_commits_and_triggers_response() -> None:
    """When VAD is disabled, the handler commits and sends response.create."""

    handler = AudioQueueHandler()

    mock_client = AsyncMock()
    mock_client.send = AsyncMock()
    mock_config = MagicMock()
    mock_config.vad_enabled = False
    mock_config.output_modalities.return_value = ["text"]

    handler.set_client(mock_client)
    handler.set_session_config(mock_config)

    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    await queue.put(b"audio-data")
    await queue.put(None)
    await handler.set_input_audio_queue(queue)

    handler.start_audio_sender()
    await asyncio.sleep(0.05)
    await handler.stop_audio_sender()

    sent_payloads = [json.loads(call.args[0]) for call in mock_client.send.await_args_list]
    event_types = {payload.get("type") for payload in sent_payloads}

    assert "input_audio_buffer.commit" in event_types, "Non-VAD mode should commit audio buffer"
    assert "response.create" in event_types, "Non-VAD mode should trigger model response"
