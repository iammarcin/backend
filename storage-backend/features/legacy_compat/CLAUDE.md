**Tags:** `#backend` `#legacy` `#api` `#mobile-api` `#kotlin`

# Legacy API Endpoints

Database and file upload endpoints at the original /api/db and /api/aws paths. These endpoints use the same canonical snake_case field names as all other endpoints.

## System Context

Part of the **storage-backend** FastAPI service. These endpoints exist at legacy paths for historical reasons but follow the same snake_case conventions as the rest of the API.

## API Endpoints

### POST /api/db
Legacy database operations for chat history.

**Supported Actions:**
| Action | Purpose | Handler |
|--------|---------|---------|
| `db_search_messages` | Search/list sessions (no messages) | `handle_db_search_messages()` |
| `db_all_sessions_for_user` | Get all sessions WITH messages | `handle_db_all_sessions_for_user()` |
| `db_get_user_session` | Get specific session with messages | `handle_db_get_user_session()` |
| `db_new_message` | Create new message(s) | `handle_db_new_message()` |

**Request Format:**
```json
{
  "action": "db_search_messages",
  "user_input": { /* action-specific params */ },
  "user_settings": { /* settings */ }
}
```
Note: `customer_id` is extracted from the validated JWT token, not from the request body.

### POST /api/aws
S3 file upload endpoint at legacy path.

**Content-Type:** `multipart/form-data`

**Allowed Extensions:**
- Images: jpg, jpeg, png, gif, webp
- Audio: mp3, pcm, mpeg, mpga, wav, m4a, opus, webm
- Video: mp4
- Documents: txt, pdf

## Architecture

```
features/legacy_compat/
├── routes.py           # /api/db, /api/aws endpoints
├── aws_handlers.py     # S3 upload handling
├── db_handlers.py      # Database operation handlers
├── converters.py       # Modern → legacy format conversion
├── response_helpers.py # Legacy response envelope
└── __init__.py
```

## Request Flow

```
Request (snake_case)
    ↓
Extract + Parse (routes.py)
    ↓
Call Service (ChatHistoryService, StorageService)
    ↓
Format Response (converters.py)
    ↓
Response Envelope
```

## Response Envelopes

**Success:**
```json
{
  "success": true,
  "code": 200,
  "message": {
    "status": "completed",
    "result": { /* data */ }
  }
}
```

**Error:**
```json
{
  "success": false,
  "code": 400,
  "message": {
    "status": "fail",
    "result": "Error description"
  }
}
```

## Key Converters

**session_to_legacy_format():**
- Maps `ChatSessionPayload` → legacy session dict
- Optional `include_messages` flag
- Defensive null coalescing with defaults

**message_to_legacy_format():**
- Maps `ChatMessagePayload` → legacy message dict
- **Dual field compatibility:** Both `file_locations` AND `file_names` contain URLs
  - `file_locations` - React ChatMessage.js
  - `file_names` - Kotlin mobile client

## Authentication

- JWT bearer token required in `Authorization` header
- Validated via `core.auth.authenticate_bearer_token()`
- `customer_id` extracted from validated token payload (not from request body)
- Returns 401 if token is missing, expired, or invalid

## Error Codes

| Code | Cause |
|------|-------|
| 400 | Invalid JSON, validation errors, unsupported action |
| 401 | Missing, expired, or invalid JWT token |
| 500 | Unexpected errors |
| 503 | Database connection errors |

## Dependencies

- `ChatHistoryService` - Modern chat history operations
- `StorageService` - S3 file uploads

## Maintenance Notes

- Response format follows standard API envelope structure
- Extension whitelist may need updates for new file types
- All field names use canonical snake_case
