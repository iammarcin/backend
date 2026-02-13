# Manual Session Persistence Test

## Quick Start

This test validates that multiple messages sent in the same WebSocket connection share the same database session.

### Why This Test?

After implementing the cancellation feature, we discovered that:
1. TestClient-based WebSocket tests hang with concurrent task processing
2. Real WebSocket tests work correctly
3. This important session persistence validation needed a working test

### Running The Test

```bash
# Set your JWT token
export JWT_TOKEN="your-actual-jwt-token-here"

# Run the test
python tests/manual/test_session_persistence_manual.py
```

Or one-liner:
```bash
JWT_TOKEN="your-token" python tests/manual/test_session_persistence_manual.py
```

### Expected Output

**If working (sessions match):**
```
🔗 Connecting to: ws://localhost:8000/chat/ws
✅ WebSocket connected
📩 Received: websocketReady

📤 Sending first message...
📊 Collecting events for first message...
   1. working
   2. text
   3. dbOperationExecuted → session_id: abc-123-def
   ...
   N. fullProcessComplete

✓ First message session ID: abc-123-def

📤 Sending second message with same session ID...
📊 Collecting events for second message...
   1. working
   2. text
   3. dbOperationExecuted → session_id: abc-123-def
   ...
   N. fullProcessComplete

============================================================
📋 TEST RESULTS
============================================================
First message session ID:  abc-123-def
Second message session ID: abc-123-def

============================================================
✅ TEST PASSED
   Both messages landed in the same session!
   Session persistence is working correctly.
============================================================
```

**If broken (sessions different):**
```
============================================================
📋 TEST RESULTS
============================================================
First message session ID:  abc-123-def
Second message session ID: xyz-456-ghi

============================================================
❌ TEST FAILED
   Messages landed in DIFFERENT sessions!
   Session persistence is BROKEN.
============================================================
```

## What This Tests

1. **First Message**: Sends a message with empty `session_id` (creates new session)
2. **Capture Session ID**: Extracts `session_id` from `dbOperationExecuted` event
3. **Second Message**: Sends another message with the captured `session_id`
4. **Verification**: Confirms both messages used the same session ID

## Critical Fix Validated

This test validates the fix for the regression where `dbOperationExecuted` was sent after `signal_completion()`, causing the frontend to never receive the `session_id`.

The fix ensures:
- `persist_workflow_result()` is called BEFORE `signal_completion()`
- `dbOperationExecuted` event arrives BEFORE completion events
- Frontend receives session ID in time to reuse it for subsequent messages

## Configuration Options

### Custom Backend URL

```bash
BACKEND_WS_URL="ws://your-backend:8000/chat/ws" JWT_TOKEN="..." python tests/manual/test_session_persistence_manual.py
```

### Different Model

Edit the script and change:
```python
"text": {
    "model": "gpt-4o-mini"  # or "claude-mini", etc.
}
```

## Troubleshooting

### Connection Refused
```
❌ Connection failed: invalid status code
```
→ Backend not running or JWT expired

### Timeout
```
⏱️  Timeout waiting for events
```
→ Backend hung or request failed silently

### No Session ID Received
```
❌ ERROR: Did not receive session_id from first message
```
→ Database persistence is failing or `dbOperationExecuted` not being sent

## Why Not Pytest?

TestClient-based WebSocket tests hang with the new concurrent task processing in the cancellation implementation. The TestClient WebSocket doesn't handle `asyncio.create_task()` + `asyncio.wait()` patterns correctly.

Real WebSocket connections work fine - this is a TestClient limitation, not a backend issue.

## Related Files

- `tests/integration/chat/test_websocket_session_persistence.py` - Original TestClient tests (now skipped)
- `tests/manual/test_anthropic_agentic_manual.py` - Similar manual test for agentic workflows
