**Tags:** `#backend` `#database` `#garmin` `#health-data` `#mysql` `#fitness` `#sleep` `#activities` `#training` `#hrv`

# Garmin Health Data Storage

Multi-table ingestion and retrieval system for persisting Garmin health metrics including sleep, activities, training readiness, body composition, and lifestyle events.

## System Context

Part of the **storage-backend** database features (`features/db/`). This is the **storage layer** that persists data to MySQL. Works in conjunction with `features/garmin/` (the **API layer**) which fetches data from Garmin Connect.

**Data Flow:**
```
Garmin Connect API → features/garmin/ (fetch & translate) → features/db/garmin/ (persist)
```

## Database Models

### Daily Metrics
| Model | Purpose | Key Fields |
|-------|---------|------------|
| **UserSummary** | Daily aggregated metrics | calories, heart rate, stress, body battery, respiration |
| **BodyComposition** | Body measurements | weight, BMI, body fat %, water %, muscle mass |
| **HRVData** | Heart rate variability | weekly/nightly averages, status qualifiers |

### Sleep Data
| Model | Purpose | Key Fields |
|-------|---------|------------|
| **SleepData** | Single night analytics | sleep phases, duration, stress, body battery change, HRV |

### Activity Data
| Model | Purpose | Key Fields |
|-------|---------|------------|
| **ActivityData** | Activity summaries | type, duration, distance, HR, pace, training effect |
| **ActivityGPSData** | GPS tracks | Raw GPS samples as JSON |

### Training Metrics
| Model | Purpose | Key Fields |
|-------|---------|------------|
| **TrainingReadiness** | Daily readiness | score (0-100), level, recovery factors |
| **EnduranceScore** | Endurance classification | score, tier (Intermediate→Elite) |
| **TrainingStatus** | Load progression | daily/chronic loads, VO2 max, balance |
| **FitnessAge** | Fitness vs chronological age | fitness age, contributing factors |

### Lifestyle
| Model | Purpose | Key Fields |
|-------|---------|------------|
| **DailyHealthEvents** | Event timestamps | last meal, drink, screen time |

## Architecture

```
features/db/garmin/
├── service.py              # GarminService (mixin-based)
├── ingestion.py            # GarminIngestionMixin (ingest_* methods)
├── retrieval.py            # GarminRetrievalMixin (fetch_dataset, etc.)
├── datasets.py             # DatasetRegistry for table metadata
├── date_windows.py         # Date range helpers
├── timestamps.py           # Timestamp normalization
├── activity_aggregation.py # Activity processing
├── sleep_processing.py     # Sleep analytics
├── db_models/
│   ├── summary.py          # UserSummary, BodyComposition, HRVData
│   ├── sleep.py            # SleepData
│   ├── activities.py       # ActivityData, ActivityGPSData
│   ├── training.py         # Training metrics models
│   └── lifestyle.py        # DailyHealthEvents
└── repositories/
    ├── _base.py            # GarminRepository (upsert/fetch)
    ├── sleep.py            # GarminSleepRepository
    ├── summary.py          # GarminSummaryRepository
    ├── training.py         # GarminTrainingRepository
    └── activity.py         # GarminActivityRepository
```

## Service Layer

**GarminService** uses mixin composition:

```python
class GarminService(GarminIngestionMixin, GarminRetrievalMixin):
    # Composes ingestion + retrieval capabilities
```

**Ingestion Methods:**
- `ingest_sleep()`, `ingest_user_summary()`, `ingest_body_composition()`
- `ingest_hrv()`, `ingest_activity()`, `ingest_activity_gps()`
- `ingest_training_readiness()`, `ingest_endurance_score()`
- `ingest_training_status()`, `ingest_fitness_age()`
- `ingest_daily_health_events()`

**Retrieval Methods:**
- `fetch_dataset()` - Generic fetch with DatasetConfig lookup
- `available_datasets()` - List supported datasets
- `default_analysis_datasets()` - Default analysis set

## Repository Pattern

**GarminRepository Base:**
- `_upsert()` - MySQL INSERT...ON DUPLICATE KEY UPDATE
- `_fetch()` - Query builder with date range, pagination, ordering

**Concrete Repositories:**
- `GarminSleepRepository` - Sleep records
- `GarminSummaryRepository` - Daily summaries + wellness
- `GarminActivityRepository` - Activities + GPS
- `GarminTrainingRepository` - Training metrics

## Configuration

**Environment Variables:**
- `GARMIN_DB_URL` - MySQL connection string

**All models indexed on:**
- `customer_id` - Multi-tenant isolation
- `calendar_date` - Date-based queries

## Related Feature

See `features/garmin/CLAUDE.md` for the API layer that fetches data from Garmin Connect and calls this storage layer for persistence.
