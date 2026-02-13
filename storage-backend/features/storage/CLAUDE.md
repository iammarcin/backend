**Tags:** `#backend` `#storage` `#s3` `#file-upload` `#attachments` `#aws` `#multipart`

# Storage Feature

S3-backed file attachment upload system with comprehensive validation, error handling, and multi-tenant asset management.

## System Context

Part of the **storage-backend** FastAPI service. Provides file upload capabilities for chat attachments, generated assets (TTS, images, videos), and user-uploaded files.

## API Endpoint

**POST /api/v1/storage/upload**
- **Content-Type:** `multipart/form-data`
- **Authentication:** JWT token required
- **Response:** `ApiResponse[Dict[str, str]]`

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | File | Yes | Uploaded file (multipart) |
| `category` | string | Yes | File category label |
| `action` | string | Yes | Action description |
| `customerId` | int | Yes | Customer ID |
| `userInput` | JSON string | No | Contains `force_filename` flag |
| `userSettings` | JSON string | No | Settings object |
| `assetInput` | JSON string | No | Asset metadata |

## Allowed Extensions

| Category | Extensions |
|----------|------------|
| Images | jpg, jpeg, png, gif, webp |
| Audio | mp3, pcm, mpeg, mpga, wav, m4a, opus, webm |
| Video | mp4 |
| Documents | txt, pdf |

## Response Format

**Success (200):**
```json
{
  "code": 200,
  "success": true,
  "message": "File uploaded successfully",
  "data": {
    "url": "https://bucket.s3.region.amazonaws.com/123/assets/chat/1/20251123_abc12345_file.jpg",
    "result": "https://...",
    "filename": "20251123_abc12345_file.jpg"
  },
  "meta": {
    "category": "image",
    "action": "upload",
    "extension": "jpg",
    "content_type": "image/jpeg"
  }
}
```

**Error Responses:**
| Status | Cause |
|--------|-------|
| 400 | Invalid JSON, unsupported extension, empty file |
| 502 | S3 upload failure |
| 500 | Unexpected error |

## Architecture

```
features/storage/
├── routes.py       # POST /upload endpoint (~186 lines)
├── dependencies.py # get_storage_service()
└── __init__.py     # Exports router

infrastructure/aws/storage.py
└── StorageService  # S3 operations
```

## S3 Path Organization

```
S3 Bucket:
├── {customer_id}/
│   └── assets/
│       ├── chat/
│       │   └── 1/                    # DEFAULT_DISCUSSION_ID
│       │       ├── 20251123_abc1_file.jpg
│       │       └── ...
│       ├── tts/
│       ├── image/
│       └── video/
```

## Filename Generation

**Default (force_filename=false):**
```
{timestamp}_{uuid8}_{safe_name}
20251123_a1b2c3d4_filename.jpg
```

**With force_filename=true:**
```
{safe_name}
filename.jpg
```

**Filename Sanitization:**
- Replaces unsafe characters with underscore
- Pattern: `re.sub(r"[^A-Za-z0-9._-]", "_", filename)`

## Upload Flow

```
1. Receive multipart form data
2. Parse JSON fields (userInput, userSettings, assetInput)
3. Validate file extension against allowlist
4. Read file content into memory
5. Validate non-empty content
6. Generate S3 key with timestamp + UUID
7. Upload to S3 with public-read ACL
8. Return public URL
```

## StorageService Methods

**upload_chat_attachment():**
- File bytes → S3
- Returns public URL
- Handles content-type detection

**Other Methods (used by other features):**
- `upload_audio()` - TTS audio files
- `upload_image()` - Generated images
- `upload_video()` - Generated videos

## Configuration

**Environment Variables:**
- `IMAGE_S3_BUCKET` - S3 bucket name
- `AWS_REGION` - AWS region for URL construction
- `AWS_ACCESS_KEY_ID` - AWS credentials
- `AWS_SECRET_ACCESS_KEY` - AWS credentials

**Constants:**
- `DEFAULT_DISCUSSION_ID = 1` - Hardcoded in paths
- `_DEFAULT_ATTACHMENT_ACL = "public-read"` - File permissions

## Security

- **Authentication:** JWT token via `require_auth_context`
- **Extension Whitelist:** Only allowed file types accepted
- **Customer Isolation:** Files organized by customer_id
- **Public ACL:** Files publicly readable via S3 URL

## Dependencies

- `boto3` - AWS S3 client
- `core/auth` - JWT authentication
- `core/pydantic_schemas/api_envelope.py` - Response formatting
