# Text Generation Provider Architecture

This document outlines the architecture of the text generation provider system in the `storage-backend`. The system is designed to be modular and extensible, allowing for the integration of various AI text generation providers with different client libraries and API conventions.

## Core Components

The system is composed of five main components:

1.  **Provider Registration**: The central registry for all available text providers.
2.  **Provider Base Interface**: An abstract base class defining the contract for all text providers.
3.  **Provider Implementations**: Concrete classes that implement the provider interface for a specific service (e.g., OpenAI, Gemini).
4.  **Model Registry**: A registry that maps model names and aliases to their configurations, including which provider to use.
5.  **Provider Factory**: A factory function that instantiates and returns a configured provider based on user settings.

---

### 1. Provider Registration

-   **File**: `core/providers/__init__.py`

At application startup, all available text provider classes are imported into this file. The `register_text_provider` function is called for each provider to map a simple string identifier (e.g., `"openai"`, `"gemini"`) to its corresponding class.

**Example:**
```python
# core/providers/__init__.py

from .factory import register_text_provider
from .text.openai import OpenAITextProvider
from .text.gemini import GeminiTextProvider

register_text_provider("openai", OpenAITextProvider)
register_text_provider("gemini", GeminiTextProvider)
```

---

### 2. Provider Base Interface

-   **File**: `core/providers/base.py`

The `BaseTextProvider` is an abstract base class that all text providers must inherit from. It defines the standard interface for text generation.

**Key Methods:**
-   `generate(...)`: The primary abstract method that must be implemented for non-streaming text generation.
-   `stream(...)`: An optional method for streaming responses. The base implementation raises a `NotImplementedError`.
-   `generate_with_reasoning(...)`: An optional method for providers that support reasoning capabilities.
-   `generate_with_audio(...)`: An optional method for providers that support audio input.

This design allows the application to interact with all providers through a consistent API, while still allowing individual providers to have unique capabilities.

---

### 3. Provider Implementations

-   **Directory**: `core/providers/text/`

Each text generation service has its own module within this directory (e.g., `openai.py`, `gemini.py`, `anthropic.py`). Each module contains a class that inherits from `BaseTextProvider` and implements the required methods.

This is where the differences in client libraries and API standards are handled:

-   **`OpenAITextProvider` (`openai.py`)**:
    -   Uses the official `openai` Python client.
    -   It implements the "Chat Completions" standard by constructing a `messages` list with `role` and `content` for each part of the conversation.
    -   The result is obtained from `client.chat.completions.create(...)`.

-   **`GeminiTextProvider` (`gemini.py`)**:
    -   Uses the `google-generativeai` Python client.
    -   It uses a simpler interface, passing a direct `prompt` string to `client.models.generate_content(...)`.

Each provider is responsible for handling the specifics of its client library, including authentication, request formatting, and error handling.

---

### 4. Model Registry

-   **Directory**: `config/providers/`

The model registry is the system's source of truth for which models are available and how to use them.

-   **`core/providers/registry/model_config.py`**: Defines the `ModelConfig` dataclass. This is a rich data structure that holds all metadata for a model, including its `provider_name`, capabilities (e.g., `supports_streaming`), operational parameters (e.g., `max_tokens_default`), and the `api_type` flag that selects between Chat Completions and Responses API flows.

-   **`config/providers/<provider>/models.py`**: Each provider has a `models.py` file that defines a dictionary of `ModelConfig` instances for all models offered by that provider.

-   **`config/providers/__init__.py`**: This file aggregates the dictionaries from all provider-specific files into a single `MODEL_CONFIGS` dictionary. It also defines `MODEL_ALIASES` to map friendly names (e.g., `"claude"`) to specific model versions (e.g., `"claude-4-sonnet"`).

-   **`core/providers/registry/registry.py`**: The `ModelRegistry` class loads all the configs and aliases. Its `get_model_config()` method is the key function that resolves a model name (handling aliases and reasoning modes) to the correct `ModelConfig`.

---

### 5. Provider Factory

-   **File**: `core/providers/factory.py`

The factory brings all the other components together to deliver a ready-to-use provider instance to the application.

**Workflow of `get_text_provider()`:**
1.  It receives the application settings, which include the desired model name.
2.  It calls `get_model_config()` from the model registry to resolve the model name into a full `ModelConfig` object.
3.  It retrieves the `provider_name` from the `ModelConfig`.
4.  It uses this `provider_name` to look up the corresponding provider class in the dictionary that was populated during the registration step.
5.  It instantiates the provider class.
6.  It attaches the `ModelConfig` to the provider instance.
7.  It returns the fully configured provider instance.

---

### 6. API Type Selection (Chat Completions vs Responses API)

Some OpenAI models (notably GPT-5 and O3 series) only support the Responses API, which differs from the standard Chat Completions API in several ways.

**API Type Configuration**:
The `ModelConfig` includes an `api_type` field that determines which API endpoint to use:
- `"chat_completion"` (default): Uses `client.chat.completions.create()`
- `"responses_api"`: Uses `client.responses.create()`

**Key Differences**:

| Aspect | Chat Completions | Responses API |
|--------|-----------------|---------------|
| **User content** | `{"type": "text", "text": "..."}` | `{"type": "input_text", "text": "..."}` |
| **Assistant content** | `{"type": "text", "text": "..."}` | `{"type": "output_text", "text": "..."}` |
| **Images** | `{"type": "image_url", ...}` | `{"type": "input_image", ...}` |
| **Files** | `{"type": "file_url", ...}` | `{"type": "input_file", ...}` |
| **Streaming events** | `delta.content` | `response.text.delta` |
| **Reasoning** | `delta.reasoning_content` | `response.reasoning.delta` |
| **Built-in tools** | Via function calling | Native `web_search_preview`, `code_interpreter` |

**Format Conversion**:
The `OpenAITextProvider` automatically converts chat history from Chat Completions format to Responses API format when `api_type="responses_api"`. This conversion is handled by `core.providers.text.utils.convert_to_responses_format()`.

**Example Model Configuration**:
```python
"gpt-5": ModelConfig(
    model_name="gpt-5-2025-08-07",
    provider_name="openai",
    api_type="responses_api",  # This model ONLY supports Responses API
    is_reasoning_model=True,
    support_image_input=True,
    supports_reasoning_effort=True,
    supports_temperature=False,
    reasoning_effort_values=["minimal", "low", "medium", "high"],
)
```

**Adding New Models**:
When adding a new OpenAI model:
1. Determine which API it supports (check OpenAI documentation)
2. Set `api_type="responses_api"` if it only supports Responses API
3. The provider will automatically use the correct API endpoint and format

### 7. Extensibility

To add a new text generation provider (e.g., "NewProvider"):

1.  **Define Model Configs**: Create `config/text/providers/newprovider/models.py` and define a dictionary of `ModelConfig` objects for its models. Specify `api_type` if applicable.
2.  **Aggregate Models**: In `config/text/providers/__init__.py`, import and add the new model dictionary to `MODEL_CONFIGS`.
3.  **Create Provider Class**: Create `core/providers/text/newprovider.py` with a `NewProviderTextProvider` class that inherits from `BaseTextProvider`.
4.  **Register Provider**: In `core/providers/__init__.py`, import the new provider class and register it with a unique name using `register_text_provider("newprovider", NewProviderTextProvider)`.

### 8. Batch mode support

- `ProviderCapabilities` exposes `batch_api`, `batch_max_requests`, and `batch_max_file_size_mb` so services can determine whether a provider supports the batch API and enforce per-provider limits. Mark capabilities when constructing provider instances (e.g., `ProviderCapabilities(batch_api=True, batch_max_requests=50000)`).
- `ModelConfig` mirrors these fields (`supports_batch_api`, `batch_max_requests`, `batch_max_file_size_mb`) so the registry can answer capability questions per model. Update model definitions in `config/text/providers/<provider>/models.py` when enabling batch support.
- Providers implement `generate_batch()` to integrate with their native batch APIs. The default implementation in `BaseTextProvider` falls back to sequential generation, so unsupported providers can opt out without breaking callers.
- Current support:
  - ✅ **OpenAI** (`core/providers/text/openai.py`) – wraps the OpenAI Batch API via `OpenAIBatchOperations`.
  - ✅ **Anthropic** (`core/providers/text/anthropic.py`) – uses the Claude Message Batches API via `AnthropicBatchOperations`.
  - ✅ **Gemini** (`core/providers/text/gemini/provider.py`) – uses the Gemini Batch API via `GeminiBatchOperations`.
  - ❌ Groq / DeepSeek / Perplexity / xAI – fall back to sequential processing.
- Shared helpers in `core/providers/batch/` encapsulate provider-specific submission, polling, and result parsing so text providers can remain focused on request/response translation.
