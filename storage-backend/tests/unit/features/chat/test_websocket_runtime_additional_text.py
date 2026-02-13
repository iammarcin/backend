"""Tests for WorkflowRuntime.set_additional_text / get_additional_text."""

import asyncio

from features.chat.utils.websocket_runtime import WorkflowRuntime
from core.streaming.manager import StreamingManager


def _make_runtime() -> WorkflowRuntime:
    manager = StreamingManager()
    frontend_queue: asyncio.Queue = asyncio.Queue()
    return WorkflowRuntime(manager=manager, tasks=[], frontend_queue=frontend_queue)


def test_additional_text_default_none():
    runtime = _make_runtime()
    assert runtime.get_additional_text() is None


def test_set_and_get_additional_text():
    runtime = _make_runtime()
    runtime.set_additional_text("Check this link")
    assert runtime.get_additional_text() == "Check this link"


def test_additional_text_overwrite():
    runtime = _make_runtime()
    runtime.set_additional_text("first")
    runtime.set_additional_text("second")
    assert runtime.get_additional_text() == "second"
