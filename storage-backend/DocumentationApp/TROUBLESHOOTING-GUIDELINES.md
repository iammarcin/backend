# Troubleshooting and Debugging Guidelines

**Purpose**: A systematic thinking framework for investigating bugs, errors, and unexpected behavior. These are generic principles that apply to any codebase, any language, any problem.

---

## Part 1: Mindset

### The Goal

> **Understand the problem completely before proposing any solution.**

Bad debugging: See symptom → guess cause → try fix → repeat.

Good debugging: Map system → trace all paths → find root cause → fix once.

### Avoid Tunnel Vision

The most dangerous debugging failure is **anchoring on a hypothesis too early**. If you recently fixed a race condition, you'll see race conditions everywhere. If you just debugged a null pointer, everything looks like a null pointer issue.

**Counter this by:**
- Deliberately looking for issues UNLIKE your initial hypothesis
- Completing the full systematic analysis (Part 2) even when you think you already know the answer
- Asking "what ELSE could cause this?"

### Verify, Don't Assume

Your mental model of how code works is usually wrong or incomplete. Before concluding anything:
- Read the actual code
- Check actual values (log them, inspect them)
- Verify actual behavior (don't assume "that part works")

---

## Part 2: Systematic Analysis Framework

Follow these steps IN ORDER. Don't skip steps because you think you found the bug.

### Step 1: Map the Complete System

Before looking for bugs, understand what you're analyzing:

| What to Map | Questions |
|-------------|-----------|
| **Components** | What modules/classes/functions are involved? |
| **States** | What states can the system be in? List ALL of them. |
| **Transitions** | How does the system move between states? What triggers each? |
| **Data Flow** | What data moves where? What format? What transformations? |
| **Entry/Exit Points** | Where does execution enter? All the ways it can exit? |

Write this down. A diagram helps. You cannot debug what you don't understand.

### Step 2: Trace Every Path

For each operation, systematically trace ALL paths:

| Path Type | Questions to Ask |
|-----------|------------------|
| **Happy path** | Does normal success work correctly? |
| **Error paths** | What if step X fails? Is error handled? What state results? |
| **Crash paths** | What if process dies mid-operation? What state is persisted? Can system recover on restart? |
| **Timeout paths** | What if something takes too long? What happens when timeout fires? |
| **Concurrent paths** | What if two operations happen simultaneously? What if order changes? |
| **Retry paths** | If this retries, what state is it in? Can retries cause duplicates? |
| **Partial completion** | What if operation completes steps 1-3 but fails on step 4? |

**Critical question for stateful systems**: "If the system stops at ANY point in this operation, what state is it left in? Can it recover?"

### Step 3: Verify Data at Every Boundary

At every boundary (function call, API call, file I/O, serialization):

| Check | Details |
|-------|---------|
| **Type** | Is the type actually correct? (not just "compiles" but semantically correct) |
| **Format** | Is the format what receiver expects? (encoding, content-type, schema, field names) |
| **Values** | Are values valid? (not null when shouldn't be, within expected ranges) |
| **Completeness** | Is all required data present? |

Don't assume - verify by reading code on BOTH sides of the boundary.

### Step 4: Check State Machine Completeness

For any system with states:

1. **List all states** - Write them down explicitly
2. **List all transitions** - What moves system from state A to state B?
3. **Check for stuck states** - Can any state be entered but never exited?
4. **Check for unreachable states** - Are there states with no transition leading to them?
5. **Check crash recovery** - If system crashes in each state, what happens on restart?

### Step 5: Verify Documentation Matches Reality

- Does the code do what comments/docs say it does?
- Do function/variable names accurately describe behavior?
- Does external documentation match actual implementation?
- Are there implicit assumptions not documented?

Mismatches between docs and code cause bugs - either code is wrong or people use it incorrectly.

### Step 6: Check Resource Lifecycle

For every resource (connections, files, handles, locks, memory):

| Question | What to verify |
|----------|----------------|
| **Creation** | Where created? Under what conditions? |
| **Usage** | Where used? Can it be used after cleanup? |
| **Cleanup** | Where cleaned up? Is cleanup guaranteed on all paths? |
| **Interruption** | What if cleanup is interrupted (crash, exception)? |
| **Ordering** | If multiple resources, is cleanup order correct? |

---

## Part 3: Verification Checklist

Before concluding your analysis is complete:

- [ ] I have mapped all components, states, and transitions
- [ ] I have traced the happy path
- [ ] I have traced all error paths
- [ ] I have traced crash/restart scenarios
- [ ] I have traced timeout scenarios
- [ ] I have traced concurrent operation scenarios
- [ ] I have verified data correctness at every boundary
- [ ] I have checked the state machine for stuck/unreachable states
- [ ] I have verified code matches documentation
- [ ] I have checked resource lifecycle (creation, cleanup, interruption)
- [ ] I have READ THE ACTUAL CODE, not assumed
- [ ] I have looked for issues UNLIKE my initial hypothesis

**If you haven't done all of these, your analysis is incomplete.**

---

## Part 4: Common Failure Patterns

These patterns will be found by the systematic framework above:

### Incomplete State Machines
- State that can be entered but never exited (stuck forever)
- State with no transitions leading to it (unreachable/dead code)
- Intermediate state not handled on crash/restart
- Recovery logic that doesn't account for all possible crash points

### Unhandled Paths
- Error path not implemented ("this shouldn't happen")
- Crash during operation leaves inconsistent state
- Timeout fires but handler doesn't clean up properly
- Partial completion not rolled back

### Boundary Mismatches
- Sender and receiver disagree on data format
- Type is technically correct but semantically wrong (e.g., wrong content-type)
- Field names don't match between systems
- Null/empty when other side doesn't expect it

### Resource Problems
- Resource created but not cleaned up on all paths
- Resource cleanup skipped on error path
- Resource cleanup interrupted, leaving resource stuck
- Using resource after cleanup

### Assumption Failures
- "This will always be non-null" (but it's not)
- "These will execute in order" (but they don't)
- "This state will never be reached" (but it is)
- "The other system will always respond" (but it doesn't)

---

## Part 5: Debugging Process

Once systematic analysis identifies potential issues:

### Reproduce Reliably
- Can you trigger it consistently?
- What exact steps reproduce it?
- What's expected vs actual behavior?

### Verify with Evidence
- Add logging at key points
- Capture actual values, not assumed values
- Confirm the failure matches your hypothesis

### Fix Root Cause
The fix should:
- Address the CAUSE, not the symptom
- Work under all conditions found in path analysis
- Not require specific timing or ordering
- Handle the crash/recovery scenarios you identified

### Verify Fix Completely
- Does it fix the reproduction case?
- Does it work under edge conditions?
- Does it handle the crash scenarios?
- Did it break anything else?

---

## Part 6: After Finding the Bug

Before implementing a fix:

1. **Explain root cause** - Not just what's wrong, but WHY
2. **Check for similar bugs** - Does this pattern exist elsewhere in the codebase?
3. **Consider side effects** - Does the fix break anything else?
4. **Update documentation** - If docs were wrong, fix them too

After implementing:

1. **Verify the original case is fixed**
2. **Verify edge cases work**
3. **Verify crash recovery works**
4. **Consider systematic prevention** - Can types/tests/linting prevent this class of bug?

---

## Part 7: When You're Stuck

If systematic analysis hasn't found the bug:

1. **Question your system map** - Is there a component/state/transition you missed?
2. **Add observability** - Log at every boundary, every state transition
3. **Simplify** - Can you reproduce with a simpler case?
4. **Check the obvious** - Right code? Right config? Right environment? Actually running?
5. **Get fresh perspective** - Explain to someone else (or rubber duck)
6. **Take a break** - Fresh eyes see what tired eyes miss

---

## Summary

The systematic framework in 6 steps:

1. **Map the system** - Components, states, transitions, data flow
2. **Trace ALL paths** - Happy, error, crash, timeout, concurrent, retry
3. **Verify boundaries** - Types, formats, values on both sides
4. **Check state machine** - Stuck states, unreachable states, crash recovery
5. **Compare to docs** - Code should match documentation
6. **Check resources** - Creation, cleanup, interruption handling

**Key principles:**
- Complete the full analysis even when you think you know the answer
- Look for issues UNLIKE your initial hypothesis
- Read actual code, don't assume
- Verify, don't trust

---

# Appendix: Python/FastAPI Specific Notes

When applying the systematic framework to this FastAPI backend:

## State Mapping: Include Async Context

When mapping states (Step 1), remember:
- Request lifecycle (dependency injection, handler, response)
- Database session lifecycle (created by Depends, closed after response)
- WebSocket connection states
- Background task states

## Path Tracing: Include Async Paths

When tracing paths (Step 2), consider:
- What if `await` is missing? (coroutine returned instead of result)
- What if exception occurs in async context?
- What if request is cancelled mid-operation?

## Boundary Verification: Check Serialization

When verifying boundaries (Step 3):

```python
# Content-type vs actual data
# Are you sending audio/mp4 when data is actually WAV?
AUDIO_MEDIA_TYPE = "audio/mp4".toMediaType()  # Check this matches actual file!

# Pydantic schema vs actual payload
class MyRequest(BaseModel):
    user_name: str  # Does client send user_name or userName?

# Database column vs code field
# Is it customer_id in DB but user_id in code?
```

## State Machine: Database Status Fields

When checking state machines (Step 4), audit status enums:

```python
class SyncStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"  # What if process dies here?
    COMPLETED = "completed"
    FAILED = "failed"

# Check: Does query fetch IN_PROGRESS for retry?
# Check: Is there recovery logic for stuck IN_PROGRESS?
```

## Resource Lifecycle: Database Sessions

When checking resources (Step 6):

```python
# Session closed after response - don't access lazy-loaded attributes
async def endpoint(db: AsyncSession = Depends(get_db)):
    user = await repo.get_user(db, id)
    return user  # OK
    # Later: user.posts  # FAIL - session closed, DetachedInstanceError

# WebSocket cleanup - does connection cleanup run on all exit paths?
```

## Quick Debugging Commands

```bash
# Check backend logs
docker logs backend --tail 100

# Check if changes were picked up
docker logs backend | grep "Reloading"

# Verify container is running
docker ps | grep backend
```
