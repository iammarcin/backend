**Tags:** `#backend` `#image-generation` `#ai-art` `#openai-dalle` `#stability-ai` `#flux` `#gemini-imagen` `#xai-grok` `#s3`

# Image Generation Feature

Multi-provider image generation system supporting text-to-image and image-to-image workflows with S3 integration for persistent storage.

## System Context

Part of the **storage-backend** FastAPI service. Provides image generation capabilities used by chat agentic workflows, standalone generation endpoints, and internal tools.

## API Endpoint

**POST /image/generate**
- **Authentication:** JWT token required
- **Request:** `ImageGenerationRequest`
- **Response:** `APIResponse[ImageGenerationResponse]`

## Supported Providers

| Provider | Model Aliases | Key Features |
|----------|---------------|--------------|
| **OpenAI DALL-E** | `openai`, `dall-e`, `gpt-image-1` | Quality levels (low/medium/high), safe prompt adjustment |
| **Stability AI** | `sd*`, `stability`, `core` | SD3.5, negative prompts, style presets |
| **Flux** | `flux-dev`, `flux-pro-1.1`, `flux-kontext-pro` | Async polling, image prompts, aspect ratios |
| **Gemini Imagen** | `gemini*`, `imagen*` | Dual API (Imagen + Flash), aspect ratios |
| **xAI Grok** | `grok*`, `grok-2-image` | URL or base64 response, style options |

## Request Format

```json
{
  "prompt": "A serene mountain landscape at sunset",
  "settings": {
    "image": {
      "model": "openai",
      "width": 1024,
      "height": 1024,
      "quality": "high"
    }
  },
  "customer_id": 123,
  "save_to_db": true
}
```

## Response Format

```json
{
  "success": true,
  "code": 200,
  "data": {
    "image_url": "https://s3.../customers/123/assets/image/...png",
    "provider": "openai",
    "model": "gpt-image-1",
    "settings": {
      "width": 1024,
      "height": 1024,
      "quality": "high"
    }
  }
}
```

## Architecture

```
features/image/
├── routes.py    # POST /image/generate endpoint
├── service.py   # ImageService, ImageGenerationService
└── __init__.py  # Package exports

core/providers/image/
├── openai.py    # OpenAI DALL-E provider
├── stability.py # Stability AI provider
├── flux.py      # Flux with polling
├── gemini.py    # Gemini Imagen/Flash
└── xai.py       # xAI Grok provider
```

## Service Layer

**ImageService:**
- Prompt validation (non-empty)
- Customer ID validation (> 0)
- Model alias resolution
- Provider resolution via factory
- Image generation
- Optional S3 upload
- Metadata assembly

**ImageGenerationService:**
- High-level wrapper for agentic workflows
- Returns tool-compatible output format

## Provider Selection

```
Model name → Pattern matching:
├─ "openai", "dall-e", "gpt-image*" → OpenAI
├─ "flux*" → Flux
├─ "sd*", "stability", "core" → Stability
├─ "gemini*", "imagen*" → Gemini
└─ "grok*" → xAI
Default: OpenAI (gpt-image-1)
```

## Provider-Specific Features

**Flux Polling:**
- Returns task_id initially
- Polls every 1s for up to 60s
- Downloads from returned URL

**Gemini Dual API:**
- Imagen models: `client.models.generate_images()`
- Flash models: `client.models.generate_content()`

## S3 Storage

**Enabled (`save_to_db: true`):**
- Uploads to `customers/{id}/assets/image/{uuid}.png`
- Returns public S3 URL

**Disabled (`save_to_db: false`):**
- Returns `data:image/png;base64,{encoded}`

## Error Handling

| Error Type | HTTP Status |
|------------|-------------|
| Empty prompt, invalid customer_id | 400 |
| Provider API failure | 502 |
| S3 upload failure | 502 |
| Unexpected error | 500 |

## Integration Points

**Agentic Workflows:**
- `ImageGenerationService` injectable into tool executor
- `generate_image` tool in chat workflows

**Dependencies:**
- `core/providers/resolvers.py` - `get_image_provider()`
- `infrastructure/aws/storage.py` - S3 uploads
