"""Audio provider model aliases and mappings.

Edit these to customize how user-friendly names are resolved to actual model IDs.
"""

from __future__ import annotations


# Gemini speech-to-text model aliases
GEMINI_SPEECH_MODEL_ALIASES: dict[str, str] = {
    "gemini": "models/gemini-2.0-flash-exp",
    "gemini-2.0-flash-exp": "models/gemini-2.0-flash-exp",
    "models/gemini-2.0-flash-exp": "models/gemini-2.0-flash-exp",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-2.5-pro": "gemini-2.5-pro",
}


__all__ = ["GEMINI_SPEECH_MODEL_ALIASES"]
