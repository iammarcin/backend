# Provider Registry System

**Tags:** `#backend` `#providers` `#ai-providers` `#factory-pattern` `#registry` `#text-generation` `#image-generation` `#video-generation` `#tts` `#speech-to-text` `#realtime` `#semantic-search` `#openai` `#anthropic` `#gemini` `#elevenlabs` `#deepgram` `#qdrant` `#streaming`

## System Context

This `providers/` directory is part of the **storage-backend** core infrastructure layer. It implements the **Provider Registry Pattern** enabling the backend to support 40+ AI models across 7 provider categories through a unified interface.

**Architecture position:** `config/providers/` (model definitions) → **`core/providers/`** (registry + implementations) → `features/` (consume via factories)

## Purpose

Multi-provider AI integration system providing:
- **Import-Time Registration** - All providers registered when module loads
- **Factory Resolution** - `get_*_provider(settings)` resolves correct implementation
- **Base Interfaces** - Abstract classes ensuring consistent API across providers
- **Model Registry** - Maps model names → provider + capabilities
- **7 Provider Categories** - Text, Image, Video, Audio, TTS, Realtime, Semantic

## Directory Structure

```
providers/
├── __init__.py           # CENTRAL REGISTRATION - imports all providers
├── base.py               # Abstract base classes for all provider types
├── capabilities.py       # ProviderCapabilities dataclass
├── factory.py            # Re-exports factory functions
├── registries.py         # Global provider registries (dicts)
├── resolvers.py          # Factory functions (get_text_provider, etc.)
│
├── registry/             # Model configuration registry
│   ├── model_config.py   # ModelConfig dataclass
│   └── registry.py       # ModelRegistry class, get_model_config()
│
├── text/                 # Text generation (8 providers)
│   ├── openai.py         # OpenAI (GPT-4o, o3, etc.)
│   ├── anthropic.py      # Anthropic (Claude)
│   ├── gemini/           # Google Gemini (multi-file)
│   ├── groq.py           # Groq
│   ├── perplexity.py     # Perplexity Sonar
│   ├── deepseek.py       # DeepSeek
│   ├── xai/              # xAI Grok (multi-file)
│   └── claude_code_sidecar.py  # Claude Code sidecar
│
├── image/                # Image generation (5 providers)
│   ├── openai.py         # DALL-E
│   ├── stability.py      # Stable Diffusion
│   ├── flux.py           # Flux (Black Forest Labs)
│   ├── gemini.py         # Gemini Imagen
│   └── xai.py            # Grok
│
├── video/                # Video generation (3 providers)
│   ├── gemini.py         # Veo 3.1
│   ├── openai.py         # Sora
│   └── klingai.py        # KlingAI
│
├── audio/                # Speech-to-text (5 providers)
│   ├── deepgram.py       # Deepgram (WebSocket streaming)
│   ├── openai.py         # Whisper
│   ├── openai_streaming.py
│   ├── gemini.py         # Gemini STT
│   └── gemini_streaming.py
│
├── tts/                  # Text-to-speech (2 providers)
│   ├── openai.py         # OpenAI TTS
│   └── elevenlabs.py     # ElevenLabs (REST + WebSocket)
│
├── realtime/             # Realtime voice chat (2 providers)
│   ├── openai.py         # OpenAI Realtime API
│   └── google.py         # Gemini Live
│
├── semantic/             # Vector search (1 provider)
│   ├── qdrant.py         # Qdrant + OpenAI embeddings
│   ├── bm25.py           # BM25 sparse vectors (hybrid search)
│   └── circuit_breaker.py
│
├── garmin/               # Health data providers
└── withings/
```

## Core Architecture

### 1. Base Interfaces (`base.py`)

All providers implement typed abstract base classes:

```python
class BaseTextProvider(ABC):
    capabilities: ProviderCapabilities

    async def generate(prompt, model, temperature, max_tokens, **kwargs) -> ProviderResponse
    async def stream(prompt, model, **kwargs) -> AsyncIterator[str | dict]
    async def generate_with_reasoning(prompt, reasoning_effort, **kwargs) -> ProviderResponse

class BaseImageProvider(ABC):
    async def generate(prompt, model, width, height, **kwargs) -> bytes

class BaseVideoProvider(ABC):
    async def generate(prompt, model, duration_seconds, **kwargs) -> bytes
    async def generate_from_image(prompt, image_url, **kwargs) -> bytes

class BaseTTSProvider(ABC):
    async def generate(request: TTSRequest) -> TTSResult
    async def stream(request: TTSRequest) -> AsyncIterator[bytes]

class BaseAudioProvider(ABC):
    async def transcribe_file(request) -> SpeechTranscriptionResult
    async def transcribe_stream(audio_source, manager) -> str

class BaseRealtimeProvider(ABC):
    async def open_session(settings) -> None
    async def receive_events() -> AsyncIterator[RealtimeEvent]
    async def send_user_event(payload) -> None
```

### 2. Provider Registration (`__init__.py`)

All providers registered at import time:

```python
# Imports trigger registration
from core.providers.text.openai import OpenAITextProvider
from core.providers.text.anthropic import AnthropicTextProvider
# ... all providers

# Registration calls
register_text_provider("openai", OpenAITextProvider)
register_text_provider("anthropic", AnthropicTextProvider)
# ... etc
```

### 3. Factory Resolution (`resolvers.py`)

Services get providers via factory functions:

```python
# Text: Model Registry lookup
provider = get_text_provider(settings)  # Uses settings.text.model

# Image: Pattern matching
provider = get_image_provider(settings)  # "flux-*" → FluxImageProvider

# TTS: Voice-first resolution
provider = get_tts_provider(settings)  # Voice determines provider

# Realtime: Model override mapping
provider = get_realtime_provider("gpt-4o-realtime")
```

### 4. Model Configuration (`registry/`)

Maps model names to providers and capabilities:

```python
ModelConfig(
    model_name="gpt-4o",
    provider_name="openai",
    api_type="chat_completion",
    support_image_input=True,
    supports_streaming=True,
    temperature_max=2.0,
    # ...
)
```

## Provider Resolution Strategies

| Category | Strategy | Example |
|----------|----------|---------|
| **Text** | Model Registry lookup | "claude-sonnet" → Anthropic |
| **Image** | Pattern matching | "flux-*" → Flux, "dall-e-*" → OpenAI |
| **Video** | Pattern matching | "veo-*" → Gemini, "sora" → OpenAI |
| **Audio** | Multi-level (provider → model → action) | streaming → Deepgram |
| **TTS** | Voice-first | ElevenLabs voice → ElevenLabs |
| **Realtime** | Model override map | "gpt-4o-realtime" → OpenAI |
| **Semantic** | Singleton cache | "qdrant" → cached instance |

## Provider Implementation Pattern

```python
class OpenAITextProvider(BaseTextProvider):
    provider_name = "openai"

    def __init__(self):
        self.client = ai_clients.get("openai_async")  # Global client
        self.capabilities = ProviderCapabilities(
            streaming=True,
            reasoning=False,
            image_input=True,
        )

    async def generate(self, prompt, model=None, **kwargs):
        model = model or self._model_config.model_name
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            # ...
        )
        return ProviderResponse(content=response.choices[0].message.content)

    async def stream(self, prompt, model=None, **kwargs):
        async for chunk in self.client.chat.completions.create(
            model=model, stream=True, ...
        ):
            yield chunk.choices[0].delta.content
```

## Capabilities System

`ProviderCapabilities` declares what each provider supports:

```python
@dataclass
class ProviderCapabilities:
    streaming: bool = False
    reasoning: bool = False
    citations: bool = False
    audio_input: bool = False
    image_input: bool = False
    file_input: bool = False
    audio_output: bool = False
    image_to_video: bool = False
    function_calling: bool = False
```

Services check capabilities before calling optional methods:
```python
if provider.capabilities.reasoning:
    response = await provider.generate_with_reasoning(...)
```

## Adding a New Provider

### Step 1: Implement Base Class
```python
# core/providers/text/myai.py
class MyAITextProvider(BaseTextProvider):
    provider_name = "myai"

    def __init__(self):
        self.client = MyAIClient(api_key=MYAI_API_KEY)
        self.capabilities = ProviderCapabilities(streaming=True)

    async def generate(self, prompt, **kwargs): ...
    async def stream(self, prompt, **kwargs): ...
```

### Step 2: Register in `__init__.py`
```python
from core.providers.text.myai import MyAITextProvider
register_text_provider("myai", MyAITextProvider)
```

### Step 3: Add Model Config
```python
# config/providers/myai/models.py
MYAI_MODELS = {
    "myai-pro": ModelConfig(
        model_name="myai-pro",
        provider_name="myai",
        # capabilities...
    )
}
```

### Step 4: Initialize Client (if needed)
```python
# core/clients/ai.py
ai_clients["myai"] = MyAIClient(api_key=os.getenv("MYAI_API_KEY"))
```

## Error Handling

Providers raise typed exceptions:

```python
from core.exceptions import ProviderError, ValidationError

async def generate(self, prompt, **kwargs):
    if not prompt:
        raise ValidationError("prompt", "Prompt cannot be empty")
    try:
        return await self.client.create(...)
    except APIError as e:
        raise ProviderError(str(e), provider=self.provider_name)
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `__init__.py` | Central registration point |
| `base.py` | Abstract base classes |
| `capabilities.py` | Capability flags dataclass |
| `resolvers.py` | Factory functions (`get_*_provider`) |
| `registries.py` | Global registry dicts |
| `registry/model_config.py` | ModelConfig dataclass |
| `registry/registry.py` | ModelRegistry, `get_model_config()` |

## Related Documentation

- `config/providers/` - Model definitions per provider
- `core/CLAUDE.md` - Core infrastructure overview
- `core/clients/ai.py` - Global AI client initialization
- Root `CLAUDE.md` - Full backend architecture
