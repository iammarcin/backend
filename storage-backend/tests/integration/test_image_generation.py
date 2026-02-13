import base64
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from core.providers.capabilities import ProviderCapabilities
from core.providers.base import BaseImageProvider
from core.providers.factory import register_image_provider
from main import app


class ImageStubProvider(BaseImageProvider):
    def __init__(self) -> None:
        self.capabilities = ProviderCapabilities(streaming=False)
        self.provider_name = "stub-image"

    async def generate(
        self,
        prompt: str,
        model: str | None = None,
        width: int = 1024,
        height: int = 1024,
        **kwargs: Dict[str, object],
    ) -> bytes:
        return b"fake-image-bytes"


@pytest.fixture(autouse=True)
def override_image_provider():
    from core.providers.registries import _image_providers

    original = _image_providers.get("openai")
    register_image_provider("openai", ImageStubProvider)
    try:
        yield
    finally:
        if original:
            _image_providers["openai"] = original
        else:
            _image_providers.pop("openai", None)


def test_image_generation_returns_data_url(auth_token_factory):
    client = TestClient(app)

    response = client.post(
        "/image/generate",
        json={
            "prompt": "A calm lake at sunrise",
            "settings": {"image": {"model": "openai", "width": 512, "height": 512}},
            "customer_id": 42,
            "save_to_db": False,
        },
        headers={"Authorization": f"Bearer {auth_token_factory(customer_id=42)}"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["success"] is True
    data_url = payload["data"]["image_url"]
    assert data_url.startswith("data:image/png;base64,")

    encoded = data_url.split(",", 1)[1]
    assert base64.b64decode(encoded) == b"fake-image-bytes"
    assert payload["data"]["provider"] == "stub-image"
    assert payload["data"]["settings"]["width"] == 512


def test_image_generation_uploads_to_s3(monkeypatch, auth_token_factory):
    client = TestClient(app)

    uploads: list[dict[str, object]] = []

    class DummyS3Client:
        def put_object(self, **kwargs):  # type: ignore[no-untyped-def]
            uploads.append(kwargs)

    monkeypatch.setattr(
        "infrastructure.aws.storage.get_s3_client",
        lambda: DummyS3Client(),
    )
    monkeypatch.setenv("IMAGE_S3_BUCKET", "test-bucket")

    response = client.post(
        "/image/generate",
        json={
            "prompt": "A futuristic city skyline",
            "settings": {"image": {"model": "openai", "width": 256, "height": 256}},
            "customer_id": 7,
            "save_to_db": True,
        },
        headers={"Authorization": f"Bearer {auth_token_factory(customer_id=7)}"},
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["success"] is True
    image_url = payload["data"]["image_url"]
    assert uploads, "Expected put_object to be called"

    upload = uploads[0]
    assert upload["Bucket"] == "test-bucket"
    assert upload["ContentType"] == "image/png"

    key = upload["Key"]
    assert key.startswith("7/assets/chat/1/")
    assert key.endswith(".png")

    # Region-specific S3 domains look like ``test-bucket.s3.eu-south-2.amazonaws.com``
    # while the default region omits the segment. The image URL should always end
    # with the uploaded key regardless of the region configuration.
    assert image_url.startswith("https://test-bucket.s3")
    assert image_url.endswith(key)
