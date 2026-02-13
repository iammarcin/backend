# storage-backend Main Database Handbook

**Last Updated:** 2026-01-12
**Scope:** How the backend connects to and operates on the PostgreSQL databases via Supabase.

## Overview

This handbook covers the PostgreSQL database architecture for storage-backend. The backend uses Supabase-hosted PostgreSQL with multiple schemas (aiapp, blood, ufc) accessed via asyncpg. Previous MySQL support was removed after full migration to PostgreSQL in January 2026.

---

## 1. Environment & Connection Management

### 1.1 Database Configuration

The backend uses PostgreSQL exclusively. Configuration is via environment variables: [F:storage-backend/config/environment.py]

| Variable | Purpose | Default |
|----------|---------|---------|
| `SUPABASE_HOST` or `SUPABASE_DB_HOST` | Supabase pooler hostname | - |
| `SUPABASE_DB_PASSWORD` or `SUPABASE_DB_PASS` | Database password | - |
| `SUPABASE_DB_USER` | Username | `postgres` |
| `SUPABASE_DB_PORT` | Port | `5432` |
| `SUPABASE_DB_NAME` | Database name | `postgres` |
| `SUPABASE_SSL_CERT_PATH` | Path to CA cert (optional) | - |

**Pool Tuning:**
- `DB_POOL_SIZE` - Connection pool size
- `DB_MAX_OVERFLOW` - Max overflow connections
- `DB_POOL_RECYCLE` - Connection recycle time (seconds)
- `DB_ECHO` - Enable SQL logging (true/false)

### 1.2 Schema Layout

Supabase uses a single database with multiple schemas: [F:storage-backend/config/database/urls.py]

```
postgres (database)
├── aiapp (schema)        → chat sessions, messages, prompts, users, garmin tables, session_summaries
├── aiapp_nonprod (schema)→ non-production garmin data
├── blood (schema)        → blood test results
└── ufc (schema)          → UFC fighter data
```

### 1.3 URL Building

URLs are built automatically with schema selection via `search_path`: [F:storage-backend/core/utils/config_helpers.py]

```python
# Format
"postgresql+asyncpg://postgres:pass@host:5432/postgres?options=-csearch_path%3Daiapp"
```

Direct URL overrides available: `MAIN_DB_URL`, `GARMIN_DB_URL`, `BLOOD_DB_URL`, `UFC_DB_URL`.

### 1.4 Engine Bootstrap

`infrastructure.db.mysql_engines` (filename kept for compatibility) creates engines and session factories: [F:storage-backend/infrastructure/db/mysql_engines.py]

- Extracts `search_path` from URL options and passes via `connect_args`
- Supports SSL for Supabase connections
- Lazy initialization - engines created on first use

### 1.5 Transactional Scope

All repositories accept an externally managed session and never call `commit`. The `session_scope` context manager commits/rolls back per request so multi-step mutations stay atomic.

---

## 2. ORM Model Snapshot

Declarative models in `features/chat/db_models` mirror the `aiapp` schema with SQLAlchemy 2.x typing: [F:storage-backend/features/chat/db_models/]

| Table | Purpose | Highlights |
|-------|---------|------------|
| `ChatSessionsNG` | Session metadata per customer | Auto-generated UUID `session_id`, JSON `tags`, last-update timestamps. |
| `ChatMessagesNG` | Every chat turn | Timers, attachment arrays, Claude metadata, GPS/audio flags. Ordered relationship back to session. |
| `Prompts` | Saved templates | Simple `title` + `prompt` pairs per customer. |
| `Users` | Auth records | Bcrypt hashed passwords, relationships for sessions/messages/prompts. |

### 2.1 DateTime Column Requirements

**All DateTime columns must use timezone-aware types:**

```python
from sqlalchemy import DateTime

# Correct - timezone-aware
calendar_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

# Wrong - will cause errors with asyncpg
calendar_date: Mapped[datetime] = mapped_column(DateTime, index=True)
```

PostgreSQL stores these as `timestamptz`. Using `DateTime` without `timezone=True` causes:
```
can't subtract offset-naive and offset-aware datetimes
```

**Tables using timezone-aware columns:**
- `ChatSessionsNG.last_update`
- `session_summaries.*` (first_message_date, last_message_date, generated_at, last_updated)
- `daily_health_events.*` (calendar_date, last_meal_time, last_drink_time, last_screen_time)
- All Garmin models (calendar_date columns)

Use `infrastructure.db.base.prepare_database` during tests to create tables against a disposable engine.

---

## 3. Repository Layer (Async CRUD)

Repositories in `features/chat/repositories/` handle persistence:

- **`ChatSessionRepository`** - creation, lookups, metadata updates, tag filtering, cascade deletes
- **`ChatMessageRepository`** - insert/update semantics, attachment handling, favorites, file filtering
- **`PromptRepository`** - prompt CRUD with optimistic updates
- **`UserRepository`** - bcrypt checks, raises `AuthenticationError` on failure

### 3.1 PostgreSQL Upsert Pattern

Upserts use PostgreSQL's `ON CONFLICT DO UPDATE`: [F:storage-backend/features/db/garmin/repositories/_base.py]

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

statement = pg_insert(model).values(**values)
statement = statement.on_conflict_do_update(
    index_elements=pk_columns,  # Primary key columns
    set_=update_columns         # Columns to update on conflict
)
```

**Note:** `index_elements` requires the exact primary key column names.

---

## 4. Service Orchestration

`ChatHistoryService` composes repositories into higher-level workflows: [F:storage-backend/features/chat/service_impl.py]

Key flows:
- **Message creation** - bootstraps session when `session_id` absent, inserts messages, updates metadata
- **Message editing** - retries missing messages by inserting replacement
- **Session listing/searching** - delegates to repositories, wraps results in typed payloads
- **Prompt management, favorites export, file audits** - reuse repository helpers

Services receive an open `AsyncSession`, enabling transactional composition.

---

## 5. HTTP Surface & Legacy Compatibility

`features/chat/routes.py` exposes REST endpoints under `/api/v1/chat`: [F:storage-backend/features/chat/routes.py]

- CRUD endpoints (`POST /messages`, `PATCH /messages`, `PUT /messages`, `DELETE /messages`)
- Session endpoints (`/sessions/list`, `/sessions/detail`, `/sessions/search`, `PATCH /sessions`)
- Prompt endpoints (`/prompts/list`, `/prompts`, etc.)
- Auth endpoint (`/auth/login`)
- Legacy dispatcher (`/api/v1/chat/legacy`) for old `MediaModel` automation

All use `_handle_service_error` for consistent 4xx/5xx responses.

---

## 6. Development & Debugging Tips

### Environment Setup

```bash
# Required for Supabase connection
export SUPABASE_HOST=xxx
export SUPABASE_DB_PASS=xxx

# Optional - defaults to hetzner behavior
export NODE_ENV=hetzner
# or explicitly
export DB_TYPE=postgresql
```

### Testing

Tests default to PostgreSQL (`DB_TYPE=postgresql` set in `tests/conftest.py`).

```bash
# Run all tests
docker exec -it backend pytest tests/

# Run specific feature tests
docker exec -it backend pytest tests/features/chat/
```

### Debugging

- Enable SQL logging: `DB_ECHO=true`
- Tail backend logs: `docker logs -f backend`
- Check connection issues via Supabase dashboard

### Connection Pooling

Supabase uses PgBouncer:
- Use session pooling mode for transactions
- Connection limits managed by Supabase
- Pool settings via `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`

---

## 7. Quick Reference

| Task | Steps |
|------|-------|
| Add new session metadata column | Update `ChatSession` model, extend `ChatSessionRepository.update_session_metadata`, expose via DTO + router. Run integration tests. |
| Attach analytics to message inserts | Extend `ChatMessageRepository.insert_message`, write tests that assert serialization via `chat_message_to_dict`. |
| Diagnose missing chat history | Enable `DB_ECHO`, call `/api/v1/chat/sessions/detail`, check logs for SQL/`DatabaseError`. |
| Migrate legacy worker to new endpoint | Translate payload into typed request model (`features/chat/schemas/requests.py`), call REST endpoint, validate envelope. |
| Add new DateTime column | Use `DateTime(timezone=True)` in model. Database column should be `timestamptz`. |
| Run upserts | Use `sqlalchemy.dialects.postgresql.insert` with `on_conflict_do_update()`. |

---

## 8. File Reference

| File | Purpose |
|------|---------|
| `config/environment.py` | Environment detection, `DATABASE_TYPE` constant |
| `config/database/urls.py` | URL building for PostgreSQL |
| `config/database/defaults.py` | Pool size, overflow, recycle defaults |
| `core/utils/config_helpers.py` | `build_postgresql_url()` helper |
| `infrastructure/db/mysql_engines.py` | Engine/session factory creation (name kept for compatibility) |
| `features/db/garmin/repositories/_base.py` | PostgreSQL upsert pattern |
| `features/chat/repositories/` | Chat CRUD repositories |
| `features/chat/service_impl.py` | Business logic orchestration |
| `features/chat/routes.py` | HTTP endpoints |

---

## 9. Migration History

**January 2026:** Completed migration from MySQL (AWS RDS) to PostgreSQL (Supabase).

Key changes during migration:
- Replaced `aiomysql` driver with `asyncpg`
- Converted `ON DUPLICATE KEY UPDATE` to `ON CONFLICT DO UPDATE`
- Added `DateTime(timezone=True)` to all timestamp columns
- Converted `timestamp without time zone` columns to `timestamptz` in database
- Replaced `GROUP_CONCAT` with PostgreSQL `string_agg`
- Replaced MySQL `DATE_SUB` with PostgreSQL interval syntax
- Fixed `json_length` to `jsonb_array_length`
- Named all Enum types explicitly for PostgreSQL compatibility

---

## References

- `DocumentationApp/migration-aws-to-hetzner-supabase.md` - Complete AWS to Supabase migration plan
- `DocumentationApp/storage-backend-ng-databases-others-handbook.md` - Garmin/Blood/UFC database details
