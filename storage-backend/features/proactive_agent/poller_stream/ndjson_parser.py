"""NDJSON line parser for Claude's streaming output."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .marker_detector import MarkerDetector, MarkerType
from .thinking_parser import ChunkType, ThinkingParser
from .tool_tracker import ToolTracker


class EventType(Enum):
    SESSION_ID = "session_id"
    THINKING_CHUNK = "thinking_chunk"
    TEXT_CHUNK = "text_chunk"
    TOOL_USE_DETECTED = "tool_use_detected"
    TOOL_START = "tool_start"
    TOOL_RESULT = "tool_result"
    CHART_DETECTED = "chart_detected"
    RESEARCH_DETECTED = "research_detected"
    SCENE_DETECTED = "scene_detected"
    COMPONENT_UPDATE_DETECTED = "component_update_detected"
    MESSAGE_STOP = "message_stop"
    STREAM_COMPLETE = "stream_complete"
    PARSE_ERROR = "parse_error"


@dataclass
class ParsedEvent:
    type: EventType
    data: dict[str, Any]


class NDJSONLineParser:
    """Parses Claude NDJSON stream lines into structured events."""

    def __init__(self) -> None:
        self._thinking = ThinkingParser()
        self._tools = ToolTracker()
        self._markers = MarkerDetector()
        self._session_id: str | None = None

    def process_line(self, line: str) -> list[ParsedEvent]:
        """Process a single NDJSON line and return events."""
        if not line or not line.strip():
            return []
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return [ParsedEvent(EventType.PARSE_ERROR, {"line": line})]
        msg_type = parsed.get("type", "")
        handlers = {"system": self._system, "stream_event": self._stream_event,
                    "assistant": self._assistant, "user": self._user, "result": self._result}
        return handlers.get(msg_type, lambda _: [])(parsed)

    def _system(self, p: dict) -> list[ParsedEvent]:
        sid = p.get("session_id")
        if sid:
            self._session_id = sid
            return [ParsedEvent(EventType.SESSION_ID, {"session_id": sid})]
        return []

    def _stream_event(self, p: dict) -> list[ParsedEvent]:
        ev = p.get("event", {})
        et = ev.get("type", "")
        if et == "content_block_delta":
            text = ev.get("delta", {}).get("text", "")
            if not text:
                return []
            return [ParsedEvent(EventType.THINKING_CHUNK if c.type == ChunkType.THINKING else EventType.TEXT_CHUNK,
                                {"content": c.content}) for c in self._thinking.process(text)]
        if et == "content_block_start":
            blk = ev.get("content_block", {})
            if blk.get("type") == "tool_use":
                return [ParsedEvent(EventType.TOOL_USE_DETECTED, {"tool_use_id": blk.get("id", ""), "name": blk.get("name", "")})]
        if et == "message_stop":
            return [ParsedEvent(EventType.MESSAGE_STOP, {})]
        return []

    def _assistant(self, p: dict) -> list[ParsedEvent]:
        events = []
        for blk in p.get("message", {}).get("content", []):
            if blk.get("type") == "tool_use":
                tid, name, inp = blk.get("id", ""), blk.get("name", ""), blk.get("input", {})
                self._tools.register_tool(tid, name, inp)
                events.append(ParsedEvent(EventType.TOOL_START, {"tool_use_id": tid, "name": name, "input": inp}))
        return events

    def _user(self, p: dict) -> list[ParsedEvent]:
        events = []
        for blk in p.get("message", {}).get("content", []):
            if blk.get("type") == "tool_result":
                events.extend(self._tool_result(blk))
        return events

    def _tool_result(self, blk: dict) -> list[ParsedEvent]:
        events: list[ParsedEvent] = []
        tid, content = blk.get("tool_use_id", ""), blk.get("content", "")
        info = self._tools.get_tool(tid)
        name, inp = (info.name, info.input) if info else ("unknown", {})
        cleaned = content
        if info and not info.should_skip_markers and self._markers.has_markers(content):
            res = self._markers.detect(content)
            cleaned = res.cleaned_content
            for m in res.markers:
                if m.type == MarkerType.CHART:
                    events.append(ParsedEvent(EventType.CHART_DETECTED, {"chart_data": m.data, "raw_json": m.raw_json}))
                elif m.type == MarkerType.RESEARCH:
                    events.append(ParsedEvent(EventType.RESEARCH_DETECTED, {"research_data": m.data, "raw_json": m.raw_json}))
                elif m.type == MarkerType.SCENE:
                    events.append(ParsedEvent(EventType.SCENE_DETECTED, {"scene_data": m.data, "raw_json": m.raw_json}))
                elif m.type == MarkerType.COMPONENT_UPDATE:
                    events.append(ParsedEvent(EventType.COMPONENT_UPDATE_DETECTED, {"update_data": m.data, "raw_json": m.raw_json}))
        events.append(ParsedEvent(EventType.TOOL_RESULT, {"tool_use_id": tid, "name": name, "input": inp, "content": content, "cleaned_content": cleaned}))
        self._tools.complete_tool(tid)
        return events

    def _result(self, p: dict) -> list[ParsedEvent]:
        events: list[ParsedEvent] = []
        sid = p.get("session_id")
        if sid:
            self._session_id = sid
            events.append(ParsedEvent(EventType.SESSION_ID, {"session_id": sid}))
        events.append(ParsedEvent(EventType.STREAM_COMPLETE, {}))
        return events

    def finalize(self) -> list[ParsedEvent]:
        """Finalize parsing at end of stream. Flushes remaining content."""
        return [ParsedEvent(EventType.THINKING_CHUNK if c.type == ChunkType.THINKING else EventType.TEXT_CHUNK,
                            {"content": c.content}) for c in self._thinking.flush()]

    def get_claude_session_id(self) -> str | None:
        """Get Claude session ID if seen."""
        return self._session_id

    def get_accumulated_text(self) -> str:
        """Get full accumulated text (with thinking tags)."""
        return self._thinking.get_accumulated_text()

    def get_clean_text(self) -> str:
        """Get accumulated text without thinking content."""
        return self._thinking.get_clean_text()

    def get_accumulated_thinking(self) -> str:
        """Get accumulated thinking content."""
        return self._thinking.get_accumulated_thinking()

    def reset(self) -> None:
        """Reset parser for reuse."""
        self._thinking.reset()
        self._tools.clear()
        self._session_id = None
