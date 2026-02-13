"""Streaming adapter and job tracking for proactive agent deep research.

Provides:
- ProactiveStreamingAdapter: Collects text, suppresses WebSocket streaming for background research
- Job tracking utilities: Rate limiting concurrent jobs per user
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from config.proactive_agent import MAX_CONCURRENT_JOBS_PER_USER
from core.connections import get_proactive_registry

_active_jobs: Dict[int, set] = {}  # user_id -> set of job_ids


class ProactiveStreamingAdapter:
    """Adapter for background deep research - collects text, suppresses WebSocket streaming.

    Unlike normal chat streaming, background research should NOT stream text to WebSocket.
    We only collect text for file writing and push status events (not content).
    """

    # Event types to suppress (don't push to WebSocket during background research)
    _SUPPRESS_TYPES = {"text_chunk", "thinking_chunk", "text_completed", "tts_not_requested"}

    def __init__(self, user_id: int, session_id: str) -> None:
        self._user_id = user_id
        self._session_id = session_id
        self._registry = get_proactive_registry()
        self._collected_chunks: List[str] = []

    async def send_to_queues(self, message: Dict[str, Any]) -> None:
        """Intercept streaming messages - collect text, suppress WebSocket noise."""
        msg_type = message.get("type", "")

        # Don't push text to WebSocket - it's background research
        # Text collection happens via collect_chunk to mirror StreamingManager behavior.
        if msg_type == "text_chunk":
            return

        # Suppress other streaming noise (reasoning, completion signals)
        if msg_type in self._SUPPRESS_TYPES:
            return

        # Push status events (deepResearch*, error, etc.) to WebSocket
        message_with_session = {**message, "session_id": self._session_id}
        await self._registry.push_to_user(self._user_id, message_with_session)

    def collect_chunk(self, chunk: str, chunk_type: str = "text") -> None:
        """Collect text chunks for final aggregation."""
        if chunk_type == "text":
            self._collected_chunks.append(chunk)

    def get_collected_text(self) -> str:
        """Return all collected text chunks."""
        return "".join(self._collected_chunks)


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to a URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:max_length]


def can_start_job(user_id: int) -> bool:
    """Check if user can start another job."""
    return len(_active_jobs.get(user_id, set())) < MAX_CONCURRENT_JOBS_PER_USER


def register_job(user_id: int, job_id: str) -> None:
    """Register a new active job for user."""
    if user_id not in _active_jobs:
        _active_jobs[user_id] = set()
    _active_jobs[user_id].add(job_id)


def unregister_job(user_id: int, job_id: str) -> None:
    """Unregister a completed job."""
    if user_id in _active_jobs:
        _active_jobs[user_id].discard(job_id)
        if not _active_jobs[user_id]:
            del _active_jobs[user_id]


# Expose _active_jobs for testing
def get_active_jobs() -> Dict[int, set]:
    """Get reference to active jobs dict (for testing)."""
    return _active_jobs


__all__ = [
    "ProactiveStreamingAdapter",
    "MAX_CONCURRENT_JOBS_PER_USER",
    "slugify",
    "can_start_job",
    "register_job",
    "unregister_job",
    "get_active_jobs",
]
