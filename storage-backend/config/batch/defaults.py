"""Default configuration values for batch mode."""

# Polling configuration
BATCH_POLLING_INTERVAL_SECONDS = 10
"""How often to poll batch job status (in seconds)."""

BATCH_INITIAL_POLLING_DELAY_SECONDS = 5
"""Initial delay before first status poll (in seconds)."""

BATCH_TIMEOUT_SECONDS = 86400
"""Maximum time to wait for batch completion (24 hours in seconds)."""

BATCH_MAX_POLLING_ATTEMPTS = 8640
"""Maximum polling attempts (24 hours at 10s intervals)."""

# OpenAI limits (per API documentation)
BATCH_MAX_REQUESTS_OPENAI = 50000
"""Maximum requests per OpenAI batch job."""

BATCH_MAX_FILE_SIZE_MB_OPENAI = 200
"""Maximum input file size for OpenAI batch (in MB)."""

# Anthropic limits (per API documentation)
BATCH_MAX_REQUESTS_ANTHROPIC = 100000
"""Maximum requests per Anthropic batch job."""

BATCH_MAX_FILE_SIZE_MB_ANTHROPIC = 256
"""Maximum input file size for Anthropic batch (in MB)."""

# Gemini limits (per API documentation)
BATCH_MAX_REQUESTS_GEMINI = 50000
"""Maximum requests per Gemini batch job (conservative estimate)."""

BATCH_MAX_FILE_SIZE_MB_GEMINI = 2048
"""Maximum input file size for Gemini batch (in MB)."""

# Result expiry
BATCH_RESULT_EXPIRY_DAYS = 29
"""How long batch results remain available (Anthropic default)."""


__all__ = [
    "BATCH_POLLING_INTERVAL_SECONDS",
    "BATCH_INITIAL_POLLING_DELAY_SECONDS",
    "BATCH_TIMEOUT_SECONDS",
    "BATCH_MAX_POLLING_ATTEMPTS",
    "BATCH_MAX_REQUESTS_OPENAI",
    "BATCH_MAX_REQUESTS_ANTHROPIC",
    "BATCH_MAX_REQUESTS_GEMINI",
    "BATCH_MAX_FILE_SIZE_MB_OPENAI",
    "BATCH_MAX_FILE_SIZE_MB_ANTHROPIC",
    "BATCH_MAX_FILE_SIZE_MB_GEMINI",
    "BATCH_RESULT_EXPIRY_DAYS",
]
