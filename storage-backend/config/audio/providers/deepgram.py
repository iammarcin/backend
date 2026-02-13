"""Deepgram audio transcription configuration."""

import os

# API credentials
API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# Model defaults
DEFAULT_MODEL = "nova-3"

# Transcription settings
DEFAULT_LANGUAGE = "en"
SMART_FORMAT = True
PUNCTUATE = True
