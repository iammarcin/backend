"""API key loading for external providers."""

from __future__ import annotations

import os
from typing import Dict


def load_api_keys() -> Dict[str, str]:
    """Load API keys from the environment with sensible defaults."""

    return {
        # AI Providers
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
        "google": os.getenv("GOOGLE_API_KEY", ""),
        "groq": os.getenv("GROQ_API_KEY", ""),
        "perplexity": os.getenv("PERPLEXITY_API_KEY", ""),
        "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
        "xai": os.getenv("XAI_API_KEY", ""),
        # Audio/TTS Providers
        "deepgram": os.getenv("DEEPGRAM_API_KEY", ""),
        "elevenlabs": os.getenv("ELEVEN_API_KEY", ""),
        # AWS
        "aws_access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
        "aws_secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
        "aws_region": os.getenv("AWS_REGION", "us-east-1"),
    }


API_KEYS = load_api_keys()

OPENAI_API_KEY = API_KEYS["openai"]
ANTHROPIC_API_KEY = API_KEYS["anthropic"]
GOOGLE_API_KEY = API_KEYS["google"]
GROQ_API_KEY = API_KEYS["groq"]
PERPLEXITY_API_KEY = API_KEYS["perplexity"]
DEEPSEEK_API_KEY = API_KEYS["deepseek"]
XAI_API_KEY = API_KEYS["xai"]
DEEPGRAM_API_KEY = API_KEYS["deepgram"]
ELEVENLABS_API_KEY = API_KEYS["elevenlabs"]
AWS_ACCESS_KEY_ID = API_KEYS["aws_access_key"]
AWS_SECRET_ACCESS_KEY = API_KEYS["aws_secret_key"]
AWS_REGION = API_KEYS["aws_region"]

__all__ = [
    "API_KEYS",
    "ANTHROPIC_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "DEEPGRAM_API_KEY",
    "DEEPSEEK_API_KEY",
    "ELEVENLABS_API_KEY",
    "GOOGLE_API_KEY",
    "GROQ_API_KEY",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
    "XAI_API_KEY",
    "load_api_keys",
]
