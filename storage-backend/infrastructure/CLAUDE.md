# Infrastructure Layer

**Tags:** `#backend` `#infrastructure` `#aws` `#s3` `#sqs` `#database` `#mysql` `#sqlalchemy` `#async` `#connection-pooling` `#boto3`

## System Context

This is the **infrastructure layer** of the BetterAI FastAPI backend. It provides low-level integrations with external services (AWS, MySQL databases) that are consumed by feature modules and core services. The infrastructure layer sits at the bottom of the dependency hierarchy - features and core modules depend on it, but it has no knowledge of business logic.

**Architectural position:** `features/` → `core/` → `infrastructure/`

---

## AWS Integration (`aws/`)

### Overview

Provides S3 object storage and SQS message queue capabilities via boto3 clients. Used throughout the backend for persisting generated assets (images, videos, TTS audio) and user-uploaded attachments.

### Files

| File | Purpose |
|------|---------|
| `clients.py` | Boto3 client initialization (S3, SQS) with retry configuration |
| `storage.py` | `StorageService` class for S3 uploads |
| `queue.py` | `SqsQueueService` class for message enqueueing |

### Client Initialization (`clients.py`)

- Clients initialized at **import time** (not lazy)
- Uses static AWS credentials from environment variables
- Retry configuration: 3 attempts, standard mode
- Timeouts: 10s connect, 30s read
- Exposes `get_s3_client()` and `get_sqs_client()` accessors

**Required environment variables:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (from core.config)

### S3 Storage Service (`storage.py`)

`StorageService` handles all S3 uploads with consistent key generation and URL construction.

**Key methods:**
- `upload_image()` - Generated images (PNG, etc.)
- `upload_video()` - Generated videos (MP4, etc.)
- `upload_audio()` - TTS audio files (MP3, etc.)
- `upload_chat_attachment()` - User file uploads

**S3 key structure:**
```
{customer_id}/assets/chat/{discussion_id}/{timestamp}_{uuid}_{category}.{ext}
```

**Usage pattern:**
```python
from infrastructure.aws.storage import StorageService

storage = StorageService()
url = await storage.upload_image(
    image_bytes=data,
    customer_id=123,
    file_extension="png"
)
```

**Configuration:**
- `IMAGE_S3_BUCKET` - Target bucket name
- Returns public URLs in format: `https://{bucket}.s3.{region}.amazonaws.com/{key}`

### SQS Queue Service (`queue.py`)

`SqsQueueService` sends JSON payloads to SQS queues with optional FIFO support.

**Key methods:**
- `enqueue()` - Send JSON payload to queue
- `enqueue_timestamped_payload()` - Adds `created_at` timestamp automatically

**FIFO queue support:**
- `message_group_id` - For message ordering
- `message_deduplication_id` - Prevent duplicates
- `delay_seconds` - Delayed delivery

**Configuration:**
- `AWS_SQS_QUEUE_URL` - Target queue URL

---

## Database Layer (`db/`)

### Overview

Manages async SQLAlchemy connections to **four separate MySQL databases**. Provides engine creation, session factories, and FastAPI dependency injection integration.

### Files

| File | Purpose |
|------|---------|
| `mysql.py` | Engine/session factory management for 4 databases |
| `base.py` | SQLAlchemy `DeclarativeBase` for ORM models |

### Four Database Architecture

The application uses domain-isolated databases:

| Database | Env Variable | Purpose |
|----------|--------------|---------|
| **Main** | `MAIN_DB_URL` | Chat sessions, messages, users, prompts |
| **Garmin** | `GARMIN_DB_URL` | Health/fitness data from Garmin Connect |
| **Blood** | `BLOOD_DB_URL` | Medical blood test results |
| **UFC** | `UFC_DB_URL` | UFC fighter data and subscriptions |

**Why separate databases?**
- Domain isolation and security boundaries
- Independent scaling and backup strategies
- Different data retention policies
- Some databases shared with other services

### Connection Pool Settings

All databases use identical pool configuration:
- `pool_size=10` - Base connections
- `max_overflow=10` - Additional connections under load
- `pool_recycle=900` - Recycle connections every 15 minutes
- `pool_pre_ping=True` - Automatic reconnection
- `isolation_level="READ COMMITTED"`
- `connect_timeout=5` seconds

### Session Management Pattern

**Engine/factory pairs created at import:**
```python
main_engine, main_session_factory = _initialise_engine(...)
garmin_engine, garmin_session_factory = _initialise_engine(...)
blood_engine, blood_session_factory = _initialise_engine(...)
ufc_engine, ufc_session_factory = _initialise_engine(...)
```

**FastAPI dependency injection:**
```python
from infrastructure.db.mysql import main_session_factory, get_session_dependency

get_main_session = get_session_dependency(main_session_factory)

@router.post("/endpoint")
async def handler(session: AsyncSession = Depends(get_main_session)):
    # Session auto-commits on success, auto-rollback on error
    ...
```

**Manual session scope (outside FastAPI):**
```python
from infrastructure.db.mysql import main_session_factory, session_scope

async with session_scope(main_session_factory) as session:
    # Automatic commit/rollback handling
    ...
```

### Key Exports

- `main_session_factory`, `garmin_session_factory`, `blood_session_factory`, `ufc_session_factory`
- `main_engine`, `garmin_engine`, `blood_engine`, `ufc_engine`
- `get_session_dependency()` - Creates FastAPI dependency from factory
- `session_scope()` - Context manager for manual session handling
- `require_main_session_factory()`, `require_garmin_session_factory()` - Fail-fast accessors

### ORM Base (`base.py`)

Provides shared `DeclarativeBase` for all ORM models:
```python
from infrastructure.db.base import Base

class MyModel(Base):
    __tablename__ = "my_table"
    ...
```

---

## Error Handling

Both AWS and DB modules raise typed exceptions from `core.exceptions`:
- `ConfigurationError` - Missing credentials, URLs, bucket names
- `ServiceError` - Runtime failures (upload failed, enqueue failed)
- `DatabaseError` - SQLAlchemy operation failures

---

## Testing Considerations

- AWS clients can be injected via constructor for mocking
- Session factories can be overridden in FastAPI test fixtures
- No automatic migrations - models reflect existing schema
- Engines may be `None` if environment variables not set
