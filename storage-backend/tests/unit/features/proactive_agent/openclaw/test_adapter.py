"""Unit tests for OpenClaw Chat Adapter."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from features.proactive_agent.openclaw.adapter import OpenClawAdapter, StreamContext
from features.proactive_agent.openclaw.client import RequestError


class TestStreamContext:
    """Test StreamContext dataclass."""

    def test_default_values(self):
        """StreamContext has correct default values."""
        ctx = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id="run-1",
            session_key="openclaw:session-1",
        )

        assert ctx.user_id == 1
        assert ctx.session_id == "session-1"
        assert ctx.run_id == "run-1"
        assert ctx.session_key == "openclaw:session-1"
        assert ctx.started is False
        assert ctx.text_buffer == ""
        assert ctx.seq == 0
        assert ctx.on_stream_start is None
        assert ctx.on_text_chunk is None
        assert ctx.on_stream_end is None
        assert ctx.on_error is None

    def test_with_callbacks(self):
        """StreamContext stores callbacks."""
        on_start = AsyncMock()
        on_chunk = AsyncMock()
        on_end = AsyncMock()
        on_error = AsyncMock()

        ctx = StreamContext(
            user_id=1,
            session_id="s",
            run_id="r",
            session_key="k",
            on_stream_start=on_start,
            on_text_chunk=on_chunk,
            on_stream_end=on_end,
            on_error=on_error,
        )

        assert ctx.on_stream_start is on_start
        assert ctx.on_text_chunk is on_chunk
        assert ctx.on_stream_end is on_end
        assert ctx.on_error is on_error


class TestOpenClawAdapterInit:
    """Test OpenClawAdapter initialization."""

    def test_init_stores_client(self):
        """Adapter stores client reference."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)
        assert adapter._client is client

    def test_init_empty_streams(self):
        """Adapter starts with no active streams."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)
        assert adapter.active_stream_count == 0
        assert adapter.get_active_run_ids() == []


class TestSendMessage:
    """Test send_message method."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with mock client."""
        client = MagicMock()
        client.request = AsyncMock(return_value={"status": "accepted"})
        return OpenClawAdapter(client)

    @pytest.mark.asyncio
    async def test_send_message_returns_run_id(self, adapter):
        """send_message returns a UUID run_id."""
        run_id = await adapter.send_message(
            user_id=1,
            session_id="session-1",
            session_key="openclaw:session-1",
            message="Hello",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )

        assert run_id is not None
        assert len(run_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_send_message_calls_client(self, adapter):
        """send_message sends chat.send request to client."""
        await adapter.send_message(
            user_id=1,
            session_id="session-1",
            session_key="openclaw:session-1",
            message="Hello",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )

        adapter._client.request.assert_called_once()
        call_args = adapter._client.request.call_args
        assert call_args[0][0] == "chat.send"
        params = call_args[0][1]
        assert params["sessionKey"] == "openclaw:session-1"
        assert params["message"] == "Hello"
        assert "idempotencyKey" in params

    @pytest.mark.asyncio
    async def test_send_message_registers_stream(self, adapter):
        """send_message registers stream context."""
        run_id = await adapter.send_message(
            user_id=1,
            session_id="session-1",
            session_key="openclaw:session-1",
            message="Hello",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )

        assert adapter.active_stream_count == 1
        assert run_id in adapter.get_active_run_ids()

    @pytest.mark.asyncio
    async def test_send_message_error_cleans_up(self, adapter):
        """send_message removes stream on request error."""
        adapter._client.request = AsyncMock(
            side_effect=RequestError("ERR", "Failed", retryable=False)
        )

        with pytest.raises(RequestError):
            await adapter.send_message(
                user_id=1,
                session_id="session-1",
                session_key="openclaw:session-1",
                message="Hello",
                on_stream_start=AsyncMock(),
                on_text_chunk=AsyncMock(),
                on_stream_end=AsyncMock(),
                on_error=AsyncMock(),
            )

        assert adapter.active_stream_count == 0


class TestHandleEvent:
    """Test handle_event method."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        client.request = AsyncMock(return_value={"status": "accepted"})
        adapter = OpenClawAdapter(client)

        # Manually add a stream context
        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_ignores_non_chat_events(self, adapter_with_stream):
        """Non-chat events are ignored."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({"event": "tick", "payload": {}})

        # No callbacks called
        ctx = adapter._active_streams[run_id]
        ctx.on_stream_start.assert_not_called()
        ctx.on_text_chunk.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_missing_run_id(self, adapter_with_stream):
        """Events without runId are ignored."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({"event": "chat", "payload": {}})

        # No callbacks called
        ctx = adapter._active_streams[run_id]
        ctx.on_stream_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_unknown_run_id(self, adapter_with_stream):
        """Events with unknown runId are ignored."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({
            "event": "chat",
            "payload": {"runId": "unknown-run-id"},
        })

        # No callbacks called
        ctx = adapter._active_streams[run_id]
        ctx.on_stream_start.assert_not_called()


class TestLifecycleHandling:
    """Test agent lifecycle event handling."""

    @pytest.mark.asyncio
    async def test_steered_lifecycle_cleans_orphan_streams(self):
        """Steered lifecycle removes sibling non-started contexts in same session."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        active_run_id = "active-run-12345678"
        orphan_run_id = "orphan-run-12345678"
        other_session_run_id = "other-session-123"

        active_ctx = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=active_run_id,
            session_key="openclaw:session-1",
        )
        active_ctx.started = True

        orphan_ctx = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=orphan_run_id,
            session_key="openclaw:session-1",
        )
        orphan_ctx.started = False

        other_session_ctx = StreamContext(
            user_id=2,
            session_id="session-2",
            run_id=other_session_run_id,
            session_key="openclaw:session-2",
        )
        other_session_ctx.started = False

        adapter._active_streams[active_run_id] = active_ctx
        adapter._active_streams[orphan_run_id] = orphan_ctx
        adapter._active_streams[other_session_run_id] = other_session_ctx

        await adapter.handle_event({
            "event": "agent",
            "payload": {
                "runId": active_run_id,
                "stream": "lifecycle",
                "data": {"phase": "steered"},
            },
        })

        assert active_run_id in adapter._active_streams
        assert orphan_run_id not in adapter._active_streams
        assert other_session_run_id in adapter._active_streams

    @pytest.mark.asyncio
    async def test_periodic_stale_cleanup_runs_at_most_once_per_interval(self):
        """Periodic stale cleanup is throttled and not run on every event."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)
        adapter.cleanup_stale_streams = AsyncMock(return_value=0)

        await adapter.handle_event({"event": "tick", "payload": {}})
        await adapter.handle_event({"event": "tick", "payload": {}})

        adapter.cleanup_stale_streams.assert_awaited_once_with(timeout_seconds=600)

    @pytest.mark.asyncio
    async def test_force_complete_non_started_context_skips_callbacks(self):
        """Never-started contexts are treated as orphans during forced cleanup."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "orphan-run-id"
        on_start = AsyncMock()
        on_end = AsyncMock()
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=on_start,
            on_stream_end=on_end,
        )

        result = await adapter.force_complete_stream(run_id, reason="idle_timeout")

        assert result is True
        on_start.assert_not_called()
        on_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_force_complete_started_context_emits_stream_end(self):
        """Started contexts still force-complete with accumulated text."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "started-run-id"
        on_end = AsyncMock()
        context = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_end=on_end,
        )
        context.started = True
        context.total_text = "partial output"
        adapter._active_streams[run_id] = context

        result = await adapter.force_complete_stream(run_id, reason="idle_timeout")

        assert result is True
        on_end.assert_called_once_with("session-1", run_id, "partial output")


class TestHandleDelta:
    """Test delta event handling."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_first_delta_emits_stream_start(self, adapter_with_stream):
        """First delta emits stream_start."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            },
        })

        ctx.on_stream_start.assert_called_once_with("session-1")

    @pytest.mark.asyncio
    async def test_delta_emits_text_chunk(self, adapter_with_stream):
        """Delta emits text_chunk with incremental text."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            },
        })

        ctx.on_text_chunk.assert_called_once_with("Hello")

    @pytest.mark.asyncio
    async def test_delta_computes_incremental_text(self, adapter_with_stream):
        """Delta computes incremental text from accumulated."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        # First delta
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            },
        })

        # Second delta with accumulated text
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 2,
                "message": {"content": [{"type": "text", "text": "Hello, World!"}]},
            },
        })

        # Should have called with incremental chunks
        assert ctx.on_text_chunk.call_count == 2
        calls = [call[0][0] for call in ctx.on_text_chunk.call_args_list]
        assert calls == ["Hello", ", World!"]

    @pytest.mark.asyncio
    async def test_delta_ignores_out_of_order_seq(self, adapter_with_stream):
        """Delta ignores out-of-order sequence numbers."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        # First delta with seq=2
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 2,
                "message": {"content": [{"type": "text", "text": "Hello"}]},
            },
        })

        # Second delta with seq=1 (out of order)
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "Old"}]},
            },
        })

        # Should only have one call
        assert ctx.on_text_chunk.call_count == 1
        ctx.on_text_chunk.assert_called_with("Hello")

    @pytest.mark.asyncio
    async def test_delta_ignores_empty_text(self, adapter_with_stream):
        """Delta ignores events with no text content."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {"content": []},
            },
        })

        ctx.on_stream_start.assert_not_called()
        ctx.on_text_chunk.assert_not_called()

    @pytest.mark.asyncio
    async def test_delta_extracts_all_text_blocks(self, adapter_with_stream):
        """Delta extracts and concatenates ALL text blocks."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "tool"},
                        {"type": "text", "text": "First"},
                        {"type": "text", "text": "Second"},
                    ]
                },
            },
        })

        # Now concatenates all text blocks with newline separator
        ctx.on_text_chunk.assert_called_once_with("First\n\nSecond")

    @pytest.mark.asyncio
    async def test_stream_start_only_called_once(self, adapter_with_stream):
        """stream_start is only called on first delta."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        # Multiple deltas
        for i in range(3):
            await adapter.handle_event({
                "event": "chat",
                "payload": {
                    "runId": run_id,
                    "state": "delta",
                    "seq": i + 1,
                    "message": {"content": [{"type": "text", "text": f"Text {i + 1}"}]},
                },
            })

        # stream_start called only once
        ctx.on_stream_start.assert_called_once()


class TestHandleFinal:
    """Test final event handling."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_final_emits_stream_end(self, adapter_with_stream):
        """Final emits stream_end with correct args."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]
        ctx.started = True
        ctx.text_buffer = "Hello, World!"

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "final",
                "message": {"content": [{"type": "text", "text": "Hello, World!"}]},
            },
        })

        ctx.on_stream_end.assert_called_once_with(
            "session-1",
            run_id,
            "Hello, World!",
        )

    @pytest.mark.asyncio
    async def test_final_removes_stream(self, adapter_with_stream):
        """Final removes stream from active streams."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "final",
                "message": {"content": [{"type": "text", "text": "Done"}]},
            },
        })

        assert adapter.active_stream_count == 0

    @pytest.mark.asyncio
    async def test_final_without_prior_delta_skips_callbacks(self, adapter_with_stream):
        """Final for non-started context (steer orphan) skips all callbacks.

        OpenClaw broadcasts chat/final for queued steer messages that never
        started a new run. Sending stream_start + stream_end would reset the
        frontend's streaming state and drop the real run's text_chunks.
        """
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "final",
                "message": {"content": [{"type": "text", "text": "Instant reply"}]},
            },
        })

        ctx.on_stream_start.assert_not_called()
        ctx.on_text_chunk.assert_not_called()
        ctx.on_stream_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_final_empty_text_non_started_skips(self, adapter_with_stream):
        """Final with empty text and non-started context skips callbacks."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "final",
                "message": {"content": []},
            },
        })

        ctx.on_stream_start.assert_not_called()
        ctx.on_text_chunk.assert_not_called()
        ctx.on_stream_end.assert_not_called()

    @pytest.mark.asyncio
    async def test_final_uses_final_text_as_authoritative(self, adapter_with_stream):
        """Final event uses final_text over buffer (source of truth)."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]
        ctx.started = True
        ctx.text_buffer = "Longer response already accumulated"

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "final",
                "message": {"content": [{"type": "text", "text": "Short"}]},
            },
        })

        ctx.on_stream_end.assert_called_once_with(
            "session-1",
            run_id,
            "Short",
        )


class TestHandleError:
    """Test error event handling."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_error_emits_on_error(self, adapter_with_stream):
        """Error emits on_error callback."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "error",
                "errorMessage": "Something went wrong",
            },
        })

        ctx.on_error.assert_called_once_with("Something went wrong")

    @pytest.mark.asyncio
    async def test_error_removes_stream(self, adapter_with_stream):
        """Error removes stream from active streams."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "error",
                "errorMessage": "Error",
            },
        })

        assert adapter.active_stream_count == 0

    @pytest.mark.asyncio
    async def test_error_default_message(self, adapter_with_stream):
        """Error uses default message if not provided."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "error",
            },
        })

        ctx.on_error.assert_called_once_with("Unknown error")


class TestHandleAborted:
    """Test aborted event handling."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_aborted_emits_on_error(self, adapter_with_stream):
        """Aborted emits on_error with abort message."""
        adapter, run_id = adapter_with_stream
        ctx = adapter._active_streams[run_id]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "aborted",
            },
        })

        ctx.on_error.assert_called_once_with("Request was aborted")

    @pytest.mark.asyncio
    async def test_aborted_removes_stream(self, adapter_with_stream):
        """Aborted removes stream from active streams."""
        adapter, run_id = adapter_with_stream

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "aborted",
            },
        })

        assert adapter.active_stream_count == 0


class TestAbort:
    """Test abort method."""

    @pytest.fixture
    def adapter_with_stream(self):
        """Create adapter with one active stream."""
        client = MagicMock()
        client.request = AsyncMock(return_value={})
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
        )
        return adapter, run_id

    @pytest.mark.asyncio
    async def test_abort_sends_request(self, adapter_with_stream):
        """abort sends chat.abort request."""
        adapter, run_id = adapter_with_stream

        result = await adapter.abort(run_id)

        assert result is True
        adapter._client.request.assert_called_once_with(
            "chat.abort",
            {"sessionKey": "openclaw:session-1", "runId": run_id},
        )

    @pytest.mark.asyncio
    async def test_abort_unknown_run_id(self, adapter_with_stream):
        """abort returns False for unknown run_id."""
        adapter, run_id = adapter_with_stream

        result = await adapter.abort("unknown-run-id")

        assert result is False
        adapter._client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_abort_request_error(self, adapter_with_stream):
        """abort returns False on RequestError."""
        adapter, run_id = adapter_with_stream
        adapter._client.request = AsyncMock(
            side_effect=RequestError("ERR", "Failed", retryable=False)
        )

        result = await adapter.abort(run_id)

        assert result is False


class TestCleanup:
    """Test cleanup methods."""

    def test_cleanup_stream(self):
        """cleanup_stream removes specific stream."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id1 = "run-1"
        run_id2 = "run-2"
        adapter._active_streams[run_id1] = StreamContext(
            user_id=1, session_id="s1", run_id=run_id1, session_key="k1"
        )
        adapter._active_streams[run_id2] = StreamContext(
            user_id=1, session_id="s2", run_id=run_id2, session_key="k2"
        )

        adapter.cleanup_stream(run_id1)

        assert adapter.active_stream_count == 1
        assert run_id1 not in adapter.get_active_run_ids()
        assert run_id2 in adapter.get_active_run_ids()

    def test_cleanup_stream_unknown(self):
        """cleanup_stream handles unknown run_id."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        # Should not raise
        adapter.cleanup_stream("unknown")
        assert adapter.active_stream_count == 0

    def test_cleanup_all_streams(self):
        """cleanup_all_streams removes all streams."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        for i in range(5):
            run_id = f"run-{i}"
            adapter._active_streams[run_id] = StreamContext(
                user_id=1, session_id=f"s{i}", run_id=run_id, session_key=f"k{i}"
            )

        run_ids = adapter.cleanup_all_streams()

        assert adapter.active_stream_count == 0
        assert len(run_ids) == 5


class TestConcurrentStreams:
    """Test concurrent stream handling."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_streams(self):
        """Adapter handles multiple concurrent streams."""
        client = MagicMock()
        client.request = AsyncMock(return_value={"status": "accepted"})
        adapter = OpenClawAdapter(client)

        # Start 3 concurrent streams
        run_ids = []
        for i in range(3):
            run_id = await adapter.send_message(
                user_id=i,
                session_id=f"session-{i}",
                session_key=f"openclaw:session-{i}",
                message=f"Message {i}",
                on_stream_start=AsyncMock(),
                on_text_chunk=AsyncMock(),
                on_stream_end=AsyncMock(),
                on_error=AsyncMock(),
            )
            run_ids.append(run_id)

        assert adapter.active_stream_count == 3

        # Events are routed to correct stream
        ctx0 = adapter._active_streams[run_ids[0]]
        ctx1 = adapter._active_streams[run_ids[1]]

        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_ids[0],
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "Hello 0"}]},
            },
        })

        ctx0.on_text_chunk.assert_called_once_with("Hello 0")
        ctx1.on_text_chunk.assert_not_called()

    @pytest.mark.asyncio
    async def test_streams_independent_state(self):
        """Each stream maintains independent state."""
        client = MagicMock()
        client.request = AsyncMock(return_value={"status": "accepted"})
        adapter = OpenClawAdapter(client)

        callbacks1 = {
            "on_stream_start": AsyncMock(),
            "on_text_chunk": AsyncMock(),
            "on_stream_end": AsyncMock(),
            "on_error": AsyncMock(),
        }
        callbacks2 = {
            "on_stream_start": AsyncMock(),
            "on_text_chunk": AsyncMock(),
            "on_stream_end": AsyncMock(),
            "on_error": AsyncMock(),
        }

        run_id1 = await adapter.send_message(
            user_id=1,
            session_id="session-1",
            session_key="openclaw:session-1",
            message="M1",
            **callbacks1,
        )
        run_id2 = await adapter.send_message(
            user_id=2,
            session_id="session-2",
            session_key="openclaw:session-2",
            message="M2",
            **callbacks2,
        )

        # Stream 1 gets multiple deltas
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id1,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "A"}]},
            },
        })
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id1,
                "state": "delta",
                "seq": 2,
                "message": {"content": [{"type": "text", "text": "AB"}]},
            },
        })

        # Stream 2 gets one delta
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id2,
                "state": "delta",
                "seq": 1,
                "message": {"content": [{"type": "text", "text": "X"}]},
            },
        })

        # Verify independent text buffers
        assert adapter._active_streams[run_id1].text_buffer == "AB"
        assert adapter._active_streams[run_id2].text_buffer == "X"

        # Verify independent seq tracking
        assert adapter._active_streams[run_id1].seq == 2
        assert adapter._active_streams[run_id2].seq == 1

        # Verify callbacks called correctly
        assert callbacks1["on_text_chunk"].call_count == 2
        assert callbacks2["on_text_chunk"].call_count == 1


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_crash(self):
        """Exception in callback doesn't crash adapter."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        failing_callback = AsyncMock(side_effect=ValueError("Callback failed"))

        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=failing_callback,
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )

        # Should raise since we're not catching callback exceptions
        with pytest.raises(ValueError, match="Callback failed"):
            await adapter.handle_event({
                "event": "chat",
                "payload": {
                    "runId": run_id,
                    "state": "delta",
                    "seq": 1,
                    "message": {"content": [{"type": "text", "text": "Hello"}]},
                },
            })

    @pytest.mark.asyncio
    async def test_handles_missing_message_content(self):
        """Handles events with missing message content."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
            on_stream_start=AsyncMock(),
            on_text_chunk=AsyncMock(),
            on_stream_end=AsyncMock(),
            on_error=AsyncMock(),
        )

        # Delta with no message
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "delta",
                "seq": 1,
            },
        })

        ctx = adapter._active_streams[run_id]
        ctx.on_stream_start.assert_not_called()
        ctx.on_text_chunk.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_unknown_state(self):
        """Unknown state is logged but doesn't crash."""
        client = MagicMock()
        adapter = OpenClawAdapter(client)

        run_id = "test-run-id-12345678"
        adapter._active_streams[run_id] = StreamContext(
            user_id=1,
            session_id="session-1",
            run_id=run_id,
            session_key="openclaw:session-1",
        )

        # Should not raise
        await adapter.handle_event({
            "event": "chat",
            "payload": {
                "runId": run_id,
                "state": "unknown_state",
            },
        })

        # Stream still exists
        assert run_id in adapter.get_active_run_ids()
