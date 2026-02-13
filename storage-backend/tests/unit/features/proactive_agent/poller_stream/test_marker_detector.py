import json

import pytest
from features.proactive_agent.poller_stream.marker_detector import (
    MarkerDetector, MarkerType, DetectedMarker, MarkerResult
)


class TestMarkerDetector:

    def test_no_markers(self):
        """Content without markers returns empty list."""
        detector = MarkerDetector()
        result = detector.detect("Just regular text output")

        assert result.markers == []
        assert result.cleaned_content == "Just regular text output"

    def test_chart_marker(self):
        """Detect chart marker with valid JSON."""
        detector = MarkerDetector()
        content = '''Some output
[SHERLOCK_CHART:v1]
{"chart_type": "line", "title": "Test"}
[/SHERLOCK_CHART]
More output'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].type == MarkerType.CHART
        assert result.markers[0].data == {"chart_type": "line", "title": "Test"}
        assert "[SHERLOCK_CHART" not in result.cleaned_content
        assert "Some output" in result.cleaned_content
        assert "More output" in result.cleaned_content

    def test_research_marker(self):
        """Detect research marker with valid JSON."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_RESEARCH:v1]
{"query": "What is the weather?"}
[/SHERLOCK_RESEARCH]'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].type == MarkerType.RESEARCH
        assert result.markers[0].data == {"query": "What is the weather?"}

    def test_multiple_chart_markers(self):
        """Detect multiple charts in same content."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "line", "id": 1}
[/SHERLOCK_CHART]
Middle text
[SHERLOCK_CHART:v1]
{"chart_type": "bar", "id": 2}
[/SHERLOCK_CHART]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        assert result.markers[0].data["id"] == 1
        assert result.markers[1].data["id"] == 2
        assert "Middle text" in result.cleaned_content

    def test_mixed_markers(self):
        """Detect both chart and research markers."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "pie"}
[/SHERLOCK_CHART]
[SHERLOCK_RESEARCH:v1]
{"query": "test"}
[/SHERLOCK_RESEARCH]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        types = {m.type for m in result.markers}
        assert types == {MarkerType.CHART, MarkerType.RESEARCH}

    def test_invalid_json_skipped(self):
        """Invalid JSON in marker is skipped, not crashed."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{invalid json here}
[/SHERLOCK_CHART]
Valid text after'''

        result = detector.detect(content)

        assert len(result.markers) == 0
        assert "Valid text after" in result.cleaned_content

    def test_unclosed_marker_ignored(self):
        """Unclosed marker is left as-is."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{"data": "test"}
No closing tag'''

        result = detector.detect(content)

        assert len(result.markers) == 0
        # Content unchanged since marker not properly closed
        assert "[SHERLOCK_CHART:v1]" in result.cleaned_content

    def test_has_markers_quick_check(self):
        """has_markers() provides quick check."""
        detector = MarkerDetector()

        assert detector.has_markers("[SHERLOCK_CHART:v1]") is True
        assert detector.has_markers("[SHERLOCK_RESEARCH:v1]") is True
        assert detector.has_markers("regular text") is False

    def test_json_with_whitespace(self):
        """JSON with various whitespace is parsed correctly."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]

    {
        "chart_type": "line",
        "data": {
            "labels": ["a", "b"]
        }
    }

[/SHERLOCK_CHART]'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].data["chart_type"] == "line"
        assert result.markers[0].data["data"]["labels"] == ["a", "b"]

    def test_raw_json_preserved(self):
        """raw_json field contains original JSON string."""
        detector = MarkerDetector()
        content = '[SHERLOCK_CHART:v1]{"x": 1}[/SHERLOCK_CHART]'

        result = detector.detect(content)

        assert result.markers[0].raw_json == '{"x": 1}'

    def test_empty_content(self):
        """Empty content returns empty result."""
        detector = MarkerDetector()
        result = detector.detect("")

        assert result.markers == []
        assert result.cleaned_content == ""

    def test_marker_at_boundaries(self):
        """Markers at start/end of content work."""
        detector = MarkerDetector()
        content = '[SHERLOCK_CHART:v1]{"x":1}[/SHERLOCK_CHART]'

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.cleaned_content == ""

    def test_complex_chart_json(self):
        """Complex nested chart JSON is parsed."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{
    "chart_type": "line",
    "title": "Accuracy Over Time",
    "data": {
        "datasets": [
            {"label": "Accuracy", "data": [92, 87, 79, 88, 95, 97, 98, 99]}
        ]
    },
    "chart_id": "accuracy_chart"
}
[/SHERLOCK_CHART]'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        data = result.markers[0].data
        assert data["chart_type"] == "line"
        assert data["chart_id"] == "accuracy_chart"
        assert len(data["data"]["datasets"][0]["data"]) == 8

    def test_detect_scene_marker(self):
        """Scene marker is detected and parsed correctly."""
        detector = MarkerDetector()
        content = '''Some text
[SHERLOCK_SCENE:v1]
{"scene_id": "test", "components": []}
[/SHERLOCK_SCENE]
More text'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].type == MarkerType.SCENE
        assert result.markers[0].data["scene_id"] == "test"
        assert "[SHERLOCK_SCENE" not in result.cleaned_content
        assert "Some text" in result.cleaned_content
        assert "More text" in result.cleaned_content

    def test_detect_multiple_scene_markers(self):
        """Multiple scene markers in same content."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_SCENE:v1]
{"scene_id": "scene1", "components": []}
[/SHERLOCK_SCENE]
Between
[SHERLOCK_SCENE:v1]
{"scene_id": "scene2", "components": []}
[/SHERLOCK_SCENE]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        assert result.markers[0].data["scene_id"] == "scene1"
        assert result.markers[1].data["scene_id"] == "scene2"

    def test_detect_scene_with_chart(self):
        """Scene marker alongside chart marker."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_CHART:v1]
{"chart_type": "line", "title": "Test"}
[/SHERLOCK_CHART]
[SHERLOCK_SCENE:v1]
{"scene_id": "test", "components": []}
[/SHERLOCK_SCENE]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        marker_types = {m.type for m in result.markers}
        assert MarkerType.CHART in marker_types
        assert MarkerType.SCENE in marker_types

    def test_detect_scene_invalid_json(self):
        """Invalid JSON in scene marker is skipped gracefully."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_SCENE:v1]
{invalid json}
[/SHERLOCK_SCENE]'''

        result = detector.detect(content)

        assert len(result.markers) == 0

    def test_detect_scene_preserves_complex_structure(self):
        """Scene with nested components is parsed correctly."""
        detector = MarkerDetector()
        scene_json = {
            "scene_id": "complex",
            "layout": "grid",
            "grid": {"columns": 2, "rows": 2},
            "timeline": {
                "master": "audio",
                "cues": [{"at": 0, "show": ["intro"]}]
            },
            "components": [
                {"type": "text", "id": "intro", "content": "Hello"},
                {"type": "audio_chunk", "id": "audio", "src": "test.mp3"}
            ]
        }
        content = f'''[SHERLOCK_SCENE:v1]
{json.dumps(scene_json)}
[/SHERLOCK_SCENE]'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].data == scene_json

    def test_has_markers_detects_scene(self):
        """has_markers() detects scene markers."""
        detector = MarkerDetector()

        assert detector.has_markers("[SHERLOCK_SCENE:v1]") is True
        assert detector.has_markers("no markers here") is False

    def test_detect_component_update_marker(self):
        """Component update marker is detected correctly."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "answer", "content": "Hello", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]'''

        result = detector.detect(content)

        assert len(result.markers) == 1
        assert result.markers[0].type == MarkerType.COMPONENT_UPDATE
        assert result.markers[0].data["component_id"] == "answer"
        assert result.markers[0].data["content"] == "Hello"
        assert result.markers[0].data["append"] is True

    def test_detect_multiple_component_update_markers(self):
        """Multiple component update markers in sequence."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "answer", "content": "Hello ", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]
[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "answer", "content": "world!", "append": true}
[/SHERLOCK_COMPONENT_UPDATE]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        assert result.markers[0].data["content"] == "Hello "
        assert result.markers[1].data["content"] == "world!"

    def test_has_markers_detects_component_update(self):
        """has_markers() detects component update markers."""
        detector = MarkerDetector()

        assert detector.has_markers("[SHERLOCK_COMPONENT_UPDATE:v1]") is True

    def test_detect_component_update_with_scene(self):
        """Component update alongside scene marker."""
        detector = MarkerDetector()
        content = '''[SHERLOCK_SCENE:v1]
{"scene_id": "s1", "components": []}
[/SHERLOCK_SCENE]
[SHERLOCK_COMPONENT_UPDATE:v1]
{"component_id": "t1", "content": "Updated", "append": false}
[/SHERLOCK_COMPONENT_UPDATE]'''

        result = detector.detect(content)

        assert len(result.markers) == 2
        marker_types = {m.type for m in result.markers}
        assert MarkerType.SCENE in marker_types
        assert MarkerType.COMPONENT_UPDATE in marker_types
