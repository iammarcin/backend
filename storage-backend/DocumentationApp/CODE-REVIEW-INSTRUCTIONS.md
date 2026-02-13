# Code Review Instructions (Python/FastAPI)

**Purpose**: Guidelines for reviewing implementations in this FastAPI backend. Read BEFORE reviewing to avoid false "complete" reports.

---

## The Core Problem

**Tests passing ≠ Feature working**

A review that only checks:
- ✅ Files exist
- ✅ Tests pass
- ✅ Type checks pass

...will miss critical gaps like:
- Code exists but no route calls it
- Service exists but no dependency wires it
- Provider registered but never resolved
- Endpoint exists but frontend doesn't call it

---

## Review Levels

### Level 1: Structural (Necessary but NOT Sufficient)

- [ ] Required files exist
- [ ] Tests exist and pass (`pytest tests/`)
- [ ] Type checks pass (`mypy`)
- [ ] No linting errors (`ruff`)

**If Level 1 passes**: Continue to Level 2. DO NOT report "complete" yet.

### Level 2: Wiring (Most Often Missed)

For each new function/class/route, verify it's actually USED **with file:line evidence**.

```bash
# Example: Verify service is used (not just defined)
# Find definition:
grep -rn "class MyService" features/
# Find usage (should find actual instantiation/calls):
grep -rn "MyService(" features/ core/

# Example: Verify route is registered
grep -rn "router.include_router" main.py app/
grep -rn "@router\.(get|post|put|delete)" features/myfeature/
```

**Checklist (each requires file:line citation):**
- [ ] Each new route is included in app router → "included at main.py:45"
- [ ] Each new service is injected via dependency → "Depends(get_my_service) at routes.py:30"
- [ ] Each new provider is registered → "register_provider() at core/providers/__init__.py:50"
- [ ] Each new repository is used by service → "repo.create() called at service.py:80"

**What does NOT count as wiring:**
- ❌ "Exported from __init__.py" - Just re-export, not usage
- ❌ "Has tests" - Tests don't mean it's called in production
- ❌ "Class defined" - Must be instantiated and used

### Level 3: Data Flow (End-to-End Trace)

Trace the feature from HTTP request to response:

```
1. Request hits /api/v1/endpoint
2. Route handler calls service
3. Service calls repository/provider
4. Repository queries database
5. Response returned via api_ok()
```

- [ ] Each step in the flow has working code
- [ ] No broken links in the chain
- [ ] Data format matches at each handoff (Pydantic schemas)

### Level 4: User Perspective

- [ ] **Can I curl this endpoint RIGHT NOW and get correct response?**
- [ ] **What request triggers this feature?** (If none → incomplete)
- [ ] **What response does the user get?** (If error → incomplete)
- [ ] **Is it documented in OpenAPI/Swagger?**

---

## Python/FastAPI Specific Checks

### Dependency Injection Verification

```python
# Definition in dependencies.py
def get_my_service(db: AsyncSession = Depends(get_db)) -> MyService:
    return MyService(db)

# Usage in routes.py - MUST be wired
@router.post("/endpoint")
async def my_endpoint(service: MyService = Depends(get_my_service)):
    ...
```

**Verify:**
- [ ] Dependency function exists in `dependencies.py`
- [ ] Dependency is used with `Depends()` in route
- [ ] Dependency's own dependencies are available

### Provider Registration Verification

```python
# Registration in core/providers/__init__.py
register_text_provider("my_provider", MyTextProvider)

# Resolution in factory.py or service
provider = get_text_provider(settings)
```

**Verify:**
- [ ] Provider class implements base class correctly
- [ ] Provider is registered in `__init__.py`
- [ ] Model configs exist in `config/providers/`
- [ ] Provider can be resolved by factory

### Repository Pattern Verification

```python
# Repository defined
class MyRepository:
    async def create(self, data: MySchema) -> MyModel:
        ...

# Service uses repository
class MyService:
    def __init__(self, repo: MyRepository):
        self.repo = repo

    async def do_thing(self):
        await self.repo.create(...)  # Actually called?
```

**Verify:**
- [ ] Repository methods are called by service
- [ ] Service is injected into routes
- [ ] Database session is properly scoped

### Async/Await Verification

```python
# BAD: Missing await
result = repo.get_by_id(id)  # Returns coroutine, not result!

# GOOD: Awaited
result = await repo.get_by_id(id)
```

**Verify:**
- [ ] All async functions are awaited
- [ ] No sync calls blocking async code
- [ ] Database operations use async session

---

## WebSocket Specific Checks

For WebSocket features:

- [ ] Handler registered in switchboard/router
- [ ] Events follow naming convention (see `websocket-events-handbook.md`)
- [ ] Completion events sent (`textCompleted`, `complete`, etc.)
- [ ] Error handling sends `error` event with `stage`
- [ ] StreamingManager used correctly (token ownership)

---

## Common Mistakes

### Mistake 1: Route Not Registered

```python
# routes.py has the route
@router.post("/my-endpoint")
async def my_endpoint(): ...

# But main.py doesn't include the router!
# app.include_router(my_router)  # Missing!
```

**Fix:** Verify router is included in app/main.py

### Mistake 2: Dependency Not Wired

```python
# Route expects dependency
async def my_endpoint(service: MyService = Depends(get_my_service)):
    ...

# But get_my_service doesn't exist or has wrong signature
```

**Fix:** Verify dependency function exists and matches expected signature

### Mistake 3: Provider Not Registered

```python
# Provider class exists
class MyNewProvider(BaseTextProvider):
    ...

# But not registered!
# register_text_provider("my_new", MyNewProvider)  # Missing!
```

**Fix:** Verify registration in `core/providers/__init__.py`

### Mistake 4: Async Not Awaited

```python
# Forgetting await
user = db.execute(select(User))  # Wrong - returns coroutine

# Correct
result = await db.execute(select(User))
user = result.scalar_one_or_none()
```

**Fix:** Check all async calls are awaited

### Mistake 5: Schema Mismatch

```python
# Route expects MyRequestSchema
async def my_endpoint(data: MyRequestSchema):
    ...

# But frontend sends different field names
# { "userName": "..." }  vs  { "user_name": "..." }
```

**Fix:** Verify schema matches what clients send (snake_case)

---

## Review Report Template

```markdown
## Implementation Review: [Feature Name]

### Level 1: Structural ✅/❌
- Files: [list]
- Tests: X passing
- Types: Clean / X errors
- Lint: Clean / X warnings

### Level 2: Wiring ✅/❌
**With file:line evidence:**
- `MyService`: ✅ Injected at `routes.py:30`
- `MyRepository`: ✅ Used at `service.py:45`
- `POST /endpoint`: ✅ Registered at `main.py:20`
- `MyProvider`: ❌ NOT REGISTERED ← BLOCKER

### Level 3: Data Flow ✅/❌
1. Request → Route ✅
2. Route → Service ✅
3. Service → Repository ❌ Method not called ← BLOCKER

### Level 4: User Perspective ✅/❌
- Can curl endpoint: Yes / No
- Returns correct response: Yes / No

### Status: ✅ COMPLETE / ❌ INCOMPLETE

### Blockers:
1. [Specific issue with file:line]
```

---

## Quick Checklist

Before reporting "complete":

- [ ] Routes included in app router
- [ ] Dependencies wired with Depends()
- [ ] Providers registered
- [ ] Repositories called by services
- [ ] All async functions awaited
- [ ] Schemas match API contract (snake_case)
- [ ] Tests cover the actual flow, not just units
- [ ] Can manually test with curl/httpx

---

## Related Documentation

- **Troubleshooting bugs?** See `TROUBLESHOOTING-GUIDELINES.md` for Python/FastAPI debugging principles
- **WebSocket events?** See `websocket-events-handbook.md` for event contract
