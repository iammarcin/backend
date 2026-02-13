# Manual Anthropic Agentic Test

## Quick Start

This is a REAL test with REAL WebSocket and REAL APIs - no mocks!

### 1. Get Your JWT Token

From your browser/app while logged in, copy the JWT token.

### 2. Run The Test

```bash
# Set your JWT token
export JWT_TOKEN="your-actual-jwt-token-here"

# Run the test
python tests/manual/test_anthropic_agentic_manual.py
```

Or one-liner:
```bash
JWT_TOKEN="your-token" python tests/manual/test_anthropic_agentic_manual.py
```

### 3. Expected Output

**If working:**
```
🔗 Connecting to: ws://localhost:8000/chat/ws
✅ WebSocket connected
📩 Received: websocketReady
   Session ID: abc-123

📤 Sending agentic request...

📊 Collecting events...
   1. working
   2. customEvent → model: claude-sonnet-3-5-20241022
   3. iterationStarted
   4. toolCall ✓ TOOL: generate_image
   5. toolResult ✓ RESULT: success
   ...
   N. complete

🏁 Workflow completed

============================================================
📋 TEST RESULTS
============================================================
Total events: 25
Tool calls detected: 1

🔧 Tool Calls:
   1. generate_image (id: call_xyz)

============================================================
✅ TEST PASSED
   Anthropic agentic workflow detected and executed tool calls!
   Issue 2 is FIXED ✓
```

**If broken:**
```
❌ TEST FAILED
   No tool calls detected in agentic workflow
   Issue 2 is NOT fixed
```

## Current Backend Bugs Blocking Tests

Before this test can pass, fix these backend bugs:

### Bug 1: emit_provider_error signature
**File:** `features/chat/utils/dispatcher_helpers.py:161`
**Error:** `TypeError: emit_provider_error() takes 0 positional arguments but 3 were given`

### Bug 2: OpenAI builtin_tool_config
**File:** `core/providers/text/streaming.py:115`
**Error:** `TypeError: AsyncCompletions.create() got an unexpected keyword argument 'builtin_tool_config'`

## Configuration Options

### Custom Backend URL

```bash
BACKEND_WS_URL="ws://your-backend:8000/chat/ws" JWT_TOKEN="..." python tests/manual/test_anthropic_agentic_manual.py
```

### Different Model

Edit the script and change:
```python
"text": {
    "model": "claude-mini"  # or "claude", "gpt-4o", etc.
}
```

## Why This Test Instead of Pytest?

- ✅ **Real WebSocket** - Uses `websockets` library, not TestClient
- ✅ **Real Backend** - Connects to actual running backend
- ✅ **Real APIs** - Calls Anthropic/OpenAI APIs for real
- ✅ **Simple** - Plain Python script, easy to debug
- ✅ **No mocks** - What you see is what you get

Pytest TestClient is still a test environment with mocking layers that don't behave like real connections.

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

### No Tool Calls But Completes
```
Total events: 15
Tool calls detected: 0
```
→ Issue 2 not fixed - provider not detecting/executing tools

## Next Steps

Once this manual test passes:
1. Issues 2 & 3 are validated as fixed
2. Can proceed with production deployment
3. Can skip complex pytest integration tests

The manual test is the source of truth ✓
