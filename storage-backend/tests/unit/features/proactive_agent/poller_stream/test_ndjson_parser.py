"""Tests for NDJSONLineParser."""

import json

import pytest

from features.proactive_agent.poller_stream.ndjson_parser import (
    EventType,
    NDJSONLineParser,
    ParsedEvent,
)


class TestNDJSONLineParser:
    """Tests for NDJSONLineParser following M1.4 specification."""

    # ========== System Events ==========

    def test_system_event_extracts_session_id(self):
        """System event extracts claude session ID."""
        parser = NDJSONLineParser()
        line = json.dumps({"type": "system", "session_id": "abc-123"})

        events = parser.process_line(line)

        assert len(events) == 1
        assert events[0].type == EventType.SESSION_ID
        assert events[0].data["session_id"] == "abc-123"
        assert parser.get_claude_session_id() == "abc-123"

    # ========== Content Streaming ==========

    def test_content_block_delta_text(self):
        """Content block delta with text produces TEXT_CHUNK."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"text": "Hello world"}
            }
        })

        events = parser.process_line(line)

        assert len(events) == 1
        assert events[0].type == EventType.TEXT_CHUNK
        assert events[0].data["content"] == "Hello world"

    def test_thinking_detection(self):
        """Thinking tags produce THINKING_CHUNK events."""
        parser = NDJSONLineParser()

        # Send thinking block
        events1 = parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "<thinking>Deep"}}
        }))
        events2 = parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": " thought</thinking>Done"}}
        }))

        # Should have thinking chunks and text chunk
        all_events = events1 + events2
        thinking_events = [e for e in all_events if e.type == EventType.THINKING_CHUNK]
        text_events = [e for e in all_events if e.type == EventType.TEXT_CHUNK]

        assert len(thinking_events) >= 1
        assert len(text_events) >= 1

    # ========== Tool Events ==========

    def test_tool_use_detected_from_content_block_start(self):
        """Tool use in content_block_start produces TOOL_USE_DETECTED."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "stream_event",
            "event": {
                "type": "content_block_start",
                "content_block": {
                    "type": "tool_use",
                    "id": "toolu_123",
                    "name": "Bash"
                }
            }
        })

        events = parser.process_line(line)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_USE_DETECTED
        assert events[0].data["tool_use_id"] == "toolu_123"
        assert events[0].data["name"] == "Bash"

    def test_tool_start_from_assistant_message(self):
        """Assistant message with tool_use produces TOOL_START."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_456",
                    "name": "Bash",
                    "input": {"command": "ls -la"}
                }]
            }
        })

        events = parser.process_line(line)

        assert len(events) == 1
        assert events[0].type == EventType.TOOL_START
        assert events[0].data["tool_use_id"] == "toolu_456"
        assert events[0].data["name"] == "Bash"
        assert events[0].data["input"] == {"command": "ls -la"}

    def test_tool_result_from_user_message(self):
        """User message with tool_result produces TOOL_RESULT."""
        parser = NDJSONLineParser()

        # First register the tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_789",
                    "name": "Bash",
                    "input": {"command": "echo hello"}
                }]
            }
        }))

        # Now process result
        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_789",
                    "content": "hello"
                }]
            }
        }))

        result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert len(result_events) == 1
        assert result_events[0].data["name"] == "Bash"
        assert result_events[0].data["content"] == "hello"

    # ========== Marker Detection ==========

    def test_chart_marker_in_tool_result(self):
        """Chart marker in tool result produces CHART_DETECTED."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_chart",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        # Tool result with chart marker
        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "line", "title": "Test"}
[/SHERLOCK_CHART]
Output text'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_chart",
                    "content": content
                }]
            }
        }))

        chart_events = [e for e in events if e.type == EventType.CHART_DETECTED]
        assert len(chart_events) == 1
        assert chart_events[0].data["chart_data"]["chart_type"] == "line"

        result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert "Output text" in result_events[0].data["cleaned_content"]
        assert "[SHERLOCK_CHART" not in result_events[0].data["cleaned_content"]

    def test_read_tool_skips_marker_detection(self):
        """Read tool results don't scan for markers."""
        parser = NDJSONLineParser()

        # Register Read tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_read",
                    "name": "Read",
                    "input": {"file_path": "/tmp/test.md"}
                }]
            }
        }))

        # Tool result with chart marker in file content
        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "line"}
[/SHERLOCK_CHART]'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_read",
                    "content": content
                }]
            }
        }))

        # Should NOT detect chart (it's from a file read)
        chart_events = [e for e in events if e.type == EventType.CHART_DETECTED]
        assert len(chart_events) == 0

        # Content should be unchanged
        result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert "[SHERLOCK_CHART:v1]" in result_events[0].data["content"]

    # ========== Result Event ==========

    def test_result_event(self):
        """Result event produces SESSION_ID and STREAM_COMPLETE."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "result",
            "session_id": "final-session-id"
        })

        events = parser.process_line(line)

        types = {e.type for e in events}
        assert EventType.SESSION_ID in types
        assert EventType.STREAM_COMPLETE in types

    # ========== Error Handling ==========

    def test_invalid_json_line(self):
        """Invalid JSON line produces PARSE_ERROR."""
        parser = NDJSONLineParser()
        events = parser.process_line("not valid json {")

        assert len(events) == 1
        assert events[0].type == EventType.PARSE_ERROR

    def test_empty_line(self):
        """Empty line produces no events."""
        parser = NDJSONLineParser()
        events = parser.process_line("")
        assert events == []

    def test_whitespace_line(self):
        """Whitespace-only line produces no events."""
        parser = NDJSONLineParser()
        events = parser.process_line("   \n\t  ")
        assert events == []

    # ========== Finalization ==========

    def test_thinking_emits_immediately_not_at_finalize(self):
        """Thinking content streams immediately, not at finalize.

        M6.1 Bug Fix: Previously, thinking content was buffered until finalize().
        Now it emits immediately during process_line() for real-time streaming.
        """
        parser = NDJSONLineParser()

        # Send incomplete thinking (no closing tag yet)
        events = parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "<thinking>Incomplete"}}
        }))

        # Should emit thinking chunk immediately, not buffer
        thinking_events = [e for e in events if e.type == EventType.THINKING_CHUNK]
        assert len(thinking_events) == 1
        assert thinking_events[0].data["content"] == "Incomplete"

        # Finalize should return nothing (content already emitted)
        final_events = parser.finalize()
        assert final_events == []

    def test_finalize_flushes_partial_tag(self):
        """Finalize flushes buffered partial closing tags."""
        parser = NDJSONLineParser()

        # Send thinking content ending with partial closing tag
        parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "<thinking>Content</think"}}
        }))

        events = parser.finalize()

        # Should flush the partial tag that was buffered
        thinking_events = [e for e in events if e.type == EventType.THINKING_CHUNK]
        assert len(thinking_events) == 1
        assert thinking_events[0].data["content"] == "</think"

    def test_accumulated_text(self):
        """get_accumulated_text returns all text with tags."""
        parser = NDJSONLineParser()
        parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "Hello <thinking>thought</thinking> world"}}
        }))

        text = parser.get_accumulated_text()
        assert "<thinking>" in text
        assert "thought" in text
        assert "Hello" in text

    def test_clean_text(self):
        """get_clean_text returns text without thinking."""
        parser = NDJSONLineParser()
        parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "Hello <thinking>thought</thinking> world"}}
        }))

        text = parser.get_clean_text()
        assert "<thinking>" not in text
        assert "thought" not in text
        assert "Hello" in text
        assert "world" in text

    # ========== Message Stop ==========

    def test_message_stop_event(self):
        """message_stop produces MESSAGE_STOP event."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "stream_event",
            "event": {"type": "message_stop"}
        })

        events = parser.process_line(line)

        assert len(events) == 1
        assert events[0].type == EventType.MESSAGE_STOP

    # ========== Research Marker ==========

    def test_research_marker_in_tool_result(self):
        """Research marker in tool result produces RESEARCH_DETECTED."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_research",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        # Tool result with research marker
        content = '''[SHERLOCK_RESEARCH:v1]
{"topic": "AI trends", "findings": ["item1"]}
[/SHERLOCK_RESEARCH]
Summary here'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_research",
                    "content": content
                }]
            }
        }))

        research_events = [e for e in events if e.type == EventType.RESEARCH_DETECTED]
        assert len(research_events) == 1
        assert research_events[0].data["research_data"]["topic"] == "AI trends"

    # ========== Reset ==========

    def test_reset_clears_state(self):
        """reset() clears all parser state."""
        parser = NDJSONLineParser()

        # Build up state
        parser.process_line(json.dumps({"type": "system", "session_id": "old-id"}))
        parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "Hello"}}
        }))

        # Reset
        parser.reset()

        # Verify cleared
        assert parser.get_claude_session_id() is None
        assert parser.get_accumulated_text() == ""
        assert parser.get_clean_text() == ""

    # ========== Edge Cases for 100% Coverage ==========

    def test_system_without_session_id(self):
        """System event without session_id produces no events."""
        parser = NDJSONLineParser()
        events = parser.process_line(json.dumps({"type": "system"}))
        assert events == []

    def test_content_block_delta_empty_text(self):
        """Content block delta with empty text produces no events."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": ""}}
        })
        events = parser.process_line(line)
        assert events == []

    def test_unknown_stream_event_type(self):
        """Unknown stream event type produces no events."""
        parser = NDJSONLineParser()
        line = json.dumps({
            "type": "stream_event",
            "event": {"type": "unknown_event_type"}
        })
        events = parser.process_line(line)
        assert events == []

    def test_get_accumulated_thinking(self):
        """get_accumulated_thinking returns thinking content."""
        parser = NDJSONLineParser()
        parser.process_line(json.dumps({
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"text": "<thinking>deep thought</thinking>"}}
        }))
        thinking = parser.get_accumulated_thinking()
        assert "deep thought" in thinking

    # ========== Scene Marker ==========

    def test_scene_marker_in_tool_result(self):
        """Scene marker in tool result produces SCENE_DETECTED."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_scene",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        # Tool result with scene marker
        scene_json = {"scene_id": "test-scene", "components": [{"type": "text", "id": "t1", "content": "Hello"}]}
        content = f'''[SHERLOCK_SCENE:v1]
{json.dumps(scene_json)}
[/SHERLOCK_SCENE]
Output text'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_scene",
                    "content": content
                }]
            }
        }))

        scene_events = [e for e in events if e.type == EventType.SCENE_DETECTED]
        assert len(scene_events) == 1
        assert scene_events[0].data["scene_data"]["scene_id"] == "test-scene"
        assert scene_events[0].data["scene_data"]["components"][0]["type"] == "text"

        result_events = [e for e in events if e.type == EventType.TOOL_RESULT]
        assert "Output text" in result_events[0].data["cleaned_content"]
        assert "[SHERLOCK_SCENE" not in result_events[0].data["cleaned_content"]

    def test_scene_marker_preserves_complex_structure(self):
        """Scene marker with timeline and grid layout is parsed correctly."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_complex",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        # Complex scene with timeline and grid
        scene_json = {
            "scene_id": "complex-scene",
            "layout": "grid",
            "grid": {"columns": 2, "rows": 2, "gap": 16},
            "timeline": {
                "master": "audio-1",
                "cues": [
                    {"at": 0, "show": ["intro"]},
                    {"at": 5, "show": ["chart"], "hide": ["intro"]}
                ]
            },
            "components": [
                {"type": "text", "id": "intro", "content": "Welcome", "style": "heading"},
                {"type": "chart", "id": "chart", "chart_id": "chart-123"},
                {"type": "audio_chunk", "id": "audio-1", "src": "tts://auto", "timeline_master": True}
            ]
        }

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_complex",
                    "content": f"[SHERLOCK_SCENE:v1]\n{json.dumps(scene_json)}\n[/SHERLOCK_SCENE]"
                }]
            }
        }))

        scene_events = [e for e in events if e.type == EventType.SCENE_DETECTED]
        assert len(scene_events) == 1
        data = scene_events[0].data["scene_data"]
        assert data["layout"] == "grid"
        assert data["grid"]["columns"] == 2
        assert len(data["timeline"]["cues"]) == 2
        assert len(data["components"]) == 3

    def test_scene_and_chart_markers_together(self):
        """Scene marker alongside chart marker both detected."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_both",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "line", "title": "Chart"}
[/SHERLOCK_CHART]
[SHERLOCK_SCENE:v1]
{"scene_id": "scene-1", "components": []}
[/SHERLOCK_SCENE]'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_both",
                    "content": content
                }]
            }
        }))

        chart_events = [e for e in events if e.type == EventType.CHART_DETECTED]
        scene_events = [e for e in events if e.type == EventType.SCENE_DETECTED]
        assert len(chart_events) == 1
        assert len(scene_events) == 1

    # ========== Component Update Marker ==========

    def test_component_update_marker_in_tool_result(self):
        """Component update marker in tool result produces COMPONENT_UPDATE_DETECTED."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_update",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        # Tool result with component update marker
        content = '''[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "answer", "content": "Hello world", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_update",
                    "content": content
                }]
            }
        }))

        update_events = [e for e in events if e.type == EventType.COMPONENT_UPDATE_DETECTED]
        assert len(update_events) == 1
        assert update_events[0].data["update_data"]["component_id"] == "answer"
        assert update_events[0].data["update_data"]["content"] == "Hello world"
        assert update_events[0].data["update_data"]["append"] is True

    def test_multiple_component_updates_in_sequence(self):
        """Multiple component update markers detected in sequence."""
        parser = NDJSONLineParser()

        # Register tool
        parser.process_line(json.dumps({
            "type": "assistant",
            "message": {
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_multi",
                    "name": "Bash",
                    "input": {}
                }]
            }
        }))

        content = '''[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "text", "content": "Part 1 ", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]
[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "text", "content": "Part 2", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]'''

        events = parser.process_line(json.dumps({
            "type": "user",
            "message": {
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_multi",
                    "content": content
                }]
            }
        }))

        update_events = [e for e in events if e.type == EventType.COMPONENT_UPDATE_DETECTED]
        assert len(update_events) == 2
        assert update_events[0].data["update_data"]["content"] == "Part 1 "
        assert update_events[1].data["update_data"]["content"] == "Part 2"
