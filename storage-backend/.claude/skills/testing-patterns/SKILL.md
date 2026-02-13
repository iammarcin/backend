# Testing Patterns Skill

This skill encodes the **BetterAI pytest patterns** for comprehensive test coverage and quality assurance.

**Tags:** `#testing` `#pytest` `#quality` `#ci-cd` `#backend`

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── api/                     # Route/endpoint tests
│   ├── conftest.py          # API-specific fixtures
│   ├── test_items.py
│   └── ...
├── features/                # Service/business logic tests
│   ├── <feature>/
│   │   └── test_<service>.py
│   └── ...
├── integration/             # End-to-end flow tests
│   └── test_<flow>.py
├── unit/                    # Pure unit tests
│   ├── core/
│   ├── config/
│   └── infrastructure/
└── manual/                  # Manual validation scripts (not in CI)
```

## Quick Reference

### Test Naming
- Test files: `test_<module>.py`
- Test functions: `test_<feature>_<scenario>`
- Test classes: `Test<FeatureOrComponent>`

### Pytest Markers
- `@pytest.mark.asyncio` - For async tests
- `@pytest.mark.parametrize` - For similar tests with different inputs
- `@pytest.mark.skip` - Skip test with reason
- `@pytest.mark.xfail` - Expected to fail

### Running Tests
```bash
# All tests
docker exec backend pytest tests/ -v

# Specific test file
docker exec backend pytest tests/api/test_items.py -v

# Specific test
docker exec backend pytest tests/api/test_items.py::test_create_item_success -v

# With coverage
docker exec backend pytest tests/ --cov=features --cov-report=term-missing --cov-fail-under=90

# Only failing tests
docker exec backend pytest tests/ --lf

# By marker
docker exec backend pytest tests/ -m asyncio

# By pattern
docker exec backend pytest tests/ -k "test_create"
```

## Test Fixtures Pattern

### Global Fixtures (conftest.py)
```python
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock

from main import app

@pytest.fixture
async def client():
    """Async HTTP client for API tests."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

@pytest.fixture
def mock_repository():
    """Mock repository with async methods."""
    repo = AsyncMock()
    repo.get_by_id.return_value = None
    repo.create.return_value = MagicMock(id="test-123")
    repo.list.return_value = ([], 0)
    return repo

@pytest.fixture
def mock_service(mock_repository):
    """Mock service with repository."""
    service = AsyncMock()
    service._repository = mock_repository
    return service

@pytest.fixture
def override_dependencies(mock_repository):
    """Override FastAPI dependencies."""
    from features.items.dependencies import get_item_repository

    app.dependency_overrides[get_item_repository] = lambda: mock_repository
    yield
    app.dependency_overrides.clear()
```

### Feature-Specific Fixtures
```python
# tests/features/items/conftest.py
import pytest
from features.items.service import ItemService

@pytest.fixture
def sample_item_data():
    """Sample item data for tests."""
    return {
        "id": "item-123",
        "name": "Test Item",
        "description": "A test item for testing",
        "price": 99.99,
    }

@pytest.fixture
async def item_service(mock_repository):
    """Item service with mock repository."""
    return ItemService(repository=mock_repository)
```

## API Test Pattern

### Route Tests with AsyncClient
```python
import pytest
from httpx import AsyncClient

class TestItemRoutes:
    """Tests for item endpoints."""

    @pytest.mark.asyncio
    async def test_create_item_success(self, client: AsyncClient):
        """Test successful item creation."""
        response = await client.post(
            "/api/v1/items",
            json={
                "name": "Test Item",
                "description": "A detailed description",
                "price": 99.99,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Test Item"

    @pytest.mark.asyncio
    async def test_create_item_invalid_name(self, client: AsyncClient):
        """Test validation error on invalid name."""
        response = await client.post(
            "/api/v1/items",
            json={
                "name": "",  # Invalid: too short
                "description": "A detailed description",
                "price": 99.99,
            },
        )

        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, client: AsyncClient):
        """Test 404 when item doesn't exist."""
        response = await client.get("/api/v1/items/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_items_pagination(self, client: AsyncClient):
        """Test list endpoint pagination."""
        response = await client.get("/api/v1/items?limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data["data"]
        assert "total" in data["data"]
```

### Testing with Dependency Overrides
```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_create_item_with_mock(client: AsyncClient, override_dependencies, mock_repository):
    """Test create endpoint with mocked repository."""
    # Mock repository returns a specific result
    mock_repository.create.return_value = MagicMock(
        id="item-123",
        name="Test Item",
        to_dict=lambda: {"id": "item-123", "name": "Test Item"}
    )

    response = await client.post(
        "/api/v1/items",
        json={"name": "Test Item", "description": "...", "price": 99.99},
    )

    assert response.status_code == 200
    # Verify mock was called correctly
    mock_repository.create.assert_called_once()
```

## Service Test Pattern

### Business Logic Tests
```python
import pytest
from core.exceptions import NotFoundError, ValidationError

class TestItemService:
    """Tests for item business logic."""

    @pytest.mark.asyncio
    async def test_create_item_success(self, item_service, mock_repository, sample_item_data):
        """Test successful item creation."""
        # Mock repository
        mock_repository.create.return_value = MagicMock(**sample_item_data)

        # Execute service
        result = await item_service.create(CreateItemRequest(**sample_item_data))

        # Assertions
        assert result["id"] == "item-123"
        assert result["name"] == "Test Item"
        mock_repository.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_item_validation_error(self, item_service):
        """Test validation error on invalid data."""
        with pytest.raises(ValidationError):
            await item_service.create(
                CreateItemRequest(name="", description="...", price=-10)
            )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, item_service, mock_repository):
        """Test get with non-existent item."""
        mock_repository.get_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await item_service.get_by_id("nonexistent")

    @pytest.mark.asyncio
    async def test_list_items_with_filters(self, item_service, mock_repository):
        """Test list with filters."""
        mock_repository.list.return_value = ([MagicMock(id="1")], 1)

        result = await item_service.list_items(limit=20, status="active")

        assert len(result) == 1
        mock_repository.list.assert_called_once_with(limit=20, status="active")
```

## Unit Test Pattern

### Pure Function Tests
```python
import pytest

class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_parse_model_name(self):
        """Test model name parsing."""
        result = parse_model_name("gpt-4-turbo")
        assert result.provider == "openai"
        assert result.model == "gpt-4-turbo"

    @pytest.mark.parametrize("temperature,valid", [
        (0.0, True),
        (1.0, True),
        (2.0, True),
        (-0.1, False),
        (2.1, False),
    ])
    def test_validate_temperature(self, temperature, valid):
        """Test temperature validation with various inputs."""
        if valid:
            assert validate_temperature(temperature) is True
        else:
            with pytest.raises(ValueError):
                validate_temperature(temperature)
```

## Parametrized Tests

### Testing Multiple Cases
```python
import pytest

@pytest.mark.parametrize("status_code,expected", [
    (200, True),
    (201, True),
    (400, False),
    (404, False),
    (500, False),
])
@pytest.mark.asyncio
async def test_response_handling(self, client: AsyncClient, status_code, expected):
    """Test response handling for various status codes."""
    # Mock response
    response = MagicMock(status_code=status_code)

    if expected:
        assert is_success(response) is True
    else:
        assert is_success(response) is False


@pytest.mark.parametrize("name,description,price", [
    ("Item 1", "Description 1", 10.00),
    ("Item 2", "Description 2", 20.00),
    ("Item 3", "Description 3", 30.00),
])
@pytest.mark.asyncio
async def test_create_multiple_items(self, client: AsyncClient, name, description, price):
    """Test creating multiple items with different data."""
    response = await client.post(
        "/api/v1/items",
        json={"name": name, "description": description, "price": price},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["name"] == name
    assert data["data"]["price"] == price
```

## Async Test Pattern

### Testing Async Functions
```python
import pytest

@pytest.mark.asyncio
async def test_async_operation():
    """Test async function."""
    result = await async_function()
    assert result == expected

@pytest.mark.asyncio
async def test_async_with_mock():
    """Test async function with mock."""
    mock = AsyncMock()
    mock.return_value = "mocked value"

    result = await mock()

    assert result == "mocked value"
    mock.assert_called_once()
```

## Mocking Pattern

### Mock Common Objects
```python
from unittest.mock import AsyncMock, MagicMock

# Mock async function
mock_async_fn = AsyncMock()
mock_async_fn.return_value = {"result": "value"}

# Mock repository
mock_repo = AsyncMock()
mock_repo.get_by_id.return_value = MagicMock(id="123")
mock_repo.list.return_value = ([MagicMock(id="1")], 1)

# Mock provider
mock_provider = AsyncMock()
mock_provider.generate.return_value = "generated content"
mock_provider.generate.side_effect = ProviderError("API error")  # For error testing

# Verify calls
mock_repo.get_by_id.assert_called_once_with("123")
mock_repo.list.assert_called()
mock_provider.generate.assert_not_called()
```

## Coverage Requirements

**Minimum: 90% coverage**

```bash
# Run with coverage report
docker exec backend pytest tests/ \
  --cov=features \
  --cov=core \
  --cov-report=term-missing \
  --cov-fail-under=90
```

### What to Test
- Happy paths (success cases)
- Error cases (validation, not found, etc.)
- Edge cases (empty input, None values, etc.)
- Boundaries (max/min values)
- Integration between components

### What NOT to Necessarily Test
- Library code (trust pytest, SQLAlchemy, etc.)
- Simple getters/setters
- Auto-generated code
- Third-party dependencies

## CI/CD Integration

### Pre-commit Hook Example
```bash
#!/bin/bash
# .git/hooks/pre-commit

docker exec backend pytest tests/ -x --tb=short -q
if [ $? -ne 0 ]; then
    echo "Tests failed, commit aborted"
    exit 1
fi
```

## Common Issues & Solutions

### Issue: "RuntimeError: Event loop closed"
**Solution:** Use `@pytest.mark.asyncio` decorator on async tests

### Issue: Tests pass locally but fail in CI
**Solution:** Ensure deterministic order - use sorted IDs, fixed seeds, explicit mocks

### Issue: Slow tests
**Solution:** Mock external services, use async properly, avoid real database calls

## Best Practices

1. **Test behavior, not implementation** - Focus on what, not how
2. **Use descriptive names** - `test_create_item_with_invalid_price` not `test_create_1`
3. **One assertion per concept** - Multiple assertions per test is OK if testing one scenario
4. **DRY up fixtures** - Reuse common setup
5. **Test in isolation** - Mock external dependencies
6. **Test error paths** - Not just success cases
7. **Keep tests fast** - Mock slow operations
8. **Document complex tests** - Explain what's being tested
9. **Use parametrize** - For similar tests with different inputs
10. **Maintain test data** - Keep test fixtures realistic

## See Also
- `@storage-backend/CLAUDE.md` - Full backend architecture
- `@storage-backend/DocumentationApp/testing-guide-handbook.md` - Testing handbook
- pytest docs: https://docs.pytest.org/
- unittest.mock: https://docs.python.org/3/library/unittest.mock.html
