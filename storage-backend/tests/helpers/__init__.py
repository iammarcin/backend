"""Test helper utilities for environment and service validation."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import Settings

logger = logging.getLogger(__name__)


def is_semantic_search_available() -> bool:
    """Check if semantic search is properly configured.

    Returns:
        True if OPENAI_API_KEY and semantic_search_enabled are set.
    """
    from core.config import settings

    has_api_key = bool(os.getenv("OPENAI_API_KEY"))
    is_enabled = settings.semantic_search_enabled

    return has_api_key and is_enabled


def is_garmin_db_available() -> bool:
    """Check if Garmin database is configured.

    Returns:
        True if GARMIN_DB_URL environment variable is set.
    """
    from core.config import settings

    if not settings.garmin_enabled:
        return False

    return bool(os.getenv("GARMIN_DB_URL"))


def is_ufc_db_available() -> bool:
    """Check if UFC database is configured.

    Returns:
        True if UFC_DB_URL environment variable is set.
    """
    return bool(os.getenv("UFC_DB_URL"))


def is_sqs_available() -> bool:
    """Check if SQS queue service is configured.

    Returns:
        True if AWS credentials and SQS_QUEUE_URL are set.
    """
    # Check for required AWS credentials
    has_credentials = bool(
        os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    # SQS_QUEUE_URL might be optional depending on implementation
    has_queue_url = bool(os.getenv("SQS_QUEUE_URL"))

    # For now, just check credentials. We'll refine this in M4.
    return has_credentials


def is_openai_available() -> bool:
    """Check if OpenAI API is configured.

    Returns:
        True if OPENAI_API_KEY environment variable is set.
    """
    return bool(os.getenv("OPENAI_API_KEY"))


def is_google_available() -> bool:
    """Check if Google/Gemini API is configured.

    Returns:
        True if GOOGLE_API_KEY environment variable is set.
    """
    return bool(os.getenv("GOOGLE_API_KEY"))


def is_anthropic_available() -> bool:
    """Check if Anthropic API is configured.

    Returns:
        True if ANTHROPIC_API_KEY environment variable is set.
    """
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def get_missing_prerequisites(service: str) -> list[str]:
    """Get list of missing prerequisites for a service.

    Args:
        service: Service name ('semantic_search', 'garmin_db', 'ufc_db', 'sqs')

    Returns:
        List of missing environment variables or configuration items.
    """
    missing = []

    if service == "semantic_search":
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")
        from core.config import settings
        if not settings.semantic_search_enabled:
            missing.append("semantic_search_enabled setting")

    elif service == "garmin_db":
        from core.config import settings

        if not settings.garmin_enabled:
            missing.append("GARMIN_ENABLED=true")
        if not os.getenv("GARMIN_DB_URL"):
            missing.append("GARMIN_DB_URL")

    elif service == "ufc_db":
        if not os.getenv("UFC_DB_URL"):
            missing.append("UFC_DB_URL")

    elif service == "sqs":
        if not os.getenv("AWS_ACCESS_KEY_ID"):
            missing.append("AWS_ACCESS_KEY_ID")
        if not os.getenv("AWS_SECRET_ACCESS_KEY"):
            missing.append("AWS_SECRET_ACCESS_KEY")

    return missing


__all__ = [
    "is_semantic_search_available",
    "is_garmin_db_available",
    "is_ufc_db_available",
    "is_sqs_available",
    "is_openai_available",
    "is_google_available",
    "is_anthropic_available",
    "get_missing_prerequisites",
]
