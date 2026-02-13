# Configuration Management

**Tags:** `#backend` `#config` `#ai-models` `#provider-registry` `#model-configuration` `#aliases` `#defaults` `#agentic` `#transcription` `#openai` `#anthropic` `#gemini` `#groq` `#deepseek` `#perplexity` `#xai`

## System Context

This `config/` directory is part of the **storage-backend** FastAPI service - a multi-provider AI backend supporting chat, image/video generation, TTS, transcription, and semantic search. The configuration layer serves as the **single source of truth** for all AI model definitions, capabilities, and global defaults.

**Role in architecture:** Configuration → feeds into `core/providers/registry/` → enables dynamic provider resolution → used by all `features/` services.

## Purpose

**Comprehensive Configuration Management** providing:
- **Single Source of Truth**: All major configuration centralized in `config/` directory
- **Hierarchical Organization**: Configuration organized by feature domain (audio, tts, video, image, semantic_search, browser, database, text, agentic)
- **Model Registry Source**: All 36+ AI models across 7 providers defined in `config/text/providers/`
- **Capability Declaration**: What each model supports (reasoning, streaming, image input, etc.)
- **Alias Mappings**: User-friendly names ("claude", "gpt-4o") → canonical model IDs
- **Global Defaults**: Temperature, token limits, system prompts in `config/defaults.py`
- **Agentic Settings**: Tool execution limits and timeouts in `config/agentic/`
- **Environment Management**: Environment detection and API key loading
- **Provider-Specific Config**: Dedicated configuration for each provider and feature domain

## Directory Structure

```
config/
├── __init__.py           # Package marker
├── environment.py        # Environment detection (development, production, sherlock)
├── api_keys.py           # All API key loading
├── defaults.py           # Truly global defaults
│
├── audio/                # Audio/STT configuration
│   ├── defaults.py       # Cross-provider audio defaults
│   ├── models.py         # Model aliases
│   ├── prompts.py        # Transcription prompts
│   └── providers/        # Provider-specific (Deepgram, OpenAI, Gemini)
│
├── tts/                  # Text-to-speech configuration
│   ├── defaults.py       # TTS defaults
│   └── providers/        # ElevenLabs, OpenAI configs
│
├── realtime/             # Realtime chat configuration
│   ├── defaults.py       # Realtime defaults
│   └── providers/        # OpenAI Realtime, Gemini Live
│
├── image/                # Image generation configuration
│   ├── defaults.py       # Image defaults
│   ├── aliases.py        # Model aliases
│   └── providers/        # OpenAI, Stability, Flux, Gemini, xAI
│
├── video/                # Video generation configuration
│   ├── defaults.py       # Video defaults
│   ├── models.py         # Model mappings
│   └── providers/        # Gemini Veo, OpenAI Sora, KlingAI
│
├── semantic_search/      # Semantic search configuration
│   ├── defaults.py       # Search defaults
│   ├── qdrant.py         # Qdrant connection
│   ├── embeddings.py     # Embedding config
│   └── utils/            # Collection resolution
│
├── browser/              # Browser automation configuration
│   ├── defaults.py       # Browser defaults
│   ├── aliases.py        # Model aliases
│   └── cleanup.py        # File retention
│
├── database/             # Database configuration
│   ├── defaults.py       # Pool settings
│   └── urls.py           # Database URLs
│
├── text/                 # Text generation (LLM) configuration
│   ├── defaults.py       # Cross-provider text defaults
│   └── providers/        # Per-provider model configs
│       ├── openai/
│       ├── anthropic/
│       ├── gemini/
│       └── ...
│
└── agentic/              # Agentic workflow configuration
    ├── settings.py       # Loop iterations, timeouts
    ├── profiles.py       # Tool profiles
    ├── prompts.py        # Tool descriptions
    └── utils/            # Helper functions
```

## Usage

**Import from config/ subdirectories:**
```python
# Audio configuration
from config.audio import DEFAULT_TRANSCRIBE_MODEL
from config.audio.providers import deepgram, gemini, openai

# TTS configuration
from config.tts.providers.elevenlabs import DEFAULT_VOICE_ID

# Video configuration
from config.video.providers.klingai import API_BASE_URL

# Semantic search
from config.semantic_search import get_collection_for_mode

# Database
from config.database import MAIN_DB_URL, POOL_SIZE

# Text providers
from config.text.providers import MODEL_CONFIGS
```

**Backward compatibility:**
`core.config` still works for essential settings:
```python
from core.config import settings, API_KEYS, ENVIRONMENT
```

## Key Files

### `defaults.py`
Global constants used across providers:
- `DEFAULT_TEMPERATURE = 0.1` - Conservative default
- `DEFAULT_MAX_TOKENS = 4096`
- `SYSTEM_PROMPTS` dict - Default prompts by use case
- `PROVIDER_DEFAULTS` dict - Per-provider capability limits

### `agentic.py`
Controls agentic workflow behavior:
- `MAX_AGENTIC_ITERATIONS = 10` - Tool loop limit
- `TOOL_EXECUTION_TIMEOUT = 300` - Per-tool timeout in seconds
- `EMIT_TOOL_EVENTS = true` - WebSocket event emission

### `text/providers/__init__.py`
Aggregates all model configs into `MODEL_CONFIGS` dict:
```python
MODEL_CONFIGS: dict[str, ModelConfig] = {
    **OPENAI_MODELS,
    **ANTHROPIC_MODELS,
    **GEMINI_MODELS,
    # ... all providers
}
```

### `text/providers/aliases.py`
Maps friendly names to canonical IDs:
```python
"claude" → "claude-sonnet"
"gpt-4o" → actual model
"cheapest-openai" → "gpt-5-nano"
```

## Model Configuration Pattern

Each provider defines models using `ModelConfig` dataclass:

```python
ModelConfig(
    model_name="claude-sonnet-4-5",
    provider_name="anthropic",
    support_image_input=True,
    supports_reasoning_effort=True,
    reasoning_effort_values=[2048, 8000, 16000],
    temperature_max=1.0,
)
```

**Key capability fields:**
- `is_reasoning_model` - Pure reasoning (o3, claude-opus)
- `support_image_input` / `support_audio_input` - Multimodal
- `supports_reasoning_effort` - Extended thinking support
- `api_type` - "chat_completion", "responses_api", "realtime"
- `supports_citations` - Perplexity's citation feature

## Provider-Specific Notes

| Provider | Models | Special Features |
|----------|--------|------------------|
| **Anthropic** | 3 | Reasoning via token counts (2048/8000/16000), temp max 1.0 |
| **OpenAI** | 18 | Responses API for reasoning, realtime voice, transcription |
| **Gemini** | 3 | All support audio input (multimodal) |
| **Groq** | 2 | No image input, no file attachments |
| **DeepSeek** | 2 | Chat + dedicated reasoner variant |
| **Perplexity** | 5 | All models support citations |
| **xAI** | 2 | Function calling support |

## How Configuration Is Used

1. **Frontend** sends model alias (e.g., "claude")
2. **Alias resolver** maps to canonical ID ("claude-sonnet")
3. **Model registry** (`core/providers/registry/`) looks up `MODEL_CONFIGS`
4. **Factory** (`core/providers/factory.py`) selects correct provider class
5. **Service** enforces capabilities from `ModelConfig`

## Adding a New Model

1. Create/update `config/text/providers/<provider>/models.py`
2. Define `ModelConfig` with all capabilities
3. Export in `config/text/providers/__init__.py`
4. Optionally add alias in `config/text/providers/aliases.py`
5. Changes take effect on next import (no restart needed with auto-reload)

## Configuration Best Practices

- **Single source of truth:** All config in `config/`, never scattered in features/providers
- **Hierarchical organization:** Group by domain (audio, tts, video, etc.)
- **Separation of concerns:** Values separate from utility functions
- **Human-readable:** Easy to find and adjust values
- **Provider isolation:** Provider-specific config in dedicated files
- **Environment-aware:** Use environment variables with sensible defaults

## Related Documentation

- `core/providers/registry/` - Model registry implementation
- `core/providers/factory.py` - Provider resolution logic
- Root `CLAUDE.md` - Full backend architecture overview
