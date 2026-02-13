#!/usr/bin/env python3
"""Validate that the import updates are working correctly."""

import sys
import traceback

def test_imports():
    """Test that the new import structure works."""
    print("Testing import updates...")

    try:
        # Test the new config imports
        from config.semantic_search.utils import get_collection_for_mode
        print("✓ config.semantic_search.utils import works")

        from config.database.urls import MAIN_DB_URL
        print("✓ config.database.urls import works")

        from config.environment import ENVIRONMENT
        print("✓ config.environment import works")

        from config.tts.utils import ElevenLabsRealtimeSettings, resolve_realtime_settings
        print("✓ config.tts.utils import works")

        from config.audio import StreamingProviderSettings, is_openai_streaming_model
        print("✓ config.audio import works")

        from config.semantic_search.qdrant import COLLECTION_NAME, URL, API_KEY
        print("✓ config.semantic_search.qdrant import works")

        from config.semantic_search.embeddings import MODEL, DIMENSIONS
        print("✓ config.semantic_search.embeddings import works")

        print("\n✅ All import updates are working correctly!")
        return True

    except Exception as e:
        print(f"\n❌ Import validation failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)