"""Proactive agent configuration.

Character routing (Claude Code vs standard) is now determined by frontend settings.
See characters.py for deprecation notes.

Configuration for deep research, rate limiting, and internal API auth.
"""

from config.proactive_agent.defaults import (
    API_VERSION,
    DEFAULT_CHARACTER_NAME,
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_REASONING_EFFORT,
    DEFAULT_RESEARCH_MODEL,
    ESTIMATED_RESEARCH_TIME_SECONDS,
    INTERNAL_API_KEY,
    MAX_CONCURRENT_JOBS_PER_USER,
    POLLER_STREAM_QUEUE_SIZE,
    POLLER_STREAM_QUEUE_TIMEOUT,
    RESEARCH_RESULTS_DIR,
)

__all__ = [
    # Deep research
    "RESEARCH_RESULTS_DIR",
    "DEFAULT_PRIMARY_MODEL",
    "DEFAULT_RESEARCH_MODEL",
    "DEFAULT_REASONING_EFFORT",
    "ESTIMATED_RESEARCH_TIME_SECONDS",
    # Rate limiting
    "MAX_CONCURRENT_JOBS_PER_USER",
    # Auth
    "INTERNAL_API_KEY",
    # Character
    "DEFAULT_CHARACTER_NAME",
    "API_VERSION",
    # Poller stream
    "POLLER_STREAM_QUEUE_SIZE",
    "POLLER_STREAM_QUEUE_TIMEOUT",
]
