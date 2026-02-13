"""
Unit tests for JSON serialization utility.

These are FAST and RELIABLE - no WebSocket, no agentic, just serialization.
"""
import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


class TestJsonSerialization:
    """Test JSON serialization utility."""

    def test_sanitize_datetime(self):
        """Test datetime conversion to ISO string."""
        from core.utils.json_serialization import sanitize_for_json

        obj = {"created_at": datetime(2025, 1, 15, 10, 30, 0)}
        result = sanitize_for_json(obj)

        assert result == {"created_at": "2025-01-15T10:30:00"}
        assert isinstance(result["created_at"], str)

        # Verify it's JSON-serializable
        json.dumps(result)  # Should not raise

    def test_sanitize_uuid(self):
        """Test UUID conversion to string."""
        from core.utils.json_serialization import sanitize_for_json

        test_uuid = UUID("12345678-1234-5678-1234-567812345678")
        obj = {"id": test_uuid}
        result = sanitize_for_json(obj)

        assert result == {"id": "12345678-1234-5678-1234-567812345678"}
        assert isinstance(result["id"], str)

        # Verify it's JSON-serializable
        json.dumps(result)

    def test_sanitize_nested_complex_objects(self):
        """Test nested dict/list with datetime/UUID."""
        from core.utils.json_serialization import sanitize_for_json

        obj = {
            "user": {
                "id": uuid4(),
                "created_at": datetime.now()
            },
            "items": [
                {"timestamp": datetime(2025, 1, 1)},
                {"timestamp": datetime(2025, 1, 2)}
            ]
        }

        result = sanitize_for_json(obj)

        # All datetime/UUID should be strings
        assert isinstance(result["user"]["id"], str)
        assert isinstance(result["user"]["created_at"], str)
        assert isinstance(result["items"][0]["timestamp"], str)

        # Verify entire result is JSON-serializable
        json.dumps(result)

    def test_sanitize_tool_result_with_datetime(self):
        """Test realistic tool result with datetime."""
        from core.utils.json_serialization import sanitize_for_json

        # Simulate image generation tool result
        tool_result = {
            "success": True,
            "image_url": "https://example.com/image.png",
            "image_id": uuid4(),
            "created_at": datetime.now(),
            "metadata": {
                "model": "flux",
                "timestamp": datetime.now()
            }
        }

        result = sanitize_for_json(tool_result)

        # Verify all non-serializable objects converted
        assert isinstance(result["image_id"], str)
        assert isinstance(result["created_at"], str)
        assert isinstance(result["metadata"]["timestamp"], str)

        # Verify JSON-serializable
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)
        assert deserialized["success"] is True

    def test_is_json_serializable(self):
        """Test is_json_serializable helper."""
        from core.utils.json_serialization import is_json_serializable

        # Serializable
        assert is_json_serializable({"name": "test"}) is True
        assert is_json_serializable([1, 2, 3]) is True
        assert is_json_serializable("string") is True

        # Not serializable
        assert is_json_serializable({"date": datetime.now()}) is False
        assert is_json_serializable({"id": uuid4()}) is False
