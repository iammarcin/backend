**Tags:** `#backend` `#database` `#ufc` `#fighters` `#mma` `#subscriptions` `#authentication` `#mysql`

# UFC Fighter Data Feature

Complete fighter database with user authentication, subscription management, and fighter metadata including fight scheduling and social links.

## System Context

Part of the **storage-backend** database features (`features/db/`). Operates on a dedicated MySQL database (`UFC_DB_URL`) for UFC-specific data separate from other systems.

## API Endpoints

### Fighter Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/ufc/fighters` | GET | List fighters with pagination and subscription status |
| `/api/v1/ufc/fighters` | POST | Create new fighter |
| `/api/v1/ufc/fighters/{fighter_id}` | PUT | Update fighter details |
| `/api/v1/ufc/fighters/queue` | POST | Queue fighter candidate for async processing |

### Authentication Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/ufc/auth/login` | POST | Authenticate user |
| `/api/v1/ufc/auth/register` | POST | Register new user |
| `/api/v1/ufc/auth/user-exists` | GET | Check if email exists |
| `/api/v1/ufc/auth/user/{email}` | GET | Get user profile |

### Subscription Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/ufc/subscriptions/toggle` | POST | Subscribe/unsubscribe user from fighter |
| `/api/v1/ufc/subscriptions/summaries` | GET | List all user subscriptions |

## Database Models

### Fighter
UFC fighter metadata with fight scheduling:
- `name`, `ufc_url` (unique), `weight_class`, `record`
- `fighter_headshot_img_url`, `fighter_full_body_img_url`
- **Next Fight:** `next_fight_date`, `next_fight_opponent`, `opponent_headshot_url`
- **Rumoured Fight:** `rumour_next_fight_*` fields
- **Profile:** `tags` (JSON), `height`, `weight`, `age`
- **Social:** `twitter`, `instagram`, `sherdog`

### Person
UFC automation user account:
- `email` (unique, indexed), `password` (bcrypt hash)
- `account_name`, `lang`, `photo`
- `total_generations`, `created_at`

### Subscription
User-to-Fighter relationship:
- `person_id` (FK to Person)
- `fighter_id` (FK to Fighter)

## Architecture

```
features/db/ufc/
├── routes.py                # Router registration hub
├── routes_fighters.py       # Fighter CRUD endpoints
├── routes_auth.py           # Authentication endpoints
├── routes_subscriptions.py  # Subscription endpoints
├── db_models.py             # Fighter, Person, Subscription
├── types.py                 # FighterRow, SubscriptionSummary
├── dependencies.py          # FastAPI DI
├── service/
│   ├── __init__.py          # UfcService coordinator
│   ├── fighters.py          # FighterCoordinator
│   ├── auth.py              # AuthCoordinator
│   ├── subscriptions.py     # SubscriptionCoordinator
│   └── queueing.py          # FighterQueueCoordinator
├── repositories/
│   ├── fighters.py          # FighterReadRepository
│   ├── auth.py              # AuthRepository
│   └── subscriptions.py     # SubscriptionReadRepository
└── schemas/
    ├── requests/            # Auth, fighter, subscription requests
    ├── internal.py          # AuthResult, UserProfile
    └── responses.py         # Response envelopes
```

## Service Layer

**UfcService** coordinates 4 sub-coordinators:

**FighterCoordinator:**
- `list_fighters()`, `search_fighters()`, `find_fighter_by_id()`
- `create_fighter()`, `update_fighter()`
- `list_fighters_with_subscriptions()` - Includes user's subscription status

**AuthCoordinator:**
- `authenticate_user()` - Verify credentials, return profile + token
- `register_user()` - Create account with bcrypt password
- `user_exists()`, `get_user_profile()`

**SubscriptionCoordinator:**
- `toggle_subscription()` - Add/remove subscription
- `list_subscription_summaries()` - Aggregated view per user

**FighterQueueCoordinator:**
- `enqueue_candidate()` - Send payload to SQS for async processing

## Authentication

- **Password Hashing:** bcrypt via `bcrypt.checkpw()`
- **Minimum Password Length:** 8 characters
- **Email Uniqueness:** Enforced at database level

## Fighter Search

Text search across multiple fields:
- `Fighter.name` - Fighter's name
- `Fighter.tags` - JSON tags array
- `Fighter.weight_class` - Division

**Filters Applied:**
- Non-null constraints on `height`, `weight`, `weight_class`
- Pattern matching with SQL LIKE

## Configuration

**Environment Variables:**
- `UFC_DB_URL` - MySQL connection string

**SQS Integration:**
- Fighter candidates queued for async processing via AWS SQS
