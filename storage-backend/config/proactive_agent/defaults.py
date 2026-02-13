"""Proactive agent configuration defaults.

Centralizes all configurable parameters for proactive agent features including:
- Deep research settings
- Job rate limiting
- Internal API authentication
"""

from __future__ import annotations

import os
from pathlib import Path

from config.environment import IS_PRODUCTION, IS_TEST

# =============================================================================
# Deep Research Configuration
# =============================================================================

# Directory for research results (mounted as /storage in container)
RESEARCH_RESULTS_DIR = Path(
    os.getenv("PROACTIVE_AGENT_RESEARCH_RESULTS_DIR", "/storage/research-results")
)

# Default models for deep research workflow
DEFAULT_PRIMARY_MODEL = os.getenv("PROACTIVE_AGENT_PRIMARY_MODEL", "gpt-4o")
DEFAULT_RESEARCH_MODEL = os.getenv("PROACTIVE_AGENT_RESEARCH_MODEL", "perplexity")

# Environment-based reasoning effort: prod=medium, non-prod=low
# This controls the depth and thoroughness of Perplexity research
_DEFAULT_EFFORT_PROD = "medium"
_DEFAULT_EFFORT_NON_PROD = "low"
DEFAULT_REASONING_EFFORT = _DEFAULT_EFFORT_PROD if IS_PRODUCTION else _DEFAULT_EFFORT_NON_PROD

# Estimated time for research completion (seconds)
ESTIMATED_RESEARCH_TIME_SECONDS = int(
    os.getenv("PROACTIVE_AGENT_ESTIMATED_RESEARCH_TIME", "180")
)

# =============================================================================
# Job Rate Limiting
# =============================================================================

# Maximum concurrent deep research jobs per user
MAX_CONCURRENT_JOBS_PER_USER = int(
    os.getenv("PROACTIVE_AGENT_MAX_CONCURRENT_JOBS", "3")
)

# =============================================================================
# Internal API Authentication
# =============================================================================

# API key for server-to-server communication (poller -> backend)
# Required in non-test environments - no default value for security
# In test environments, use a placeholder to allow auth tests to work
INTERNAL_API_KEY = os.getenv("PROACTIVE_AGENT_INTERNAL_API_KEY")
if not INTERNAL_API_KEY:
    if IS_TEST:
        INTERNAL_API_KEY = "test-placeholder-key-not-for-production"
    else:
        raise ValueError("PROACTIVE_AGENT_INTERNAL_API_KEY environment variable is required")

# =============================================================================
# Default Character Settings
# =============================================================================

# Default AI character name when not specified
DEFAULT_CHARACTER_NAME = os.getenv("PROACTIVE_AGENT_DEFAULT_CHARACTER", "sherlock")

# API version for health endpoint
API_VERSION = "1.0.0"

# =============================================================================
# Poller Stream Configuration (M2.3 Backpressure)
# =============================================================================

# Maximum queue size for buffering NDJSON lines from poller
POLLER_STREAM_QUEUE_SIZE = int(
    os.getenv("POLLER_STREAM_QUEUE_SIZE", "100")
)

# Timeout (seconds) for queue put operation before closing with backpressure error
POLLER_STREAM_QUEUE_TIMEOUT = int(
    os.getenv("POLLER_STREAM_QUEUE_TIMEOUT", "30")
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
