**Tags:** `#backend` `#admin` `#model-registry` `#openai` `#api-inspection` `#configuration`

# Admin Feature

Lightweight administrative module providing REST API endpoints for inspecting and listing registered AI model configurations.

## System Context

Part of the **storage-backend** FastAPI service. This feature exposes read-only endpoints for querying the model registry - useful for frontend model selection, debugging provider configurations, and validating model capabilities.

## API Endpoints

All endpoints under `/admin` prefix:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/admin/models/openai` | GET | List all registered OpenAI models |
| `/admin/models/openai/realtime` | GET | List realtime (speech-to-speech) models only |
| `/admin/models/openai/transcription` | GET | List streaming transcription models |
| `/admin/models/openai/by-category/{category}` | GET | Filter models by category (chat, realtime, stt) |
| `/admin/models/openai/{model}` | GET | Get detailed config for specific model |

## Response Format

**Model List Response:**
```json
{
  "total": 45,
  "models": {
    "gpt-4o": { /* ModelConfig */ },
    "gpt-realtime": { /* ModelConfig */ }
  }
}
```

**Single Model Response:**
```json
{
  "model": "gpt-realtime",
  "config": {
    "model_name": "gpt-realtime",
    "provider_name": "openai",
    "api_type": "realtime",
    "support_audio_input": true,
    "voices": ["alloy", "echo", ...]
  },
  "voices": ["alloy", "ash", "ballad", ...]
}
```

## Key Dependencies

- `config/providers/openai/models.py` - Model definitions (chat, realtime, transcription)
- `core/providers/registry/model_config.py` - `ModelConfig` dataclass with capabilities

## File Structure

```
admin/
├── __init__.py   # Exports router
└── routes.py     # 5 GET endpoints (~100 lines)
```

## ModelConfig Fields

Key fields exposed via admin endpoints:
- `model_name`, `provider_name` - Identification
- `category` - Classification (chat, realtime, transcription, stt)
- `api_type` - Interaction type (chat_completion, realtime, audio_transcription)
- `voices` - Available voice options (realtime models)
- `is_deprecated`, `replacement_model` - Deprecation status
- Capability flags: `support_audio_input`, `supports_streaming`, etc.
- Cost fields: `audio_input_cost_per_min`, etc.

## Use Cases

1. **Frontend Model Selection** - Populate UI dropdowns with available models
2. **Voice Discovery** - Get available voices for realtime models
3. **Debugging** - Verify model registrations and capabilities
4. **Deprecation Tracking** - Check which models are deprecated
