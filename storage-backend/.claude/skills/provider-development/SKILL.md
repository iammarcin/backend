# Provider Development Skill

This skill encodes how to **add new AI providers** to BetterAI backend.

**Tags:** `#providers` `#ai-models` `#integration` `#factory-pattern` `#backend`

## Provider System Overview

The provider system uses a **registration pattern** with factory resolution:

```
Config (models defined)
     ↓
Registry (maps models → providers)
     ↓
Factory (resolves provider instance)
     ↓
Provider (implements generation)
```

**All 40+ models across 7 providers follow this pattern.**

## Step-by-Step: Adding a New Provider

### Step 1: Define Models (config/providers/<provider>/models.py)

```python
from core.providers.registry.types import ModelConfig, ModelCapabilities

PROVIDER_MODELS = {
    "model-id-1": ModelConfig(
        id="model-id-1",
        name="Model Display Name",
        provider="provider-name",
        capabilities=ModelCapabilities(
            supports_streaming=True,
            supports_vision=False,
            supports_audio_input=False,
            max_tokens=4096,
            supports_batch_api=False,
        ),
        config={"temperature": (0.0, 2.0), "top_p": (0.0, 1.0)},
    ),
    "model-id-2": ModelConfig(...),
}
```

**Key capability flags:**
- `supports_streaming` - Can stream completions
- `supports_vision` - Can accept image inputs
- `supports_audio_input` - Can accept audio directly
- `supports_reasoning` - Has advanced reasoning capability
- `supports_batch_api` - Works with batch endpoints

### Step 2: Aggregate Models (config/providers/__init__.py)

```python
from config.providers.newprovider.models import PROVIDER_MODELS

# Add to ALL_MODELS dictionary
ALL_MODELS.update({
    "model-name": {
        "provider": "newprovider",
        "config": PROVIDER_MODELS["model-id"],
    },
})
```

### Step 3: Implement Provider Class (core/providers/<category>/<provider>.py)

All providers inherit from base classes:

```python
from core.providers.base import BaseTextProvider
from core.exceptions import ProviderError, ValidationError

class NewProviderTextProvider(BaseTextProvider):
    """Text generation via NewProvider API."""

    def __init__(self, api_key: str, **options) -> None:
        self._api_key = api_key
        self._client = NewProviderClient(api_key=api_key)
        self._options = options

    async def generate_stream(
        self,
        messages: list[dict],
        model: str,
        settings: GenerationSettings,
    ) -> AsyncGenerator[TextChunk, None]:
        """Stream text generation."""
        try:
            # Call provider API
            response = await self._client.create_chat_completion(
                model=model,
                messages=messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                stream=True,
            )

            # Stream chunks
            async for chunk in response:
                if chunk.content:
                    yield TextChunk(content=chunk.content)

        except NewProviderError as exc:
            raise ProviderError(f"NewProvider error: {exc}") from exc
        except Exception as exc:
            raise ProviderError(f"Unexpected error: {exc}") from exc

    async def generate(
        self,
        messages: list[dict],
        model: str,
        settings: GenerationSettings,
    ) -> ProviderResponse:
        """Non-streaming text generation."""
        try:
            response = await self._client.create_chat_completion(
                model=model,
                messages=messages,
                temperature=settings.temperature,
                max_tokens=settings.max_tokens,
                stream=False,
            )

            return ProviderResponse(
                content=response.content,
                model=model,
                tokens_used=response.usage.total_tokens,
            )

        except NewProviderError as exc:
            raise ProviderError(f"NewProvider error: {exc}") from exc
```

### Step 4: Register Provider (core/providers/__init__.py)

```python
from core.providers.text.newprovider import NewProviderTextProvider

# Register in factory
register_text_provider("newprovider", NewProviderTextProvider)
```

### Step 5: Create Factory Function (core/providers/factory.py)

```python
def get_text_provider(settings: CoreConfig) -> BaseTextProvider:
    """Resolve text provider based on model."""
    # Already handles registry lookup
    return _provider_factory.get_text_provider(settings.model)
```

### Step 6: Add Configuration (config/defaults.py or config/<category>/defaults.py)

```python
# config/defaults.py
NEWPROVIDER_API_KEY = os.getenv("NEWPROVIDER_API_KEY", "")

# Or feature-specific
# config/audio/defaults.py
NEWPROVIDER_STT_MODEL = os.getenv("NEWPROVIDER_STT_MODEL", "default-model")
```

### Step 7: Initialize Client (core/clients/ai.py)

```python
# Add to client initialization
from newprovider import AsyncNewProviderClient

try:
    ai_clients["newprovider"] = AsyncNewProviderClient(
        api_key=os.getenv("NEWPROVIDER_API_KEY")
    )
except Exception as e:
    logger.warning(f"NewProvider client not initialized: {e}")
```

### Step 8: Write Tests (tests/unit/core/providers/test_newprovider.py)

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.providers.text.newprovider import NewProviderTextProvider
from core.exceptions import ProviderError

@pytest.fixture
def mock_client():
    return AsyncMock()

@pytest.fixture
def provider(mock_client):
    provider = NewProviderTextProvider(api_key="test-key")
    provider._client = mock_client
    return provider

@pytest.mark.asyncio
async def test_generate_stream_success(provider, mock_client):
    """Test streaming text generation."""
    mock_client.create_chat_completion.return_value = AsyncMock()
    # Mock streaming chunks...

    chunks = []
    async for chunk in provider.generate_stream(
        messages=[{"role": "user", "content": "test"}],
        model="test-model",
        settings=GenerationSettings(),
    ):
        chunks.append(chunk)

    assert len(chunks) > 0
    mock_client.create_chat_completion.assert_called_once()

@pytest.mark.asyncio
async def test_generate_stream_error(provider, mock_client):
    """Test error handling."""
    mock_client.create_chat_completion.side_effect = Exception("API Error")

    with pytest.raises(ProviderError):
        async for _ in provider.generate_stream(
            messages=[{"role": "user", "content": "test"}],
            model="test-model",
            settings=GenerationSettings(),
        ):
            pass
```

## Provider Categories

### Text Generation
- **File**: `core/providers/text/<provider>.py`
- **Base**: `BaseTextProvider`
- **Config**: `config/providers/<provider>/models.py`
- **Methods**: `generate()`, `generate_stream()`

### Image Generation
- **File**: `core/providers/image/<provider>.py`
- **Base**: `BaseImageProvider`
- **Methods**: `generate()`, `generate_batch()`

### Video Generation
- **File**: `core/providers/video/<provider>.py`
- **Base**: `BaseVideoProvider`
- **Methods**: `generate()`

### Audio (Speech-to-Text)
- **File**: `core/providers/audio/<provider>.py`
- **Base**: `BaseAudioProvider`
- **Methods**: `transcribe()`, `transcribe_stream()`

### Text-to-Speech
- **File**: `core/providers/tts/<provider>.py`
- **Base**: `BaseTTSProvider`
- **Methods**: `synthesize()`, `synthesize_stream()`

### Realtime (Voice Chat)
- **File**: `core/providers/realtime/<provider>.py`
- **Base**: `BaseRealtimeProvider`
- **Methods**: Various for duplex audio streams

## Exception Handling

All providers should raise typed exceptions:

```python
from core.exceptions import ProviderError, ValidationError, RateLimitError

# Specific error
try:
    response = await self._client.call()
except APIRateLimitError as exc:
    raise RateLimitError(f"Rate limited: {exc}") from exc
except APIAuthError as exc:
    raise ValidationError(f"Auth failed: {exc}") from exc
except APIError as exc:
    raise ProviderError(f"API error: {exc}") from exc
```

## Provider Pattern Checklist

- [ ] Models defined in `config/providers/<provider>/models.py`
- [ ] Models aggregated in `config/providers/__init__.py`
- [ ] Provider class inherits from `BaseXProvider`
- [ ] All async methods implemented
- [ ] Error handling with typed exceptions
- [ ] Registration in factory (`core/providers/__init__.py`)
- [ ] Client initialization if needed (`core/clients/ai.py`)
- [ ] Configuration loaded from environment
- [ ] Unit tests with mocked client
- [ ] Documentation in CLAUDE.md

## Common Provider Patterns

### Streaming with Timeout
```python
async for chunk in self._client.stream(...):
    if chunk.timeout:
        raise ProviderError("Stream timeout")
    yield TextChunk(content=chunk.text)
```

### Retry Logic
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _call_api(self, ...):
    return await self._client.call()
```

### Token Counting
```python
# Some providers can estimate tokens
try:
    tokens = self._client.count_tokens(prompt)
except NotImplementedError:
    # Fallback to rough estimate
    tokens = len(prompt.split()) // 4
```

## Provider Interface Requirements

Every provider must implement:

```python
class BaseTextProvider:
    async def generate_stream(
        self,
        messages: list[dict],
        model: str,
        settings: GenerationSettings,
    ) -> AsyncGenerator[TextChunk, None]:
        """Stream text completion."""
        raise NotImplementedError

    async def generate(
        self,
        messages: list[dict],
        model: str,
        settings: GenerationSettings,
    ) -> ProviderResponse:
        """Generate text completion."""
        raise NotImplementedError
```

## Example: Adding OpenRouter Provider

```python
# 1. config/providers/openrouter/models.py
PROVIDER_MODELS = {
    "openrouter/auto": ModelConfig(
        id="openrouter/auto",
        name="OpenRouter Auto",
        provider="openrouter",
        capabilities=ModelCapabilities(supports_streaming=True),
    ),
}

# 2. config/providers/__init__.py
from config.providers.openrouter.models import PROVIDER_MODELS
ALL_MODELS.update({"openrouter/auto": PROVIDER_MODELS["openrouter/auto"]})

# 3. core/providers/text/openrouter.py
class OpenRouterTextProvider(BaseTextProvider):
    async def generate_stream(self, messages, model, settings):
        async with self._client.stream(...) as response:
            async for chunk in response:
                yield TextChunk(content=chunk.choices[0].delta.content)

# 4. core/providers/__init__.py
register_text_provider("openrouter", OpenRouterTextProvider)

# 5. Tests and done!
```

## See Also
- `@storage-backend/CLAUDE.md` - Backend architecture
- `@storage-backend/DocumentationApp/text-providers-config-handbook.md` - Provider details
- `@core/providers/base.py` - Base class definitions
- `@core/providers/registry/` - Registry system
