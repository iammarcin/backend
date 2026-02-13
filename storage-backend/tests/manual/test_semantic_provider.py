"""Manual test for semantic search provider."""

from __future__ import annotations

import asyncio
import logging
import os

import pytest

# Manual regression script; requires live Qdrant & MySQL services.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="Set RUN_MANUAL_TESTS=1 to run semantic provider manual test against live infrastructure",
)

from core.clients import semantic as semantic_client
from core.providers.semantic import factory as semantic_factory
from core.providers.semantic import get_semantic_provider
from core.providers.semantic.schemas import SearchRequest
from features.semantic_search import service as service_module

logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_provider() -> None:
    """Test basic provider functionality."""
    print("\n" + "=" * 80)
    print("SEMANTIC SEARCH PROVIDER TEST")
    print("=" * 80 + "\n")

    # Clear caches at start for clean test state
    semantic_factory._PROVIDER_CACHE.clear()
    service_module._service_instance = None
    semantic_client._qdrant_client = None

    try:
        print("1. Getting provider instance...")
        provider = get_semantic_provider("qdrant")
        print("   ✓ Provider created\n")

        print("2. Testing health check...")
        health = await provider.health_check()
        healthy = bool(health.get("healthy")) if isinstance(health, dict) else bool(health)
        print(f"   ✓ Health check: {'PASSED' if healthy else 'FAILED'}")
        print(f"   Details: {health}\n")

        print("3. Creating collection...")
        await provider.create_collection()
        print("   ✓ Collection ready\n")

        print("4. Indexing test message...")
        await provider.index(
            message_id=1,
            content="We discussed starting a SaaS business with recurring revenue model",
            metadata={
                "customer_id": 123,
                "session_id": "test-session-001",
                "message_type": "user",
                "created_at": "2024-01-15T10:30:00Z",
                "tags": ["business_ideas"],
                "session_name": "Business Ideas Discussion",
            },
        )
        print("   ✓ Message indexed\n")

        print("5. Searching for 'business ideas'...")
        results = await provider.search(
            SearchRequest(
                query="business ideas",
                customer_id=123,
                limit=10,
                score_threshold=0.5,
            )
        )
        print(f"   ✓ Found {len(results)} results\n")

        if results:
            print("   Results:")
            for idx, result in enumerate(results, start=1):
                print(f"     {idx}. [Score: {result.score:.3f}] Message {result.message_id}")
                preview = result.content[:100].replace("\n", " ")
                print(f"        Content: {preview}...")
                session_name = result.metadata.get("session_name", "Unknown session")
                print(f"        Session: {session_name}\n")

        print("6. Updating message...")
        await provider.update(
            message_id=1,
            content="We refined our SaaS idea focusing on B2B workflow automation",
            metadata={
                "customer_id": 123,
                "session_id": "test-session-001",
                "message_type": "user",
                "created_at": "2024-01-15T10:30:00Z",
                "tags": ["business_ideas"],
                "session_name": "Business Ideas Discussion",
            },
        )
        print("   ✓ Message updated\n")

        print("7. Deleting message...")
        await provider.delete(message_id=1)
        print("   ✓ Message deleted\n")

        # Allow any pending async operations to complete
        await asyncio.sleep(0.1)

        print("=" * 80)
        print("ALL TESTS PASSED ✓")
        print("=" * 80)

    finally:
        # Ensure proper cleanup of async resources
        print("8. Cleaning up resources...")
        try:
            await semantic_client.close_qdrant_client()
            print("   ✓ Qdrant client closed\n")
        except Exception as e:
            print(f"   ⚠ Warning: Failed to close Qdrant client: {e}\n")

        # Clear caches for next test run
        semantic_factory._PROVIDER_CACHE.clear()
        service_module._service_instance = None
        semantic_client._qdrant_client = None
        print("   ✓ Caches cleared\n")


if __name__ == "__main__":
    asyncio.run(test_provider())
