**Tags:** `#backend` `#database` `#mysql` `#sqlalchemy` `#health-data` `#blood-tests` `#garmin-storage` `#ufc`

# Database Features Overview

Container directory for database-backed domain features that persist specialized data to dedicated MySQL databases.

## System Context

Part of the **storage-backend** FastAPI service. This directory contains three distinct sub-features, each operating on its own MySQL database for data isolation and scalability.

## Sub-Features

| Feature | Database | Purpose | Documentation |
|---------|----------|---------|---------------|
| **blood** | `BLOOD_DB_URL` | Blood test result tracking | `db/blood/CLAUDE.md` |
| **garmin** | `GARMIN_DB_URL` | Garmin health metrics storage | `db/garmin/CLAUDE.md` |
| **ufc** | `UFC_DB_URL` | UFC fighter data management | `db/ufc/CLAUDE.md` |

## Database Architecture

**Four Separate MySQL Databases:**
- `MAIN_DB_URL` - Chat sessions, messages, prompts, users (in `features/chat/`)
- `BLOOD_DB_URL` - Blood test results
- `GARMIN_DB_URL` - Garmin health metrics
- `UFC_DB_URL` - UFC fighter data

**Session Management:**
- Engines created at import in `infrastructure/db/mysql.py`
- FastAPI dependencies yield scoped sessions
- Repositories never commit - handled by dependency scope
- Missing DB URLs raise `ConfigurationError` on first access

## Common Patterns

All sub-features follow consistent architecture:

**Dependency Injection:**
```python
get_<feature>_session()      # Async session factory
get_<feature>_repositories() # Repository collection
get_<feature>_service()      # Service with repositories
```

**Repository Pattern:**
- Repositories handle database operations only
- Services orchestrate business logic
- Routes call services, not repositories directly

**Error Response Envelope:**
```python
api_ok(message, data, meta)    # Success response
api_error(code, message, data) # Error response
```

## Directory Structure

```
db/
├── __init__.py           # Module exports
├── CLAUDE.md             # This file
├── blood/                # Blood test tracking
│   ├── CLAUDE.md
│   ├── routes.py
│   ├── service.py
│   ├── db_models.py
│   └── repositories/
├── garmin/               # Garmin health storage
│   ├── CLAUDE.md
│   ├── service.py
│   ├── ingestion.py
│   ├── retrieval.py
│   ├── db_models/
│   └── repositories/
└── ufc/                  # UFC fighter data
    ├── CLAUDE.md
    ├── routes*.py
    ├── db_models.py
    ├── service/
    └── repositories/
```

## Relationship to features/garmin/

**Important Distinction:**
- `features/db/garmin/` - **Storage Layer** - Persists health data to database
- `features/garmin/` - **API Layer** - Fetches data from Garmin Connect API

The API layer (`features/garmin/`) fetches data from external Garmin APIs, translates it, and optionally persists via the storage layer (`features/db/garmin/`). See each feature's CLAUDE.md for details.

## Adding New Database Features

1. Create sub-directory: `features/db/<name>/`
2. Define ORM models in `db_models.py`
3. Create repository layer
4. Implement service with repositories
5. Add routes with dependency injection
6. Configure database URL in environment
7. Add `CLAUDE.md` documentation
