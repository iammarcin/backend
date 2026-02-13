"""Database Infrastructure - Async SQLAlchemy Engine Management for 4 MySQL Databases

This module provides the database connection layer for the BetterAI backend.
It manages four separate MySQL databases using async SQLAlchemy with connection
pooling, automatic reconnection, and FastAPI dependency injection integration.

Database Architecture:
    The application uses FOUR separate MySQL databases for domain isolation:
    1. MAIN_DB: Chat sessions, messages, users, prompts
       - Primary application data
       - ChatSessionsNG, ChatMessagesNG, Users, Prompts tables
    2. GARMIN_DB: Health and fitness data
       - GarminActivities, GarminSleep, GarminHealth tables
       - Integration with Garmin Connect API
    3. BLOOD_DB: Medical test results
       - BloodTests table with lab result data
    4. UFC_DB: Sports data and subscriptions
       - Fighters, Subscriptions tables
       - UFC fighter information

Connection Management:
    - Engines created lazily on first access (not at import time)
    - Connection pooling (10 base + 10 overflow per database)
    - Automatic reconnection (pool_pre_ping=True)
    - Connection recycling every 15 minutes
    - READ COMMITTED isolation level

FastAPI Integration Pattern:
    1. Engine created at module import
    2. Session factory created from engine
    3. Dependency function yields scoped session per request
    4. Session auto-commits on success, auto-rolls back on error

Usage Example:
    # In FastAPI route
    from infrastructure.db.mysql import main_session_factory, get_session_dependency
    get_main_session = get_session_dependency(main_session_factory)
    @router.post("/create-chat")
    async def create_chat(
        session: AsyncSession = Depends(get_main_session)
    ):
        # Use session for queries
        chat = ChatSessionNG(...)
        session.add(chat)
        await session.flush()  # Get ID
        # Session auto-commits when function returns successfully

Repository Pattern:
    - Routes call services
    - Services orchestrate providers + repositories
    - Repositories handle database CRUD operations
    - Repositories NEVER commit (services/routes control transactions)

Why Separate Databases?:
    - Domain isolation and security
    - Independent scaling and backup strategies
    - Different data retention policies
    - Some databases shared with other services

Design Notes:
    - No automatic migrations (models reflect existing schema)
    - Connection URLs configurable via environment variables
    - Engines can be None if database URL not provided
    - Pool settings optimized for async workload

See Also:
    - features/chat/db_models.py: ORM models for main database
    - features/chat/repositories/: CRUD operations for chat data
    - features/garmin/db_models.py: Garmin database models
"""

from infrastructure.db.mysql_engines import (
    AsyncSessionFactory,
    SessionDependency,
    create_mysql_engine,
    dispose_all_engines,
    get_session_factory,
    main_engine,
    main_session_factory,
    garmin_engine,
    garmin_session_factory,
    blood_engine,
    blood_session_factory,
    ufc_engine,
    ufc_session_factory,
)
from infrastructure.db.mysql_sessions import (
    get_session_dependency as _get_session_dependency,
    require_blood_session_factory,
    require_cc4life_session_factory,
    require_garmin_session_factory,
    require_main_session_factory,
    require_ufc_session_factory,
    session_scope,
)

# Re-export for backward compatibility
get_session_dependency = _get_session_dependency

__all__ = [
    "AsyncSessionFactory",
    "SessionDependency",
    "create_mysql_engine",
    "get_session_factory",
    "session_scope",
    "get_session_dependency",
    "require_main_session_factory",
    "require_garmin_session_factory",
    "dispose_all_engines",
    "require_blood_session_factory",
    "require_ufc_session_factory",
    "require_cc4life_session_factory",
    "main_engine",
    "main_session_factory",
    "garmin_engine",
    "garmin_session_factory",
    "blood_engine",
    "blood_session_factory",
    "ufc_engine",
    "ufc_session_factory",
]
