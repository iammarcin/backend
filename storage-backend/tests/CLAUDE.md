# Testing Guidelines (CLAUDE Cheatsheet)

1. **Gate all paid/live flows with `RUN_MANUAL_TESTS`.**  
   - Wrap manual or live-provider tests in `pytest.mark.skipif(os.getenv("RUN_MANUAL_TESTS") != "1", ...)`.  
   - Live provider suites must also call `tests.utils.live_providers.require_live_client(...)` so they only run when both the flag *and* the relevant API key/client are available.

2. **Always label external API work with `pytest.mark.live_api`.**  
   - Keeps the fast suite (`pytest -m "not live_api"`) deterministic.  
   - Convert transient provider failures to skips via `skip_if_transient_provider_error(...)`.

3. **Prefer ASGI/TestClient patterns for API routes.**  
   - Use `httpx.ASGITransport(app=app)` + dependency overrides to avoid hitting the real network.  
   - Encode external effects (S3, MySQL, etc.) behind fixtures/mocks so default runs stay free.

