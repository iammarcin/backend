"""ElevenLabs text-to-speech configuration."""

from __future__ import annotations

import os
from typing import Dict, List

# API credentials
API_KEY = os.getenv("ELEVEN_API_KEY", "")

# Model defaults
DEFAULT_MODEL = os.getenv("ELEVENLABS_MODEL_DEFAULT", "eleven_monolingual_v1")

# Voice settings
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
DEFAULT_STABILITY = 0.85
DEFAULT_SIMILARITY_BOOST = 0.95
DEFAULT_SIMILARITY = 0.95  # Alias for backward compatibility
DEFAULT_STYLE = 0.0
DEFAULT_USE_SPEAKER_BOOST = False

# Voice ID mapping (migrated from ElevenLabs helpers)
VOICE_NAME_TO_ID: Dict[str, str] = {
    "sherlock": "ywZw8GayBRRkuqUnUGhk",
    "naval": "30zc5PfKKHzfXQfjXbLU",
    "yuval": "Pr8yZ8kUAqVppjka91Ip",
    "elon": "N1LkSFjuhW6TRodJYBhu",
    "hermiona": "IlULyVcJD5RzBQR0n2LG",
    "david": "2hYX7DThVWR7WT2BGQ3N",
    "shaan": "QIhQcQqeyCWyOPuE7kv9",
    "rick": "tRT6MMJIOgJI7oSILj0I",
    "morty": "0P79HLgfttzosL3iYbb5",
    "samantha": "a5l5z8A3DCH5XmSdNGyS",
    "allison": "xctasy8XvGp2cVO9HL9k",
    "amelia": "ZF6FPAbjXT4488VcRRnw",
    "danielle": "FVQMzxJGPUBtfz1Azdoy",
    "hope": "OYTbf65OHHFELVut7v2H",
    "alice": "Xb7hH8MSUJpSbSDYk0k2",
    "bill": "pqHfZKP75CvOlQylNhV4",
    "brian": "nPczCjzI2devNBz1zQrb",
    "eric": "cjVigY5qzO86Huf0OWal",
    "jessica": "cgSgspJ2msm6clMCkdW9",
    "sarah": "EXAVITQu4vr4xnSDxMaL",
    "claire": "gsm4lUH9bnZ3pjR1Pw7w",
    "anarita": "wJqPPQ618aTW29mptyoc",
    "bianca": "2bk7ULW9HfwvcIbMWod0",
    "will": "bIHbv24MWmeRgasZH58o",
}

KNOWN_VOICE_IDS = set(VOICE_NAME_TO_ID.values()) | {DEFAULT_VOICE_ID}

# Streaming / realtime defaults
DEFAULT_CHUNK_SCHEDULE: List[int] = [120, 160, 250, 290]
DEFAULT_REALTIME_FORMAT = "pcm_24000"
DEFAULT_INACTIVITY_TIMEOUT = 180  # seconds
STREAM_TIMEOUT = 30  # seconds for REST streaming timeouts
BUFFER_SIZE = 1024  # bytes per chunk for streaming

__all__ = [
    "API_KEY",
    "DEFAULT_MODEL",
    "DEFAULT_VOICE_ID",
    "DEFAULT_STABILITY",
    "DEFAULT_SIMILARITY_BOOST",
    "DEFAULT_SIMILARITY",
    "DEFAULT_STYLE",
    "DEFAULT_USE_SPEAKER_BOOST",
    "VOICE_NAME_TO_ID",
    "KNOWN_VOICE_IDS",
    "DEFAULT_CHUNK_SCHEDULE",
    "DEFAULT_REALTIME_FORMAT",
    "DEFAULT_INACTIVITY_TIMEOUT",
    "STREAM_TIMEOUT",
    "BUFFER_SIZE",
]
