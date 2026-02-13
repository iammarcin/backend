"""Filtering helpers for chat message queries."""

from __future__ import annotations

import re
from typing import Any

from features.chat.db_models import ChatMessage


def collect_file_candidates(
    message: ChatMessage,
    *,
    file_extension: str | None = None,
    check_image_locations: bool = False,
    exact_filename: str | None = None,
) -> list[str]:
    """Collect candidate files from a message based on filter criteria.

    Args:
        message: ChatMessage to extract files from
        file_extension: Optional extension to filter by (e.g., '.pdf')
        check_image_locations: If True, include image_locations in candidates
        exact_filename: Optional filename to check for in message text

    Returns:
        List of file path strings that match the criteria
    """
    candidates: list[str] = []
    files = message.file_locations or []
    images = message.image_locations or []

    if file_extension:
        extension = file_extension.lower()
        candidates.extend(
            [f for f in files if isinstance(f, str) and f.lower().endswith(extension)]
        )
        if check_image_locations:
            candidates.extend(
                [f for f in images if isinstance(f, str) and f.lower().endswith(extension)]
            )
    else:
        candidates.extend(files)
        if check_image_locations:
            candidates.extend(images)
            # Extract URLs from message text (markdown images and plain URLs)
            if exact_filename and isinstance(message.message, str):
                # Find markdown images: ![alt](url)
                markdown_urls = re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', message.message)
                candidates.extend(markdown_urls)
                # Also find plain URLs containing the filename
                plain_urls = re.findall(r'https?://[^\s\)]+' + re.escape(exact_filename), message.message)
                candidates.extend(plain_urls)

    return candidates


def message_matches_file_filter(
    message: ChatMessage,
    *,
    exact_filename: str | None = None,
    file_extension: str | None = None,
    check_image_locations: bool = False,
) -> bool:
    """Check if a message matches file filtering criteria.

    Args:
        message: ChatMessage to check
        exact_filename: Optional exact filename to match (case-insensitive substring)
        file_extension: Optional extension to filter by
        check_image_locations: If True, include image_locations in check

    Returns:
        True if message matches the filter criteria
    """
    candidates = collect_file_candidates(
        message,
        file_extension=file_extension,
        check_image_locations=check_image_locations,
        exact_filename=exact_filename,
    )

    if exact_filename:
        match_in_files = any(
            isinstance(f, str) and exact_filename.lower() in f.lower()
            for f in candidates
        )
        if not match_in_files:
            return False

    return bool(candidates)
