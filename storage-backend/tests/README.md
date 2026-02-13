# Test Suite Documentation

## Running Tests

### Full Test Suite

```bash
pytest docker/storage-backend/tests/
```

### With Coverage

```bash
pytest --cov=docker/storage-backend --cov-report=html
```

### Specific Markers

```bash
# Run only integration tests
pytest -m integration

# Run only tests that require semantic search
pytest -m requires_semantic_search

# Skip tests that require external services
pytest -m "not live_api"
```

## Test Markers

| Marker | Purpose | Prerequisites |
|--------|---------|---------------|
| `asyncio` | Requires asyncio event loop | None |
| `anyio` | Requires AnyIO async support | None |
| `requires_docker` | Needs Docker daemon | Docker running |
| `live_api` | Hits real third-party APIs | API keys, network |
| `integration` | Multi-service integration | Varies by test |
| `requires_semantic_search` | Needs semantic search | `OPENAI_API_KEY`, `semantic_search_enabled` |
| `requires_garmin_db` | Needs Garmin database | `GARMIN_ENABLED=true`, `GARMIN_DB_URL` |
| `requires_ufc_db` | Needs UFC database | `UFC_DB_URL` |
| `requires_sqs` | Needs SQS queue service | AWS credentials |
| `requires_openai` | Needs OpenAI API | `OPENAI_API_KEY` |
| `requires_google` | Needs Google/Gemini API | `GOOGLE_API_KEY` |
| `requires_anthropic` | Needs Anthropic API | `ANTHROPIC_API_KEY` |

## Skipping Tests Based on Prerequisites

### Method 1: Using Fixtures (Recommended)

```python
def test_my_feature(require_semantic_search):
    """Test that automatically skips if semantic search not configured."""
    # Test code here
```

Available fixtures:
- `require_semantic_search`
- `require_garmin_db`
- `require_ufc_db`
- `require_sqs`

### Method 2: Using pytest.mark.skipif

```python
import pytest
from tests.helpers import is_semantic_search_available

@pytest.mark.skipif(
    not is_semantic_search_available(),
    reason="Semantic search not configured"
)
def test_my_feature():
    """Test that skips with clear reason."""
    # Test code here
```

### Method 3: Manual Skip in Test

```python
import pytest
from tests.helpers import is_semantic_search_available

def test_my_feature():
    """Test that checks prerequisites explicitly."""
    if not is_semantic_search_available():
        pytest.skip("Semantic search not configured")

    # Test code here
```

## Environment Variables

### Required for Semantic Search Tests
- `OPENAI_API_KEY` - OpenAI API key
- `semantic_search_enabled=true` - In settings

### Required for Garmin Tests
- `GARMIN_ENABLED=true` - Feature toggle must be enabled
- `GARMIN_DB_URL` - MySQL connection string for Garmin data

### Required for UFC Tests
- `UFC_DB_URL` - MySQL connection string for UFC data

### Required for SQS Tests
- `AWS_ACCESS_KEY_ID` - AWS access key
- `AWS_SECRET_ACCESS_KEY` - AWS secret key
- `SQS_QUEUE_URL` - (optional) SQS queue URL

## Examples

See `tests/unit/test_infrastructure_milestone.py` for complete examples of:
- Using markers
- Using fixtures
- Checking prerequisites
- Handling multiple dependencies
