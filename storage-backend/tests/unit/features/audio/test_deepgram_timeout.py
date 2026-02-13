import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from features.audio.deepgram_helpers import receive_transcription


@pytest.mark.asyncio
async def test_receive_transcription_timeout_detection(caplog: pytest.LogCaptureFixture) -> None:
    """Receive handler should detect Deepgram timeout close code."""

    async def message_iter():
        yield json.dumps(
            {"type": "Results", "channel": {"alternatives": [{"transcript": "hello"}]}}
        )
        yield json.dumps(
            {"type": "Results", "channel": {"alternatives": [{"transcript": "world"}]}}
        )
        raise ConnectionClosedError(Close(1011, "Deepgram timeout"), None)

    class MockClient:
        def __aiter__(self):
            return message_iter()

    mock_client = MockClient()

    manager = MagicMock()
    manager.send_to_queues = AsyncMock()

    caplog.set_level(logging.DEBUG, logger="features.audio.deepgram_helpers")

    transcript = await receive_transcription(mock_client, manager, "simple")

    assert transcript == "hello world"

    timeout_logs = [record.message for record in caplog.records if "Deepgram timeout" in record.message]
    assert timeout_logs, "Expected timeout log entry when Deepgram closes with code 1011"

    code_logs = [record.message for record in caplog.records if "code=1011" in record.message]
    assert code_logs, "Expected connection close log to include close code"
