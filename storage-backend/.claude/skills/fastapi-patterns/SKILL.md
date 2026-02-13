# FastAPI Patterns Skill

This skill encodes the **BetterAI FastAPI backend patterns** for consistent, maintainable API development.

**Tags:** `#fastapi` `#patterns` `#backend` `#architecture` `#python`

## Quick Reference

### Project Conventions
- **File size limit**: 200-250 lines max per file
- **Layer hierarchy**: config/ → core/ → features/ → infrastructure/
- **Response envelope**: All endpoints use `api_ok()` or raise `HTTPException`
- **Dependency injection**: FastAPI dependency system for service/repository access
- **Database**: Async SQLAlchemy, repositories never commit (handled by session scope)

### Standard Feature Structure
```
features/<domain>/
├── routes.py         # FastAPI router (export as `router`)
├── service.py        # Business logic (service classes)
├── dependencies.py   # FastAPI dependency providers
├── schemas/
│   ├── __init__.py   # Re-export all schemas
│   ├── request.py    # Pydantic request models
│   └── response.py   # Pydantic response models
├── db_models.py      # SQLAlchemy ORM models (if DB-backed)
├── repositories/
│   ├── __init__.py   # Re-export repository classes
│   └── <name>_repository.py
└── CLAUDE.md         # Feature documentation
```

## Route Definition Patterns

### Basic Route with Dependency
```python
from fastapi import APIRouter, Depends, HTTPException, status
from core.pydantic_schemas import ok as api_ok
from features.items.dependencies import get_item_repository
from features.items.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/api/v1/items", tags=["items"])

@router.post("/", response_model=dict)
async def create_item(
    request: CreateItemRequest,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict:
    """Create a new item."""
    service = ItemService(repository)
    result = await service.create(request)
    return api_ok("Item created", data=result)
```

### Error Handling Pattern
```python
from core.exceptions import NotFoundError, ValidationError

@router.get("/{item_id}")
async def get_item(
    item_id: str,
    repository: ItemRepository = Depends(get_item_repository),
) -> dict:
    service = ItemService(repository)
    try:
        result = await service.get_by_id(item_id)
        return api_ok("Item retrieved", data=result)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
```

### Query Parameters & Filters
```python
@router.get("/")
async def list_items(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(None),
    repository: ItemRepository = Depends(get_item_repository),
) -> dict:
    """List items with pagination and filters."""
    service = ItemService(repository)
    results = await service.list_items(limit=limit, offset=offset, status=status)
    return api_ok("Items retrieved", data=results)
```

## Service Layer Pattern

### Service Class Structure
```python
from typing import Optional, Any
from core.exceptions import NotFoundError, ValidationError

class ItemService:
    """Business logic orchestration for items."""

    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    async def create(self, request: CreateItemRequest) -> dict[str, Any]:
        """Create new item through repository."""
        # Validate business rules
        if not request.name or len(request.name) < 2:
            raise ValidationError("Item name must be at least 2 characters")

        # Delegate to repository
        item = await self._repository.create(
            name=request.name,
            description=request.description,
        )

        return item.to_dict()

    async def get_by_id(self, item_id: str) -> dict[str, Any]:
        """Retrieve item by ID."""
        item = await self._repository.get_by_id(item_id)
        if not item:
            raise NotFoundError(f"Item {item_id} not found")
        return item.to_dict()
```

## Repository Pattern

### Async Repository Implementation
```python
from datetime import UTC, datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

class ItemRepository:
    """CRUD operations for items."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, **data) -> Item:
        """Create new item."""
        item = Item(**data)
        self._session.add(item)
        await self._session.flush()  # Get ID without committing
        return item

    async def get_by_id(self, item_id: str) -> Optional[Item]:
        """Retrieve by ID."""
        result = await self._session.execute(
            select(Item).where(Item.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        **filters,
    ) -> tuple[list[Item], int]:
        """List with pagination and filters."""
        query = select(Item)

        # Apply filters
        for field, value in filters.items():
            if value is not None and hasattr(Item, field):
                query = query.where(getattr(Item, field) == value)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self._session.execute(count_query)).scalar() or 0

        # Get paginated results
        results = await self._session.execute(
            query.order_by(Item.created_at.desc()).limit(limit).offset(offset)
        )
        return list(results.scalars().all()), total

    async def update(self, item_id: str, **updates) -> Optional[Item]:
        """Update item."""
        item = await self.get_by_id(item_id)
        if not item:
            return None

        # Update timestamp
        updates["updated_at"] = datetime.now(UTC)

        for field, value in updates.items():
            if hasattr(item, field) and value is not None:
                setattr(item, field, value)

        await self._session.flush()
        return item

    async def delete(self, item_id: str) -> bool:
        """Delete item."""
        item = await self.get_by_id(item_id)
        if not item:
            return False
        await self._session.delete(item)
        await self._session.flush()
        return True
```

## Pydantic Schema Pattern

### Request Schemas
```python
from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class CreateItemRequest(BaseModel):
    """Request model for creating an item."""

    name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Item name"
    )
    description: str = Field(
        ...,
        min_length=10,
        description="Item description"
    )
    price: float = Field(..., gt=0, description="Price in USD")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Sample Item",
                "description": "A detailed description of the item",
                "price": 99.99,
            }
        }
    }

class UpdateItemRequest(BaseModel):
    """Request model for updating an item."""

    name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    price: Optional[float] = Field(None, gt=0)
```

### Response Schemas
```python
from datetime import datetime

class ItemResponse(BaseModel):
    """Response model for an item."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Item name")
    description: str = Field(..., description="Item description")
    price: float = Field(..., description="Price in USD")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class ItemListResponse(BaseModel):
    """Response model for listing items."""

    items: list[ItemResponse] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    limit: int = Field(..., description="Limit used for query")
    offset: int = Field(..., description="Offset used for query")
```

## Database Model Pattern

### SQLAlchemy Model
```python
from sqlalchemy import Column, DateTime, String, Float, Index, Text
from sqlalchemy.sql import func
from infrastructure.db.base import Base

class Item(Base):
    """Item data model."""

    __tablename__ = "items"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    price = Column(Float, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_name", "name"),
        Index("idx_created", "created_at"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "price": self.price,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
```

## Dependency Injection Pattern

### Creating Dependencies
```python
from typing import AsyncGenerator
from infrastructure.db.mysql import require_main_session_factory, session_scope

async def get_item_repository() -> AsyncGenerator[ItemRepository, None]:
    """Yield repository bound to a database session."""
    session_factory = require_main_session_factory()
    async with session_scope(session_factory) as session:
        yield ItemRepository(session)

# Use in routes:
@router.get("/")
async def list_items(
    repository: ItemRepository = Depends(get_item_repository),
) -> dict:
    ...
```

## Key Best Practices

1. **Keep layers separated** - Routes call services, services use repositories
2. **Fail fast** - Validate input early in service layer
3. **Use typed exceptions** - Don't catch generic `Exception`
4. **Name endpoints clearly** - Describe what they do (create, list, get, update, delete)
5. **Document with OpenAPI** - Use Field descriptions and docstrings
6. **Handle errors explicitly** - Use HTTPException with appropriate status codes
7. **Keep files under 250 lines** - Split into helpers if growing too large
8. **Use async/await throughout** - All database operations must be async
9. **Test at each layer** - Unit tests for services, API tests for routes
10. **Validate at boundaries** - Use Pydantic for request validation

## Common Status Codes

| Code | Usage |
|------|-------|
| 200 | Successful GET, PATCH, DELETE |
| 201 | POST successful (when creating, use 200 with api_ok) |
| 400 | Validation error, bad request |
| 401 | Authentication required |
| 403 | Permission denied |
| 404 | Resource not found |
| 422 | Validation error (Pydantic) |
| 500 | Server error |
| 502 | Provider/external service error |

## See Also
- `@storage-backend/CLAUDE.md` - Full backend architecture
- `@storage-backend/DocumentationApp/storage-backend-ng-developer-handbook.md` - Comprehensive guide
- FastAPI docs: https://fastapi.tiangolo.com/
- SQLAlchemy async: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
