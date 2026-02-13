"""Google Gemini default settings."""

# Model defaults
DEFAULT_MODEL = "gemini-flash-latest"

# Generation defaults
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 2048

# Tool configuration
TOOL_CONFIG_MODE = "auto"  # "auto", "any", "none"
ALLOWED_FUNCTION_NAMES = None  # None = allow all
DEFAULT_TOOL_SETTINGS = {
    "google_search": {"enabled": True},
    "code_execution": True,
    "functions": [],
}

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_MAX_TOKENS",
    "TOOL_CONFIG_MODE",
    "ALLOWED_FUNCTION_NAMES",
    "DEFAULT_TOOL_SETTINGS",
]
