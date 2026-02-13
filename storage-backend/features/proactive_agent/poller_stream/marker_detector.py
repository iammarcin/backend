"""Detector for extracting special markers from tool result content."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MarkerType(Enum):
    CHART = "chart"
    RESEARCH = "research"
    SCENE = "scene"
    COMPONENT_UPDATE = "component_update"


@dataclass
class DetectedMarker:
    type: MarkerType
    data: dict[str, Any]
    raw_json: str


@dataclass
class MarkerResult:
    markers: list[DetectedMarker]
    cleaned_content: str


class MarkerDetector:
    """Detects and extracts special markers from tool result content."""

    CHART_START, CHART_END = "[SHERLOCK_CHART:v1]", "[/SHERLOCK_CHART]"
    RESEARCH_START, RESEARCH_END = "[SHERLOCK_RESEARCH:v1]", "[/SHERLOCK_RESEARCH]"
    SCENE_START, SCENE_END = "[SHERLOCK_SCENE:v1]", "[/SHERLOCK_SCENE]"
    COMPONENT_UPDATE_START = "[SHERLOCK_COMPONENT_UPDATE:v1]"
    COMPONENT_UPDATE_END = "[/SHERLOCK_COMPONENT_UPDATE]"

    def detect(self, content: str) -> MarkerResult:
        """Detect all markers in content and return cleaned content."""
        if not content:
            return MarkerResult(markers=[], cleaned_content="")
        markers: list[DetectedMarker] = []
        cleaned = content
        for start, end, mtype in [
            (self.CHART_START, self.CHART_END, MarkerType.CHART),
            (self.RESEARCH_START, self.RESEARCH_END, MarkerType.RESEARCH),
            (self.SCENE_START, self.SCENE_END, MarkerType.SCENE),
            (self.COMPONENT_UPDATE_START, self.COMPONENT_UPDATE_END, MarkerType.COMPONENT_UPDATE),
        ]:
            markers.extend(self._extract_markers(cleaned, start, end, mtype))
            cleaned = self._remove_markers(cleaned, start, end)
        return MarkerResult(markers=markers, cleaned_content=cleaned)

    def has_markers(self, content: str) -> bool:
        """Quick check if content might contain markers."""
        return (
            self.CHART_START in content
            or self.RESEARCH_START in content
            or self.SCENE_START in content
            or self.COMPONENT_UPDATE_START in content
        )

    def _extract_markers(
        self, content: str, start_tag: str, end_tag: str, marker_type: MarkerType
    ) -> list[DetectedMarker]:
        markers, pos = [], 0
        while True:
            start = content.find(start_tag, pos)
            if start == -1:
                break
            end = content.find(end_tag, start + len(start_tag))
            if end == -1:
                break
            raw_json = content[start + len(start_tag):end].strip()
            try:
                markers.append(DetectedMarker(marker_type, json.loads(raw_json), raw_json))
            except json.JSONDecodeError:
                pass
            pos = end + len(end_tag)
        return markers

    def _remove_markers(self, content: str, start_tag: str, end_tag: str) -> str:
        result = content
        while True:
            start = result.find(start_tag)
            if start == -1:
                break
            end = result.find(end_tag, start)
            if end == -1:
                break
            result = result[:start] + result[end + len(end_tag):]
        return result
