**Tags:** `#backend` `#garmin` `#health-api` `#fitness` `#activities` `#sleep` `#training` `#withings` `#data-translation`

# Garmin API Feature

Provider service that fetches raw health data from Garmin Connect API, translates payloads into normalized schemas, validates data, and optionally persists to the Garmin database.

## System Context

Part of the **storage-backend** FastAPI service. This is the **API layer** that interfaces with external Garmin Connect APIs. Works in conjunction with `features/db/garmin/` (the **storage layer**) for persistence.

**Data Flow:**
```
Garmin Connect API → fetch → translate → validate → persist (optional)
         ↓                                              ↓
   features/garmin/                           features/db/garmin/
```

## API Endpoints

All endpoints under `/api/v1/garmin` prefix:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/status` | GET | Provider metadata, available datasets |
| `/activities` | POST | Persist enriched activities |
| `/analysis/overview` | GET | Aggregated datasets for dashboards |
| `/activity/{id}` | GET | Raw GPS metrics and details |
| `/activity/{id}/weather` | GET | Weather conditions during activity |
| `/activity/{id}/hr-zones` | GET | Heart rate zone distribution |

### Dynamic Dataset Routes (13 total)

| Route | Dataset Key | Requires Activity ID |
|-------|-------------|----------------------|
| `/sleep` | sleep | No |
| `/summary` | summary | No |
| `/body-composition` | body_composition | No |
| `/hrv` | hrv | No |
| `/training-readiness` | training_readiness | No |
| `/endurance-score` | training_endurance | No |
| `/training-status` | training_status | No |
| `/training-load-balance` | training_load_balance | No |
| `/fitness-age` | training_fitness_age | No |
| `/activities` | activity | No |
| `/activity-gps` | activity_gps | Yes |
| `/daily-health-events` | daily_health_events | No |
| `/max-metrics` | max_metrics | No |

## Architecture

```
features/garmin/
├── routes.py               # Main endpoints
├── routes_datasets.py      # Dynamic dataset routes
├── routes_common.py        # Shared utilities, error handling
├── service.py              # GarminProviderService orchestration
├── dependencies.py         # FastAPI DI
├── dataset_registry.py     # DatasetConfig mapping
├── dataset_fetchers.py     # Low-level API fetchers
├── settings.py             # Provider configuration
├── types.py                # TypedDicts for Garmin payloads
├── results.py              # IngestResult dataclass
├── schemas/
│   ├── base.py             # GarminRequest base class
│   ├── queries.py          # GarminDataQuery params
│   ├── activity.py         # ActivityRequest with enrichment
│   ├── sleep.py            # Sleep schemas
│   ├── wellness.py         # Training, body composition
│   └── internal.py         # Persisted DTOs
└── translators/
    ├── activity.py         # Activity payload translation
    ├── summaries.py        # Sleep, summary translation
    ├── training.py         # Training status, load balance
    ├── recovery.py         # HRV, training readiness
    ├── performance.py      # Endurance, fitness age
    ├── body_composition.py # Garmin + Withings merge
    ├── metrics.py          # VO2 max metrics
    ├── weather.py          # Weather normalization
    └── utils.py            # Payload traversal helpers
```

## Data Pipeline

```
1. Dataset Request → GarminProviderService.fetch_dataset()
2. Fetcher() → Raw Garmin API response
3. Translator() → Normalized dictionaries
4. Validator() → Pydantic GarminRequest instances
5. Ingest() → GarminService (db/garmin) persistence
6. Return DatasetResult with items, metadata
```

## Key Components

### GarminProviderService
Main coordinator:
- Validates dataset exists in registry
- Calls fetcher for raw data
- Applies translator for normalization
- Validates against Pydantic schemas
- Optionally persists via GarminService

### Dataset Registry
Maps dataset names to runtime configurations:
```python
DatasetConfig(
    translator=translate_sleep,
    schema=SleepIngestRequest,
    ingest_method="ingest_sleep",
    fetcher=fetch_sleep,
)
```

### Translators
Normalize Garmin API responses:
- Extract nested fields
- Coerce dates to consistent format
- Flatten complex structures
- Handle missing/optional fields

### Withings Integration
Body composition fetcher merges Garmin + Withings data:
- Dual-source payload: `{"garmin": ..., "withings": ...}`
- Translator merges on `calendar_date`
- Optional: controlled via WithingsClient availability

## Query Parameters

**GarminDataQuery:**
- `start_date`, `end_date` - Date range (YYYY-MM-DD)
- `target_date` - For VO2 backfill
- `sort` - asc/desc for calendar_date
- `limit`, `offset` - Pagination
- `source` - "garmin" (API) or "database" (skip API)
- `activity_id` - Filter to specific activity

## Error Handling

| Exception | Status | Cause |
|-----------|--------|-------|
| `ConfigurationError` (GARMIN_ENABLED) | 503 | Feature disabled |
| `ConfigurationError` (other) | 500 | Missing config |
| `ValidationError` | 422 | Schema validation failed |
| `ProviderError` | 502 | Garmin API error |

## Configuration

**Environment Variables:**
- `GARMIN_USERNAME`, `GARMIN_PASSWORD` - Garmin Connect credentials
- `GARMIN_DB_URL` - Database connection (for persistence)
- `WITHINGS_CLIENT_ID`, `WITHINGS_CLIENT_SECRET` - Optional Withings

**Feature Flag:**
- `settings.garmin_enabled` - Enable/disable entire feature

## Related Feature

See `features/db/garmin/CLAUDE.md` for the storage layer that persists data fetched by this API layer.
