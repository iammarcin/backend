import base64
import json
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions import ProviderError, ServiceError
from core.providers.audio.openai_streaming import OpenAIStreamingSpeechProvider
from core.providers.audio.utils.session import build_session_config
from core.providers.audio.utils.streaming import (
    forward_audio_chunks,
    receive_transcription_events,
)
from core.streaming.manager import StreamingManager


@pytest.fixture
def provider() -> OpenAIStreamingSpeechProvider:
    """Return a fresh provider for each test."""

    return OpenAIStreamingSpeechProvider()


@pytest.fixture
def mock_manager() -> StreamingManager:
    """Return a streaming manager with mocked fan-out helpers."""

    manager = StreamingManager()
    manager.send_to_queues = AsyncMock()
    manager.collect_chunk = MagicMock()
    return manager


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Return a mocked websocket client."""

    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


async def mock_audio_source(chunks: list[bytes | None]) -> AsyncIterator[bytes | None]:
    """Yield provided chunks to emulate microphone input."""

    for chunk in chunks:
        yield chunk


def _async_iter(events: list[str]) -> AsyncIterator[str]:
    """Return an async iterator over the supplied events."""

    async def iterator() -> AsyncIterator[str]:
        for event in events:
            yield event

    return iterator()


class TestOpenAIStreamingSpeechProvider:
    """Behavioural tests for the streaming provider."""

    def test_initialization_defaults(self, provider: OpenAIStreamingSpeechProvider) -> None:
        """Provider starts with expected defaults."""

        assert provider.name == "openai-streaming"
        assert provider.streaming_capable is True
        assert provider.supports_translation is False
        assert provider.model == "gpt-4o-transcribe"
        assert provider.sample_rate == 24000
        assert provider.enable_vad is True

    def test_configure_updates_fields(self, provider: OpenAIStreamingSpeechProvider) -> None:
        """Configuration payload customises runtime behaviour."""

        settings = {
            "model": "gpt-4o-mini-transcribe",
            "language": "es",
            "sample_rate": 24000,
            "recording_sample_rate": 44100,
            "enable_vad": False,
            "vad_threshold": 0.65,
            "vad_prefix_padding_ms": 120,
            "vad_silence_duration_ms": 750,
            "prompt": "Medical context",
        }

        provider.configure(settings)

        assert provider.model == "gpt-4o-mini-transcribe"
        assert provider.language == "es"
        assert provider.sample_rate == 24000
        assert provider.recording_sample_rate == 44100
        assert provider.enable_vad is False
        assert provider.vad_threshold == pytest.approx(0.65)
        assert provider.vad_prefix_padding_ms == 120
        assert provider.vad_silence_duration_ms == 750
        assert provider.prompt == "Medical context"

    def test_session_configuration_uses_realtime_type(
        self, provider: OpenAIStreamingSpeechProvider
    ) -> None:
        """Session payload conforms to GA realtime expectations."""

        config = build_session_config(
            model=provider.model,
            session_model="gpt-realtime",
            transcription_model=provider.model,
            language=provider.language,
            prompt="technical jargon expected",
            enable_vad=False,
        )

        assert config["type"] == "session.update"
        session = config["session"]
        assert session["type"] == "realtime"
        assert session["model"] == "gpt-realtime"
        audio_input = session["audio"]["input"]
        transcription = audio_input["transcription"]
        assert transcription["model"] == provider.model
        assert transcription["language"] == provider.language
        assert transcription["prompt"] == "technical jargon expected"
        assert audio_input["turn_detection"] is None

    def test_session_configuration_includes_vad_settings(
        self, provider: OpenAIStreamingSpeechProvider
    ) -> None:
        """VAD configuration maps into session payload when enabled."""

        config = build_session_config(
            model=provider.model,
            session_model="gpt-realtime",
            transcription_model=provider.model,
            language=provider.language,
            enable_vad=True,
            vad_threshold=0.65,
            vad_prefix_padding_ms=150,
            vad_silence_duration_ms=700,
        )

        audio_input = config["session"]["audio"]["input"]
        turn_detection = audio_input["turn_detection"]

        assert turn_detection is not None
        assert turn_detection["type"] == "server_vad"
        assert turn_detection["threshold"] == pytest.approx(0.65)
        assert turn_detection["prefix_padding_ms"] == 150
        assert turn_detection["silence_duration_ms"] == 700

    @pytest.mark.anyio
    async def test_transcribe_file_not_supported(self, provider: OpenAIStreamingSpeechProvider) -> None:
        """Static transcription delegates to non-streaming provider."""

        from core.providers.audio.base import SpeechProviderRequest

        request = SpeechProviderRequest(file_bytes=b"test")

        with pytest.raises(ProviderError) as exc:
            await provider.transcribe_file(request)

        assert "streaming transcription only" in str(exc.value).lower()

    @pytest.mark.anyio
    @patch("core.providers.audio.openai_streaming.OPENAI_API_KEY", None)
    async def test_transcribe_stream_requires_api_key(
        self, provider: OpenAIStreamingSpeechProvider, mock_manager: StreamingManager
    ) -> None:
        """ServiceError raised when credentials missing."""

        async def audio() -> AsyncIterator[bytes | None]:
            yield b"data"
            yield None

        with pytest.raises(ServiceError) as exc:
            await provider.transcribe_stream(
                audio_source=audio(),
                manager=mock_manager,
                mode="non-realtime",
            )

        assert "api key" in str(exc.value).lower()

    @pytest.mark.anyio
    @patch("core.providers.audio.openai_streaming.OPENAI_API_KEY", "test-key")
    @patch(
        "core.providers.audio.openai_streaming.receive_transcription_events",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.forward_audio_chunks",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.connect_to_openai_realtime",
        new_callable=AsyncMock,
    )
    async def test_connect_to_openai_sends_config(
        self,
        mock_connect: AsyncMock,
        mock_forward: AsyncMock,
        mock_receive: AsyncMock,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Provider passes configuration through to session helper."""

        mock_connect.return_value = mock_websocket
        mock_forward.return_value = 0
        mock_receive.return_value = ""

        audio = mock_audio_source([None])

        await provider.transcribe_stream(
            audio_source=audio,
            manager=mock_manager,
            mode="non-realtime",
        )

        mock_connect.assert_awaited_once()
        _, kwargs = mock_connect.await_args
        assert kwargs["model"] == provider.model
        assert kwargs["language"] == provider.language
        assert kwargs["prompt"] == provider.prompt
        assert kwargs["enable_vad"] is provider.enable_vad
        assert kwargs["vad_threshold"] == provider.vad_threshold
        assert kwargs["vad_prefix_padding_ms"] == provider.vad_prefix_padding_ms
        assert kwargs["vad_silence_duration_ms"] == provider.vad_silence_duration_ms

        mock_forward.assert_awaited_once()
        assert mock_forward.await_args.kwargs["sample_rate"] == provider.sample_rate
        mock_receive.assert_awaited_once_with(
            mock_websocket,
            mock_manager,
            mode="non-realtime",
            provider_name=provider.name,
        )
        mock_websocket.close.assert_awaited()

    @pytest.mark.anyio
    async def test_send_audio_chunks_base64_encodes(
        self, provider: OpenAIStreamingSpeechProvider, mock_websocket: AsyncMock
    ) -> None:
        """Audio chunks are encoded and final commit issued."""

        chunks = [b"\x01\x02" * 10, b"\x03\x04" * 8, None]
        audio = mock_audio_source(chunks)

        with patch(
            "core.providers.audio.utils.streaming._commit_audio_buffer",
            new=AsyncMock(),
        ) as mock_commit:
            count = await forward_audio_chunks(
                audio,
                mock_websocket,
                sample_rate=provider.sample_rate,
            )

        assert count == 2
        assert mock_websocket.send.await_count == 2

        first_message = json.loads(mock_websocket.send.call_args_list[0].args[0])
        assert first_message["type"] == "input_audio_buffer.append"
        base64.b64decode(first_message["audio"])  # raises if invalid

        mock_commit.assert_awaited_once()

    @pytest.mark.anyio
    async def test_send_audio_chunks_skips_empty(
        self, provider: OpenAIStreamingSpeechProvider, mock_websocket: AsyncMock
    ) -> None:
        """Empty buffers are ignored."""

        chunks = [b"\x00\x01", b"", b"\x02\x03", None]
        audio = mock_audio_source(chunks)

        with patch(
            "core.providers.audio.utils.streaming._commit_audio_buffer",
            new=AsyncMock(),
        ):
            count = await forward_audio_chunks(
                audio,
                mock_websocket,
                sample_rate=provider.sample_rate,
            )

        assert count == 2

    @pytest.mark.anyio
    async def test_receive_transcription_streams_deltas(
        self,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Delta events are forwarded to streaming manager."""

        events = [
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.delta",
                    "delta": "Hello ",
                }
            ),
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.delta",
                    "delta": "world",
                }
            ),
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "transcript": "Hello world",
                }
            ),
        ]

        mock_websocket.__aiter__ = MagicMock(return_value=_async_iter(events))

        result = await receive_transcription_events(
            mock_websocket,
            mock_manager,
            mode="non-realtime",
            provider_name=provider.name,
        )

        assert result == "Hello world"
        assert mock_manager.send_to_queues.await_count == 3
        assert mock_manager.collect_chunk.call_count == 2

    @pytest.mark.anyio
    async def test_receive_transcription_error_event(
        self,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Error events raise ProviderError."""

        events = [
            json.dumps(
                {
                    "type": "error",
                    "error": {"code": "invalid_audio", "message": "Audio format not supported"},
                }
            )
        ]

        mock_websocket.__aiter__ = MagicMock(return_value=_async_iter(events))

        with pytest.raises(ProviderError) as exc:
            await receive_transcription_events(
                mock_websocket,
                mock_manager,
                mode="non-realtime",
                provider_name=provider.name,
            )

        assert "audio format not supported" in str(exc.value).lower()

    @pytest.mark.anyio
    async def test_receive_transcription_realtime_mode(
        self,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Realtime mode avoids frontend queue fan-out."""

        events = [
            json.dumps(
                {
                    "type": "conversation.item.input_audio_transcription.delta",
                    "delta": "Realtime",
                }
            )
        ]

        mock_websocket.__aiter__ = MagicMock(return_value=_async_iter(events))

        result = await receive_transcription_events(
            mock_websocket,
            mock_manager,
            mode="realtime",
            provider_name=provider.name,
        )

        assert result == "Realtime"
        mock_manager.send_to_queues.assert_not_awaited()
        mock_manager.collect_chunk.assert_called_once_with("Realtime", "transcription")

    @pytest.mark.anyio
    @patch("core.providers.audio.openai_streaming.OPENAI_API_KEY", "test-key")
    @patch(
        "core.providers.audio.openai_streaming.receive_transcription_events",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.forward_audio_chunks",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.connect_to_openai_realtime",
        new_callable=AsyncMock,
    )
    async def test_transcribe_stream_happy_path(
        self,
        mock_connect: AsyncMock,
        mock_forward: AsyncMock,
        mock_receive: AsyncMock,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Full transcription flow returns aggregated text."""

        mock_connect.return_value = mock_websocket
        mock_forward.return_value = 2
        mock_receive.return_value = "Hello world"

        audio = mock_audio_source([b"\x00\x01" * 5, None])

        result = await provider.transcribe_stream(
            audio_source=audio,
            manager=mock_manager,
            mode="non-realtime",
        )

        assert result == "Hello world"
        mock_connect.assert_awaited_once()
        mock_forward.assert_awaited_once()
        mock_receive.assert_awaited_once()
        mock_websocket.close.assert_awaited()

    @pytest.mark.anyio
    @patch("core.providers.audio.openai_streaming.OPENAI_API_KEY", "test-key")
    @patch(
        "core.providers.audio.openai_streaming.receive_transcription_events",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.forward_audio_chunks",
        new_callable=AsyncMock,
    )
    @patch(
        "core.providers.audio.openai_streaming.connect_to_openai_realtime",
        new_callable=AsyncMock,
    )
    async def test_transcribe_stream_cleans_up_on_failure(
        self,
        mock_connect: AsyncMock,
        mock_forward: AsyncMock,
        mock_receive: AsyncMock,
        provider: OpenAIStreamingSpeechProvider,
        mock_manager: StreamingManager,
        mock_websocket: AsyncMock,
    ) -> None:
        """Errors propagate and websocket closes."""

        mock_connect.return_value = mock_websocket
        mock_forward.side_effect = ProviderError("Connection lost", provider=provider.name)
        mock_receive.return_value = ""

        audio = mock_audio_source([b"test", None])

        with pytest.raises(ProviderError):
            await provider.transcribe_stream(
                audio_source=audio,
                manager=mock_manager,
                mode="non-realtime",
            )

        mock_connect.assert_awaited_once()
        mock_forward.assert_awaited_once()
        assert mock_receive.await_count <= 1
        mock_websocket.close.assert_awaited()
