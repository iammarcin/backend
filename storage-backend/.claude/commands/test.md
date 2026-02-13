---
description: Run comprehensive test suite for current changes. Validates implementation quality and coverage.
allowed-tools: Read, Bash, Grep, Glob
model: claude-sonnet-4-5-20250929
---

# Run Test Suite

## Context
- Request ID: $1
- Changed files: !`git diff --name-only HEAD~1 2>/dev/null || git diff --name-only`

## Test Execution Strategy

### Step 1: Identify Affected Tests

Map changed files to relevant test suites:

| Changed Path | Test Path |
|--------------|-----------|
| features/chat/ | tests/features/chat/, tests/api/chat/ |
| features/automation/ | tests/features/automation/, tests/api/automation/ |
| core/providers/ | tests/unit/core/providers/ |
| core/streaming/ | tests/unit/core/streaming/ |
| config/ | tests/unit/config/ |
| infrastructure/ | tests/unit/infrastructure/ |

### Step 2: Run Targeted Tests First

Run tests most likely to be affected by recent changes:

```bash
# Get list of changed Python files
CHANGED=$(git diff --name-only HEAD~1 2>/dev/null | grep '\.py$' || echo "")

# Run tests for changed feature modules
docker exec backend pytest tests/ -x --tb=short -q 2>&1 | tail -50
```

### Step 3: Run Unit Tests

```bash
docker exec backend pytest tests/unit/ -v --tb=short -q
```

Expected: All unit tests pass

### Step 4: Run Feature Tests

```bash
docker exec backend pytest tests/features/ -v --tb=short -q
```

Expected: All feature tests pass

### Step 5: Run API Tests

```bash
docker exec backend pytest tests/api/ -v --tb=short -q
```

Expected: All API route tests pass

### Step 6: Run Integration Tests (if needed)

Only for changes affecting multiple components:

```bash
docker exec backend pytest tests/integration/ -v --tb=short -q
```

### Step 7: Check Coverage

```bash
docker exec backend pytest tests/ \
  --cov=features \
  --cov=core \
  --cov-report=term-missing \
  --cov-fail-under=90
```

Expected: Coverage >= 90%

### Step 8: Record Results

Create a summary of test results:

```json
{
  "total_tests": <number>,
  "passed": <number>,
  "failed": <number>,
  "skipped": <number>,
  "coverage_percent": <number>,
  "failing_tests": [<list if any>],
  "duration_seconds": <number>
}
```

Update the request with results:

```bash
python3 .claude/scripts/update_request_status.py $1 \
  --status testing \
  --test-results '<json>'
```

## Failure Handling

If tests fail:

1. **Parse failure output** - Identify which tests failed and why
2. **Categorize failures**:
   - Flaky test (retry once)
   - Missing fixture (check conftest.py)
   - Actual regression (needs fix)
   - New feature not tested (needs test)
3. **Report failures** with:
   - Test name and file
   - Error message
   - Suggested fix
4. **Do NOT proceed** to deployment until all tests pass

## Quality Gates

Before marking tests as passed, verify:
- [ ] No test failures
- [ ] Coverage >= 90%
- [ ] No skipped tests without reason
- [ ] All new code has tests
- [ ] Integration tests pass (if applicable)

## Output

Report:
1. Total tests run and results
2. Coverage percentage
3. Any failures with details
4. Recommendation (proceed/fix needed)
