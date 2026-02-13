# Image & Video Generation Systems - Architecture & Implementation Guide

## Overview

The betterai codebase implements a sophisticated provider-based architecture for image and video generation, supporting multiple third-party providers through a factory pattern. This document details the complete system including endpoints, providers, request/response structures, and frontend integration.

---

## 1. IMAGE GENERATION SYSTEM

### 1.1 HTTP Endpoint & Route

**File:** `/home/user/betterai/docker/storage-backend/features/image/routes.py`

**Endpoint:**
```
POST /image/generate
Content-Type: application/json
Authorization: Bearer <jwt-token>
```

**Response Model:** `APIResponse` wrapping `ImageGenerationResponse`

### 1.2 Request Structure

**File:** `/home/user/betterai/docker/storage-backend/core/pydantic_schemas/requests.py`

```python
class ImageGenerationRequest(BaseModel):
    prompt: str                      # Required, min_length=1
    settings: Dict[str, Any]        # Optional, defaults to {}
    customer_id: int                # Required, must be > 0
    image_url: Optional[str]        # Optional reference image
    message_id: Optional[str]       # Optional message reference
    save_to_db: bool                # Default: True (saves to S3)
    session_id: Optional[str]       # Optional session reference
```

**Settings Structure (nested in `settings.image`):**
```json
{
  "settings": {
    "image": {
      "model": "openai|flux|stability|gemini|grok",
      "width": 1024,
      "height": 1024,
      "quality": "low|medium|high|auto",
      // Provider-specific parameters below
    }
  }
}
```

### 1.3 Response Structure

**File:** `/home/user/betterai/docker/storage-backend/core/pydantic_schemas/responses.py`

```python
class ImageGenerationResponse(BaseModel):
    image_url: str              # Either S3 URL or data:image/png;base64,...
    provider: str               # Provider name (openai, stability, flux, gemini, xai)
    model: str                  # Model identifier used
    settings: Dict[str, Any]    # Echo of all generation settings

# Wrapped in APIResponse:
class APIResponse(BaseModel):
    success: bool
    data: ImageGenerationResponse
    error: Optional[str]
    code: int = 200
```

### 1.4 Available Image Providers

#### A. OpenAI (DALL-E)

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/openai.py`

**Class:** `OpenAIImageProvider`

**Model Identifiers:**
- `gpt-image-1` (default)
- `dall-e-3`
- Any model starting with `openai` or `dall-e`

**Parameters:**
- `width`: 1024 (default)
- `height`: 1024 (default)
- `quality`: "low", "medium" (default), "high", "auto"
- `disable_safe_prompt_adjust`: bool (adds safety prompt prefix if true)

**Implementation Details:**
- Uses `asyncio.to_thread()` to call synchronous OpenAI client
- Returns base64-decoded image bytes from response
- Quality "standard" is normalized to "medium"
- Safe prompt adjustment is applied by default

**Error Handling:** Raises `ProviderError` on API failures

---

#### B. Stability AI

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/stability.py`

**Class:** `StabilityImageProvider`

**Model Identifiers:**
- `core` (default)
- `sd3`, `sd3.5`, `sd-ultra`
- Anything starting with `sd` or `stability`

**Parameters:**
- `width`: 1024 (default)
- `height`: 1024 (default)
- `negative_prompt`: str (optional)
- `seed`: int (optional)
- `cfg_scale`: float (optional)
- `style_preset`: str (optional)
- `mode`: str (optional)

**Implementation Details:**
- Uses httpx.AsyncClient for HTTP requests
- Models `sd3.5*` are mapped to `sd3` endpoint
- Supports both JSON and image/binary responses
- Can return base64 or binary image directly
- Async multipart form encoding

**Required Environment:** `STABILITY_API_KEY`

---

#### C. Flux (Black Forest Labs)

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/flux.py`

**Class:** `FluxImageProvider`

**Model Identifiers:**
- `flux-dev` (default)
- `flux-pro`
- Anything starting with `flux`

**Parameters:**
- `width`: 1024 (default)
- `height`: 1024 (default)
- `guidance`: float (optional, guidance scale)
- `steps`: int (optional, number of steps)
- `seed`: int (optional)
- `prompt_upsampling`: bool (optional)

**Implementation Details:**
- Uses BFL (Black Forest Labs) API at `https://api.bfl.ml/`
- Supports async task polling (status-based)
- Polls for completion up to 30 times (with 2-second intervals)
- Can return both base64 and downloadable URLs
- Includes comprehensive error handling for queued tasks
- Task timeout: 60 seconds (30 polls × 2 seconds)

**Required Environment:**
- `FLUX_API_KEY`
- `FLUX_API_VERSION` (default: "v1")

---

#### D. Google Gemini (Imagen)

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/gemini.py`

**Class:** `GeminiImageProvider`

**Model Identifiers:**
- `imagen-4.0-generate-001` (default)
- Anything starting with `imagen` or `gemini`

**Parameters:**
- `width`: 1024 (default)
- `height`: 1024 (default)
- `number_of_images`: int (default: 1)

**Implementation Details:**
- Uses Google GenAI SDK (`google.genai.types`)
- Automatically calculates aspect ratio from width/height
- Aspect ratio format: "WIDTHxHEIGHT" (e.g., "16:9")
- Extracts image bytes from response (supports multiple fields: `image_bytes`, `data`, `b64_json`)
- Uses `asyncio.to_thread()` for sync API calls

**Required Environment:** Standard Google GenAI SDK initialization (handled by `core/clients/ai.py`)

---

#### E. xAI Grok

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/xai.py`

**Class:** `XaiImageProvider`

**Model Identifiers:**
- `grok-2-image` (default)
- Anything starting with `grok`

**Parameters:**
- `width`: 1024 (default)
- `height`: 1024 (default)
- `response_format`: "b64_json" (default) | "url"
- `number_of_images`: int (default: 1)
- `size`: str (optional, e.g., "1024x1024" overrides width/height)
- `background`: str (optional)
- `moderation`: bool (optional)
- `output_format`: str (optional)
- `output_compression`: str (optional)
- `style`: str (optional)
- `user`: str (optional)
- `seed`: int (optional)
- `quality`: str (ignored, logs warning)

**Implementation Details:**
- Posts to `{base_url}/images/generations`
- Supports both base64 and URL response formats
- Validates and handles dimension overrides
- Downloads images from URLs if needed
- Default base URL: `https://api.x.ai/v1` (configurable)

**Required Environment:**
- `XAI_API_KEY`
- `XAI_API_BASE_URL` (optional, defaults to https://api.x.ai/v1)

---

### 1.5 Provider Resolution Logic

**File:** `/home/user/betterai/docker/storage-backend/core/providers/factory.py`

**Function:** `get_image_provider(settings: Dict[str, object]) -> BaseImageProvider`

**Resolution Steps:**
1. Extracts model from `settings['image']['model']` (default: "openai")
2. Normalizes model name to lowercase
3. Maps model to provider name:
   - `openai*`, `dall-e*`, `gpt-image*` → `openai`
   - `flux*` → `flux`
   - `sd*`, `stability*`, `core` → `stability`
   - `gemini*`, `imagen*` → `gemini`
   - `grok*` → `xai`
   - Anything else → ConfigurationError
4. Instantiates provider class
5. Returns provider instance

**Registration:** Happens at import time in `/home/user/betterai/docker/storage-backend/core/providers/__init__.py`

---

### 1.6 Image Generation Service

**File:** `/home/user/betterai/docker/storage-backend/features/image/service.py`

**Class:** `ImageService`

**Key Method:** `async def generate_image(...) -> Tuple[Optional[str], bytes, Dict[str, object]]`

**Workflow:**
1. Validates prompt (non-empty) and customer_id (> 0)
2. Extracts settings from nested structure
3. Gets provider via factory.get_image_provider(settings)
4. Calls `provider.generate(prompt, model, width, height, quality)`
5. If `save_to_s3=True`:
   - Uploads to S3 via `StorageService.upload_image()`
   - Returns S3 URL
6. Otherwise: Returns None for URL (client uses base64 data URL)
7. Returns tuple: (s3_url, image_bytes, metadata)

**Metadata Structure:**
```python
{
    "provider": getattr(provider, "provider_name"),
    "model": model,
    "width": width,
    "height": height,
    "quality": getattr(provider, "last_quality", quality)
}
```

---

### 1.7 Shared Image Utilities

**File:** `/home/user/betterai/docker/storage-backend/core/providers/image/utils/flux.py`

**Utilities:**

```python
def find_first_base64(payload: Any) -> Optional[bytes]
    # Recursively searches response for base64-encoded image
    # Looks for keys: image, image_base64, image_b64, b64_json, base64, etc.

def find_first_url(payload: Any) -> Optional[str]
    # Recursively searches response for image URL

def maybe_decode_base64(value: str, require_length: bool = True) -> Optional[bytes]
    # Safely decodes base64 strings

async def download_image(url: str, api_key: str) -> bytes
    # Downloads image from URL with API authentication
```

---

## 2. VIDEO GENERATION SYSTEM

### 2.1 HTTP Endpoint & Route

**File:** `/home/user/betterai/docker/storage-backend/features/video/routes.py`

**Endpoint:**
```
POST /video/generate
Content-Type: application/json
Authorization: Bearer <jwt-token>
```

**Response Model:** `APIResponse` wrapping `VideoGenerationResponse`

### 2.2 Request Structure

**File:** `/home/user/betterai/docker/storage-backend/core/pydantic_schemas/requests.py`

```python
class VideoGenerationRequest(BaseModel):
    prompt: str                      # Required, min_length=1
    settings: Dict[str, Any]        # Optional, defaults to {}
    customer_id: int                # Required, must be > 0
    input_image_url: Optional[str]  # Optional image for image-to-video mode
    save_to_db: bool                # Default: True (saves to S3)
    session_id: Optional[str]       # Optional session reference
```

**Settings Structure (nested in `settings.video`):**
```json
{
  "settings": {
    "video": {
      "model": "veo-3.1-fast|sora-2",
      "duration_seconds": 5,
      "aspect_ratio": "16:9|9:16",
      "person_generation": "dont_allow|allow_adult",
      "enhance_prompt": true,
      "number_of_videos": 1,
      "file_extension": "mp4",
      "fps": 24,
      "resolution": "720p|1080p",
      "generate_audio": bool,
      "compression_quality": "medium",
      "reference_images": [string],
      "last_frame": string (url),
      "mask": string (url),
      "negative_prompt": string,
      "poll_timeout_seconds": 240,      // OpenAI only
      "poll_interval_seconds": 5.0      // OpenAI only
    }
  }
}
```

### 2.3 Response Structure

**File:** `/home/user/betterai/docker/storage-backend/core/pydantic_schemas/responses.py`

```python
class VideoGenerationResponse(BaseModel):
    video_url: str                  # Either S3 URL or data:video/mp4;base64,...
    provider: str                   # Provider name (gemini, openai)
    model: str                      # Model identifier used
    duration: int                   # Duration in seconds
    settings: Dict[str, Any]        # Echo of all generation settings
```

---

### 2.4 Available Video Providers

#### A. Google Gemini Veo 3.1 Fast

**File:** `/home/user/betterai/docker/storage-backend/core/providers/video/gemini.py`

**Class:** `GeminiVideoProvider`

**Model Identifiers:**
- `veo-3.1-fast` (default) → maps to `veo-3.1-fast-generate-preview`
- `veo-3.1` → maps to `veo-3.1-generate-preview`
- Anything starting with `veo` or `gemini`

**Capabilities:**
- Text-to-video generation
- Image-to-video generation
- Aspect ratios: 16:9, 9:16
- Resolutions: 720p, 1080p
- Reference image support

**Parameters:**
- `duration_seconds`: 5 (default, clamped to valid range)
- `aspect_ratio`: "16:9" (default), "9:16"
- `person_generation`: "dont_allow", "allow_adult" (optional)
- `enhance_prompt`: bool (optional, not supported by all models)
- `number_of_videos`: int (default: 1)
- `resolution`: "720p", "1080p" (optional)
- `negative_prompt`: str (optional)
- `reference_images`: List[str] (URLs or objects)
- `last_frame`: str (URL)

**Implementation Details:**
- Uses Google GenAI SDK (`google.genai.types`)
- Builds `GenerateVideosConfig` via utility functions
- Polls for completion every 20 seconds (600-second timeout)
- Supports reference images as ASSET type
- STYLE reference type is unsupported and falls back to ASSET

**Methods:**
```python
async def generate(
    prompt: str,
    model: str | None = None,
    duration_seconds: int = 5,
    aspect_ratio: str = "16:9",
    **kwargs
) -> bytes

async def generate_from_image(
    prompt: str,
    image_url: str,
    **kwargs
) -> bytes
```

**Required Environment:** Standard Google GenAI SDK initialization

**Polling Configuration:**
- Poll interval: 20 seconds
- Timeout: 600 seconds (10 minutes)

---

#### B. OpenAI Sora

**File:** `/home/user/betterai/docker/storage-backend/core/providers/video/openai.py`

**Class:** `OpenAIVideoProvider`

**Model Identifiers:**
- `sora-2` (default)
- Anything starting with `sora` or `openai`

**Capabilities:**
- Text-to-video generation
- Image-to-video generation
- Aspect ratios: 16:9, 9:16
- Resolutions: 720p, 1080p
- Flexible polling configuration

**Parameters:**
- `duration_seconds`: 4-12 seconds (clamped to allowed values: 4, 8, 12)
- `aspect_ratio`: "16:9" (default), "9:16"
- `size`: "WIDTHxHEIGHT" (optional, overrides aspect_ratio-based sizing)
- `resolution`: "720p", "1080p" (optional, maps to predefined sizes)
- `poll_timeout_seconds`: 240 (default, min: 1)
- `poll_interval_seconds`: 5.0 (default, min: 0.1)

**Size Mapping:**
```
16:9 aspect ratio:
  Default: 1280x720
  720p: 1280x720
  1080p: 1792x1024

9:16 aspect ratio:
  Default: 720x1280
  720p: 720x1280
  1080p: 1024x1792
```

**Implementation Details:**
- Uses AsyncOpenAI client with `.videos` API
- Submits job and polls for completion
- Supports input reference images with optional resizing
- Downloads video bytes from completed job
- Validates input reference dimensions against target size

**Methods:**
```python
async def generate(
    prompt: str,
    model: str | None = None,
    duration_seconds: int = 5,
    aspect_ratio: str = "16:9",
    **kwargs
) -> bytes

async def generate_from_image(
    prompt: str,
    image_url: str,
    **kwargs
) -> bytes
```

**Job Status Flow:**
1. Create job → status: "queued"
2. Poll status → "processing" (transient)
3. Complete → status: "completed"
4. Failed → status: "failed|cancelled|canceled" (with error details)

**Required Environment:** `OPENAI_API_KEY` (handled by `core/clients/ai.py`)

---

### 2.5 Provider Resolution Logic

**File:** `/home/user/betterai/docker/storage-backend/core/providers/factory.py`

**Function:** `get_video_provider(settings: Dict[str, object]) -> BaseVideoProvider`

**Resolution Steps:**
1. Extracts model from `settings['video']['model']` (default: "veo-3.1-fast")
2. Normalizes model name to lowercase
3. Maps model to provider name:
   - `veo*`, `gemini*` → `gemini`
   - `sora*`, `openai*` → `openai`
   - Anything else → ConfigurationError
4. Instantiates provider class
5. Returns provider instance

---

### 2.6 Video Generation Service

**File:** `/home/user/betterai/docker/storage-backend/features/video/service.py`

**Class:** `VideoService`

**Key Method:** `async def generate(...) -> Dict[str, Any]`

**Workflow:**

1. **Validation:**
   - Prompt must be non-empty
   - customer_id must be > 0

2. **Settings Extraction:**
   - Model (default: "veo-3.1-fast")
   - Duration (default: 5s)
   - Aspect ratio (default: "9:16")
   - Person generation, enhance prompt, number of videos
   - FPS, resolution, audio generation, compression quality
   - Reference images, last frame, mask, negative prompt

3. **Provider-Specific Configuration:**
   - **OpenAI Only:**
     - Extracts and validates poll_timeout_seconds (min: 1)
     - Extracts and validates poll_interval_seconds (min: 0.1)

4. **Mode Selection:**
   - **Text-to-Video:** Calls `provider.generate(prompt, model, **kwargs)`
   - **Image-to-Video:** Calls `provider.generate_from_image(prompt, image_url, **kwargs)`

5. **Storage:**
   - If `save_to_s3=True`: Uploads to S3 via `StorageService.upload_video()`
   - Returns S3 URL

6. **Metadata Assembly:**
   - Provider name, model, aspect ratio, duration
   - Mode (text_to_video|image_to_video)
   - All optional parameters that were provided

7. **Response Structure:**
   ```python
   {
       "video_url": str | None,           # S3 URL or None
       "video_bytes": bytes | None,       # Raw bytes if no S3 URL
       "model": str,
       "duration": int,
       "settings": {
           "provider": str,
           "model": str,
           "aspect_ratio": str,
           "duration_seconds": int,
           "mode": "text_to_video|image_to_video",
           "enhance_prompt": bool,
           "number_of_videos": int,
           ...additional_options
       }
   }
   ```

---

### 2.7 Video Provider Utilities

**Gemini Video Utilities:** `/home/user/betterai/docker/storage-backend/core/providers/video/utils/gemini/`

**Files:**
- `requests.py` - Request building
- `options.py` - Option validation/normalization
- `operations.py` - Execution and polling
- `assets.py` - Image preparation
- `sources.py` - Image fetching

**Key Functions:**

```python
# requests.py
async def build_generation_request(
    duration_seconds: Any,
    aspect_ratio: Any,
    kwargs: Mapping[str, Any],
    number_of_videos: int,
    available_aspect_ratios: set[str],
    available_person_generation: set[str],
    available_resolutions: set[str],
    prepare_image: ImagePreparer,
    resolve_reference_type: ResolveReferenceType,
    default_aspect_ratio: str,
) -> GeminiGenerationRequest
    # Builds and validates GenerateVideosConfig

# options.py
def clamp_duration(value: Any) -> int
    # Clamps duration to valid range

def normalise_aspect_ratio(
    value: Any,
    available: set[str],
    default: str
) -> str
    # Normalizes aspect ratio format

def resolve_resolution(value: Any, available: set[str]) -> Optional[str]
    # Maps friendly names to resolution values

def resolve_number_of_videos(value: Any) -> int
    # Validates number of videos

def resolve_reference_type(
    entry: Any,
    available_types: dict
) -> Optional[types.VideoGenerationReferenceType]
    # Resolves reference image types

# operations.py
async def execute_generation(
    client: Any,
    prompt: str,
    model: str,
    config: types.GenerateVideosConfig,
    poll_interval: int,
    timeout: int,
    image: Optional[types.Image] = None
) -> bytes
    # Executes generation and polls for completion
```

---

**OpenAI Video Utilities:** `/home/user/betterai/docker/storage-backend/core/providers/video/utils/openai/`

**Files:**
- `operations.py` - Job creation and polling
- `options.py` - Size/duration resolution
- `references.py` - Reference image preparation

**Key Functions:**

```python
# operations.py
async def create_video_job(
    client: Any,
    prompt: str,
    model: str,
    seconds: str,
    size: str,
    input_reference: Tuple[str, bytes, str] | None = None,
    provider_name: str = "openai_video",
    poll_timeout_seconds: int = 240,
    poll_interval_seconds: float = 5.0,
) -> Video
    # Creates job and polls until completion

async def download_video_bytes(
    client: Any,
    video: Video,
    provider_name: str = "openai_video"
) -> bytes
    # Downloads completed video bytes

# options.py
def resolve_seconds(
    duration: Any,
    allowed_values: tuple[int, ...]
) -> str
    # Finds nearest allowed duration value

def resolve_size(
    aspect_ratio: str,
    size_override: str | None,
    aspect_ratio_to_size: dict,
    available_sizes: set[str],
    resolution_presets: dict
) -> str
    # Resolves final video size

# references.py
async def prepare_input_reference(
    image_url: str,
    provider_name: str,
    target_size: tuple[int, int] | None
) -> Tuple[str, bytes, str]
    # Fetches, validates, and optionally resizes image
```

---

## 3. FRONTEND INTEGRATION

### 3.1 Frontend Hooks

#### A. Image Generation Hook

**File:** `/home/user/betterai/docker/storage-flowstudio/src/hooks/useImageGeneration.js`

**Export:** `useImageGeneration()`

**Returned Object:**
```javascript
{
    generateImages(options?: object): Promise<{ success: bool, error?: any }>
    regenerateImage(imageId: string, options?: object): Promise<...>
    editImage(imageId: string, userPrompt: string, options?: object): Promise<...>
    clearImageError(): void
    
    isImageGenerating: bool
    imageError: string | null
    lastImagePrompt: string | null
    requestInfo: {
        prompt: string,
        count: number,
        model: string,
        provider: string,
        startedAt: timestamp
    }
}
```

**Workflow:**
1. User calls `generateImages()` or `regenerateImage()`
2. Hook validates prompt from state or parameter
3. Constructs request with:
   - Prompt
   - Customer ID (resolved from env)
   - Base settings (from app state)
   - Options override
4. Calls `generateImagesRequest()` API function
5. Updates state on success/failure
6. Returns result promise

---

#### B. Video Generation Hook

**File:** `/home/user/betterai/docker/storage-flowstudio/src/hooks/useVideoGeneration.js`

**Export:** `useVideoGeneration()`

**Returned Object:**
```javascript
{
    generateVideo(overrides?: object): Promise<{ success: bool, video?: object, error?: any }>
    clearVideoError(): void
    
    isVideoGenerating: bool
    videoError: string | null
    latestRequest: {
        mode: string,
        prompt: string,
        startedAt: timestamp,
        completedAt?: timestamp,
        failedAt?: timestamp,
        settings: object,
        response?: object,
        error?: string
    }
}
```

**Modes:**
1. **Single Image Mode:** One image → animated video
2. **Start/End Mode:** Two images → transition video (Gemini only)
3. **Timeline Mode:** Multiple scenes with images → narrative video

**Workflow:**
1. User calls `generateVideo(overrides)`
2. Hook validates:
   - At least one scene with hero image
   - Scene selection based on mode
3. Builds narrative by combining:
   - Custom details
   - Latest assistant message
   - User input
   - Scene descriptions
   - Custom instructions
4. Constructs payload:
   - Prompt (narrative)
   - Customer ID
   - Settings with video config
   - Mode-specific parameters
5. Calls `generateVideoRequest()` API function
6. Normalizes response for consistent structure
7. Adds video to state
8. Updates request info with response/error

---

### 3.2 API Service

**File:** `/home/user/betterai/docker/storage-flowstudio/src/services/api.js`

#### Image Generation Request

```javascript
async generateImagesRequest({
    prompt,              // Required: string
    customerId,          // Required: int
    settings,            // Required: object
    options              // Optional: object
}) -> object
```

**HTTP Details:**
- Method: POST
- URL: `${API_BASE_URL}/image/generate`
- Headers: `Content-Type: application/json`

**Body Construction:**
```javascript
{
    prompt: prompt.trim(),
    customer_id: customerId ?? 1,
    settings: settings ?? {},
    save_to_db: true,
    ...options              // Merge options into root
}
```

**Response Processing:**
- Returns `response.data ?? response` (unwraps APIResponse wrapper)

**Error Handling:**
- Parses error from JSON or statusText
- Throws Error with message

---

#### Video Generation Request

```javascript
async generateVideoRequest(payload) -> object
```

**HTTP Details:**
- Method: POST
- URL: `${API_BASE_URL}/video/generate`
- Headers: `Content-Type: application/json`

**Request Payload Structure:**
```javascript
{
    prompt: string,
    customer_id: int,
    settings: {
        video: {
            model: string,
            duration_seconds: int,
            aspect_ratio: string,
            ...other_options
        }
    },
    input_image_url?: string,
    save_to_db: bool,
    scenes?: array,  // Timeline mode only
    mode: "single|start_end|timeline"
}
```

**Response Processing:**
- Returns `result.data ?? result` (unwraps APIResponse wrapper)
- Normalizes video object to consistent structure:
  ```javascript
  {
      id: string,
      url: string | null,
      thumbnail: string | null,
      prompt: string,
      provider: string,
      model: string,
      duration_seconds: int,
      aspect_ratio: string,
      resolution: string,
      timestamp: number,
      createdAt: number,
      metadata: object
  }
  ```

---

### 3.3 API Base Configuration

**Base URL Resolution:**
```javascript
API_BASE_URL = import.meta.env.VITE_BACKEND_HTTP_URL ??
               import.meta.env.VITE_API_URL ??
               'http://localhost:8000'
```

**Customer ID Resolution:**
```javascript
customerId = import.meta.env.VITE_CUSTOMER_ID ??
             import.meta.env.VITE_APP_CUSTOMER_ID ??
             '1'
```

---

## 4. SHARED UTILITIES & INFRASTRUCTURE

### 4.1 Base Provider Interface

**File:** `/home/user/betterai/docker/storage-backend/core/providers/base.py`

```python
class BaseImageProvider(ABC):
    capabilities: ProviderCapabilities
    provider_name: str  # Set by implementations
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        **kwargs: Any,
    ) -> bytes:
        """Generate an image and return bytes."""

class BaseVideoProvider(ABC):
    capabilities: ProviderCapabilities
    provider_name: str  # Set by implementations
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        **kwargs: Any,
    ) -> bytes:
        """Generate a video and return bytes."""
    
    async def generate_from_image(
        self,
        prompt: str,
        image_url: str,
        **kwargs: Any,
    ) -> bytes:
        """Generate a video from an image (optional)."""
        # Raises NotImplementedError if not supported
```

---

### 4.2 Storage Service

**File:** `/home/user/betterai/docker/storage-backend/infrastructure/aws/storage.py`

```python
class StorageService:
    async def upload_image(
        self,
        image_bytes: bytes,
        customer_id: int,
        file_extension: str = "png"
    ) -> str:
        """Upload image and return S3 URL."""
    
    async def upload_video(
        self,
        video_bytes: bytes,
        customer_id: int,
        file_extension: str = "mp4"
    ) -> str:
        """Upload video and return S3 URL."""
```

---

### 4.3 Provider Capabilities

**File:** `/home/user/betterai/docker/storage-backend/core/providers/capabilities.py`

```python
@dataclass
class ProviderCapabilities:
    streaming: bool = False           # Supports text streaming
    reasoning: bool = False           # Supports extended reasoning
    audio_input: bool = False         # Accepts audio input
    image_to_video: bool = False      # Supports image-to-video
    # ... other flags
```

---

### 4.4 Exception Hierarchy

**File:** `/home/user/betterai/docker/storage-backend/core/exceptions.py`

```python
class ProviderError(Exception):
    """Provider API or execution error."""
    def __init__(self, message: str, provider: str, original_error: Exception = None)

class ValidationError(Exception):
    """Input validation error."""
    def __init__(self, message: str, field: str = None)

class ConfigurationError(Exception):
    """Configuration or provider resolution error."""
    def __init__(self, message: str, key: str = None)

class ServiceError(Exception):
    """Service/storage error."""
```

---

### 4.5 AI Client Initialization

**File:** `/home/user/betterai/docker/storage-backend/core/clients/ai.py`

All AI SDKs are initialized at import time:

```python
ai_clients = {
    "openai": OpenAI(...),
    "openai_async": AsyncOpenAI(...),
    "gemini": genai.Client(...),
    "anthropic": Anthropic(...),
    "groq": Groq(...),
    # ... others
}
```

Available to providers via: `from core.clients.ai import ai_clients`

---

## 5. ERROR HANDLING

### 5.1 HTTP Status Codes

| Code | Scenario |
|------|----------|
| 200 | Success |
| 400 | ValidationError (empty prompt, invalid customer_id, config error) |
| 501 | NotImplementedError (unsupported provider/mode) |
| 502 | ProviderError (API failure) or ServiceError (storage failure) |
| 500 | Unexpected errors (logged with traceback) |

### 5.2 Error Response Format

```json
{
    "success": false,
    "data": null,
    "error": "Descriptive error message",
    "code": 400
}
```

---

## 6. ENVIRONMENT VARIABLES

### Required for Image Generation

| Variable | Default | Providers |
|----------|---------|-----------|
| `OPENAI_API_KEY` | - | OpenAI |
| `STABILITY_API_KEY` | - | Stability |
| `FLUX_API_KEY` | - | Flux |
| `FLUX_API_VERSION` | `v1` | Flux |
| `XAI_API_KEY` | - | xAI |
| `XAI_API_BASE_URL` | `https://api.x.ai/v1` | xAI |

### Required for Video Generation

| Variable | Default | Providers |
|----------|---------|-----------|
| `OPENAI_API_KEY` | - | OpenAI Sora |
| (Google SDK setup) | - | Gemini Veo |

### Frontend

| Variable | Default |
|----------|---------|
| `VITE_BACKEND_HTTP_URL` | `http://localhost:8000` |
| `VITE_API_URL` | `http://localhost:8000` |
| `VITE_CUSTOMER_ID` | `1` |
| `VITE_APP_CUSTOMER_ID` | `1` |

---

## 7. TOOL WRAPPING CONSIDERATIONS

When wrapping these systems as Claude MCP tools, consider:

1. **Image Generation Tool:**
   - Accept: prompt, provider, model, width, height, quality
   - Return: image_url, provider, model, metadata
   - Handle: Provider selection, validation, error messaging

2. **Video Generation Tool:**
   - Accept: prompt, provider, model, duration, aspect_ratio, mode, reference_image
   - Return: video_url, provider, model, duration, metadata
   - Handle: Mode selection, validation, polling (wait for completion)

3. **Provider Capabilities:**
   - Query available models per provider
   - Validate parameters before submission
   - Document supported options per provider

4. **Error Handling:**
   - Wrap exceptions in user-friendly messages
   - Include provider details for debugging
   - Implement retry logic for transient failures

5. **Async Operations:**
   - Video generation requires polling (handle in wrapper)
   - Implement timeout mechanisms
   - Return job IDs for long-running operations if needed

