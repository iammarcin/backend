**Tags:** `#backend` `#video-generation` `#ai-video` `#gemini-veo` `#openai-sora` `#klingai` `#text-to-video` `#image-to-video`

# Video Generation Feature

Multi-provider video generation system supporting text-to-video and image-to-video workflows with S3 integration for persistent storage.

## System Context

Part of the **storage-backend** FastAPI service. Provides video generation capabilities for chat agentic workflows and standalone generation endpoints.

## Supported Providers

| Provider | Model Aliases | Key Features |
|----------|---------------|--------------|
| **Gemini Veo** | `veo-3.1-fast`, `veo-3.1`, `veo` | Text & image-to-video, aspect ratios, prompt enhancement |
| **OpenAI Sora** | `sora`, `sora-1`, `openai` | Text-to-video with polling, quality settings |
| **KlingAI** | `kling`, `kling-v1` | Text & image-to-video, video extension |

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/video/generate` | POST | Generate video from text/image |
| `/video/extend` | POST | Extend existing video (KlingAI) |

## Request Format

```json
{
  "prompt": "A serene mountain landscape at sunset",
  "settings": {
    "video": {
      "model": "veo-3.1-fast",
      "duration_seconds": 5,
      "aspect_ratio": "9:16",
      "enhance_prompt": true,
      "number_of_videos": 1
    }
  },
  "customer_id": 123,
  "input_image_url": "https://...",  // Optional: image-to-video
  "save_to_db": true
}
```

## Response Format

```json
{
  "success": true,
  "code": 200,
  "data": {
    "video_url": "https://s3.../customers/123/assets/video/...mp4",
    "provider": "gemini",
    "model": "veo-3.1-fast",
    "duration": 5,
    "settings": {
      "aspect_ratio": "9:16",
      "enhance_prompt": true
    }
  }
}
```

## Architecture

```
features/video/
├── routes.py    # /generate, /extend endpoints
├── service.py   # VideoService, VideoGenerationService
├── helpers.py   # Validation, settings extraction, S3 upload
└── __init__.py

core/providers/video/
├── gemini.py    # Gemini Veo provider
├── openai.py    # OpenAI Sora provider
└── klingai.py   # KlingAI provider
```

## Generation Modes

### Text-to-Video
Default mode when no `input_image_url` provided:
```python
video_bytes = await provider.generate(prompt, model, **kwargs)
```

### Image-to-Video
When `input_image_url` is provided:
```python
video_bytes = await provider.generate_from_image(prompt, image_url, **kwargs)
```

### Video Extension (KlingAI only)
Extend existing video with additional frames:
```python
video_bytes = await provider.extend_video(video_id, prompt, **kwargs)
```

## Provider Selection

```
Model name → Pattern matching:
├─ "kling*" → KlingAI
├─ "veo*" OR "gemini*" → Gemini
└─ "sora*" OR "openai*" → OpenAI
Default: veo-3.1-fast
```

## Video Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | veo-3.1-fast | Generation model |
| `duration_seconds` | 5 | Video duration |
| `aspect_ratio` | 9:16 | Video dimensions (9:16, 16:9, 1:1) |
| `enhance_prompt` | true | Auto-enhance prompt |
| `number_of_videos` | 1 | Videos to generate |
| `fps` | null | Frames per second |
| `resolution` | null | Video resolution |
| `generate_audio` | null | Include audio |

## OpenAI Sora Specifics

**Polling Mechanism:**
- `poll_timeout_seconds` - Max wait time
- `poll_interval_seconds` - Check frequency (min 0.1s)
- Async result fetching for long generations

## S3 Storage

**Enabled (save_to_db: true):**
- Path: `customers/{id}/assets/video/{timestamp}_{uuid}.mp4`
- Returns public S3 URL

**Disabled (save_to_db: false):**
- Returns `data:video/mp4;base64,{encoded}`

## Error Handling

| Error Type | HTTP Status |
|------------|-------------|
| Empty prompt, invalid customer_id | 400 |
| Invalid provider configuration | 400 |
| Feature not implemented | 501 |
| Provider API failure | 502 |
| S3 upload failure | 502 |
| Unexpected error | 500 |

## Generation Flow

```
1. HTTP Request → VideoService.generate()
2. Validate params (prompt, customer_id)
3. Extract video settings with defaults
4. Resolve provider via factory
5. Build provider-specific kwargs
6. Detect mode (text/image-to-video)
7. Call provider.generate() or generate_from_image()
8. Upload to S3 (optional)
9. Build metadata
10. Return VideoGenerationResponse
```

## Integration Points

**Agentic Workflows:**
- `VideoGenerationService` injectable into tool executor
- `generate_video` tool in chat workflows

**Dependencies:**
- `core/providers/resolvers.py` - `get_video_provider()`
- `infrastructure/aws/storage.py` - S3 uploads
