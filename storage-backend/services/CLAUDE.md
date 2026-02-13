# Services Layer

**Tags:** `#backend` `#services` `#temporary-storage` `#file-upload` `#audio` `#transcription` `#fastapi` `#uploadfile` `#tempfile` `#async`

## System Context

This is the **services layer** of the BetterAI FastAPI backend. It provides shared application-level utilities that bridge the gap between feature modules and infrastructure. Services here are stateless helpers consumed by multiple features but don't belong to any single domain.

**Architectural position:** `features/` → `services/` → `infrastructure/`

---

## Temporary Storage (`temporary_storage.py`)

### Purpose

Handles temporary file persistence for uploaded content that requires disk access before processing. Primary use case: audio files uploaded for transcription that need to be written to disk before being sent to speech-to-text providers (Deepgram, OpenAI Whisper, Gemini).

### Why Temporary Storage?

FastAPI's `UploadFile` is an in-memory/spooled file object. Some downstream services require:
- File path on disk (not file-like objects)
- Persistent access across async operations
- Organized storage by customer for debugging/cleanup

### Key Components

**`StoredUpload` dataclass:**
```python
@dataclass(slots=True)
class StoredUpload:
    path: Path       # Absolute path to temp file
    filename: str    # Original filename
    content_type: str | None  # MIME type

    def open(self, mode: str = "rb"):
        """Open the stored file for downstream consumers."""
```

**`persist_upload_file()` function:**
```python
async def persist_upload_file(
    upload: UploadFile,
    *,
    customer_id: int,
    category: str = "audio",
    prefix: str = "upload_",
) -> StoredUpload
```

### Storage Location

Files are organized under system temp directory:
```
/tmp/storage-backend-ng/{customer_id}/{category}/{prefix}{random}{suffix}
```

Example:
```
/tmp/storage-backend-ng/123/audio/upload_abc123.mp3
```

### Usage Pattern

Typical usage in audio transcription flow:

```python
from services.temporary_storage import persist_upload_file

# In a FastAPI route handling audio upload
stored = await persist_upload_file(
    upload_file,
    customer_id=user.id,
    category="audio",
    prefix="transcribe_"
)

# Pass to transcription service
try:
    result = await transcriber.transcribe(stored.path)
finally:
    # Cleanup (caller's responsibility)
    stored.path.unlink(missing_ok=True)
```

### Implementation Details

- **Async-safe:** Uses `asyncio.to_thread()` for blocking I/O operations
- **Directory creation:** Auto-creates customer/category directories
- **Extension preservation:** Maintains original file extension from upload
- **Binary handling:** Handles both bytes and string content

### Consumers

Primary consumers within the backend:
- `features/audio/` - Speech-to-text transcription uploads
- Any feature requiring disk-based file processing

### Cleanup Responsibility

**Important:** This service does NOT handle cleanup. Callers must delete temporary files after processing:

```python
import os
os.unlink(stored.path)
# or
stored.path.unlink(missing_ok=True)
```

### Exports

```python
__all__ = ["persist_upload_file", "StoredUpload"]
```

---

## Design Rationale

### Why Not Use Infrastructure Layer?

Temporary storage is application-level logic, not external service integration:
- No external credentials or connections
- No network calls
- Pure local filesystem operations
- Consumed by features, not infrastructure

### Why Separate from Features?

- Used by multiple features (audio, potentially others)
- Generic utility, not domain-specific
- Keeps feature modules focused on business logic
