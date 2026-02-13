"""Compatibility exports for chat history persistence helpers."""

from __future__ import annotations

from .history_persistence_core import persist_workflow_result
from .history_tts_persistence import persist_tts_only_result

__all__ = ["persist_workflow_result", "persist_tts_only_result"]
