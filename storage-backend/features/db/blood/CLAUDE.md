**Tags:** `#backend` `#database` `#blood-tests` `#health-data` `#mysql` `#medical-records` `#lab-results`

# Blood Test Tracking Feature

Read-only, filter-aware blood test result tracking system for storing and querying lab test results with optional metadata.

## System Context

Part of the **storage-backend** database features (`features/db/`). Operates on a dedicated MySQL database (`BLOOD_DB_URL`) separate from the main chat database for data isolation.

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/blood/tests` | GET | List blood test records with optional filters |
| `/api/v1/blood/legacy` | POST | Legacy automation payload compatibility |

### GET /api/v1/blood/tests

**Query Parameters:**
- `start_date` (date, optional) - Minimum test date
- `end_date` (date, optional) - Maximum test date
- `category` (string, optional) - Filter by test category (e.g., "Lipids", "Immune")
- `limit` (int, 1-500, optional) - Max records to return

**Response:**
```json
{
  "status": "ok",
  "data": {
    "items": [/* BloodTestItem[] */],
    "total": 42,
    "latest_date": "2025-01-15",
    "filters_applied": {"category": "Lipids"}
  }
}
```

## Database Models

### TestDefinition
Reference table for supported blood test types:
- `id` (int, PK)
- `category` (string) - e.g., "Lipids", "Immune", "Metabolic"
- `test_name` (string, unique) - Test identifier
- `short_explanation`, `long_explanation` (text) - Descriptions

### BloodTest
Individual blood test results:
- `id` (int, PK)
- `test_date` (date, indexed) - When test was performed
- `test_definition_id` (FK to TestDefinition)
- `result_value` (string) - Test result
- `result_unit` (string) - e.g., "mg/dL", "mmol/L"
- `reference_range` (string) - Normal range

## Architecture

```
features/db/blood/
├── routes.py           # HTTP endpoints
├── service.py          # BloodService business logic
├── db_models.py        # SQLAlchemy ORM models
├── dependencies.py     # FastAPI DI (session, service)
├── types.py            # BloodTestRow TypedDict
├── repositories/
│   └── tests.py        # BloodTestRepository (read-only)
└── schemas/
    ├── requests.py     # BloodTestListQueryParams
    ├── responses.py    # Response envelopes
    └── internal.py     # BloodTestFilterParams
```

## Service Layer

**BloodService:**
- `list_tests()` - Fetch tests, apply filters, compute metadata
- Filters applied client-side after DB fetch for flexibility
- Returns latest test date and total count

**BloodTestRepository:**
- `list_tests()` - Async read with eager loading of TestDefinition
- Orders by `test_date DESC`, then `id DESC`
- Returns enriched `BloodTestRow` with category and test name

## Data Flow

```
GET /api/v1/blood/tests?category=Lipids&limit=30
    ↓
BloodService.list_tests(filters)
    ↓
BloodTestRepository.list_tests() → eager load TestDefinition
    ↓
Apply client-side filters (date, category)
    ↓
Apply limit, compute metadata
    ↓
Return BloodTestListEnvelope
```

## Configuration

**Environment Variables:**
- `BLOOD_DB_URL` - MySQL connection string for blood database

**Dependencies:**
- `get_blood_session()` - Async session factory
- `get_blood_service()` - Service with repositories wired
