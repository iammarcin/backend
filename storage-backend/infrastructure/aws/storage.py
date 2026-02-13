"""Service objects for interacting with S3 object storage."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.aws import AWS_REGION, IMAGE_S3_BUCKET
from core.exceptions import ConfigurationError, ServiceError

from .clients import get_s3_client

logger = logging.getLogger(__name__)


DEFAULT_DISCUSSION_ID = 1


_DEFAULT_ATTACHMENT_ACL = "public-read"


def _normalise_filename(filename: str) -> str:
    """Return a filesystem-safe filename preserving the original extension."""

    candidate = Path(filename or "upload.bin").name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", candidate)
    return safe_name or "upload.bin"


def _resolve_content_type(filename: str, provided: str | None) -> str:
    """Infer a sensible content type for attachments when none is supplied."""

    if provided:
        return provided
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class StorageService:
    """Handle uploads of generated assets to S3."""

    def __init__(self, *, bucket_name: str | None = None, s3_client: Any | None = None) -> None:
        client = s3_client or get_s3_client()
        if client is None:
            raise ConfigurationError("S3 client not initialised", key="AWS credentials")

        self._s3_client = client
        resolved_bucket = bucket_name or os.getenv("IMAGE_S3_BUCKET") or IMAGE_S3_BUCKET
        if not resolved_bucket:
            raise ConfigurationError(
                "IMAGE_S3_BUCKET must be configured",
                key="IMAGE_S3_BUCKET",
            )
        self._bucket_name = resolved_bucket
        self._region = AWS_REGION or ""

        logger.debug("StorageService initialised", extra={"bucket": self._bucket_name})

    async def upload_image(
        self,
        *,
        image_bytes: bytes,
        customer_id: int,
        file_extension: str = "png",
    ) -> str:
        """Upload raw image bytes to S3 and return the public URL."""

        if not image_bytes:
            raise ServiceError("Cannot upload empty image payload")

        key = self._build_chat_asset_key(
            customer_id=customer_id,
            asset_category="image",
            extension=file_extension,
        )
        logger.info("Uploading generated image to S3 bucket=%s key=%s", self._bucket_name, key)

        await asyncio.to_thread(
            self._s3_client.put_object,
            Bucket=self._bucket_name,
            Key=key,
            Body=image_bytes,
            ContentType=f"image/{file_extension}",
        )

        url = self._object_url(key)
        logger.info("Image uploaded successfully to %s", url)
        return url

    async def upload_video(
        self,
        *,
        video_bytes: bytes,
        customer_id: int,
        file_extension: str = "mp4",
    ) -> str:
        """Upload generated video bytes to S3 and return the public URL."""

        if not video_bytes:
            raise ServiceError("Cannot upload empty video payload")

        key = self._build_chat_asset_key(
            customer_id=customer_id,
            asset_category="video",
            extension=file_extension,
        )
        logger.info(
            "Uploading generated video to S3 bucket=%s key=%s",
            self._bucket_name,
            key,
        )

        await asyncio.to_thread(
            self._s3_client.put_object,
            Bucket=self._bucket_name,
            Key=key,
            Body=video_bytes,
            ContentType=f"video/{file_extension}",
        )

        url = self._object_url(key)
        logger.info("Video uploaded successfully to %s", url)
        return url

    async def upload_audio(
        self,
        *,
        audio_bytes: bytes,
        customer_id: int,
        file_extension: str = "mp3",
        folder: str | None = None,
        content_type: str | None = None,
        key: str | None = None,
        acl: str | None = None,
    ) -> str:
        """Upload generated audio bytes to S3 and return the public URL."""

        if not audio_bytes:
            raise ServiceError("Cannot upload empty audio payload")

        resolved_key = self._resolve_audio_key(
            customer_id=customer_id,
            folder=folder,
            extension=file_extension,
            key=key,
        )
        logger.info(
            "Uploading generated audio to S3 bucket=%s key=%s",
            self._bucket_name,
            resolved_key,
        )

        resolved_content_type = content_type or f"audio/{file_extension}"
        put_kwargs = {
            "Bucket": self._bucket_name,
            "Key": resolved_key,
            "Body": audio_bytes,
            "ContentType": resolved_content_type,
        }
        if acl:
            put_kwargs["ACL"] = acl

        await asyncio.to_thread(
            self._s3_client.put_object,
            **put_kwargs,
        )

        url = self._object_url(resolved_key)
        logger.info("Audio uploaded successfully to %s", url)
        return url

    async def upload_chat_attachment(
        self,
        *,
        file_bytes: bytes,
        customer_id: int,
        filename: str,
        content_type: str | None = None,
        force_filename: bool = False,
        acl: str | None = _DEFAULT_ATTACHMENT_ACL,
    ) -> str:
        """Upload a user-provided chat attachment and return the public URL."""

        if not file_bytes:
            raise ServiceError("Cannot upload empty attachment payload")

        safe_name = _normalise_filename(filename)
        extension = Path(safe_name).suffix.lstrip(".").lower()
        if not extension:
            raise ServiceError("Attachment must include a valid file extension")

        if force_filename:
            stored_name = safe_name
        else:
            timestamp = datetime.now(UTC).strftime("%Y%m%d")
            random_part = uuid.uuid4().hex[:8]
            stored_name = f"{timestamp}_{random_part}_{safe_name}"

        key = f"{customer_id}/assets/chat/{DEFAULT_DISCUSSION_ID}/{stored_name}"
        resolved_content_type = _resolve_content_type(stored_name, content_type)

        put_kwargs = {
            "Bucket": self._bucket_name,
            "Key": key,
            "Body": file_bytes,
            "ContentType": resolved_content_type,
        }
        if acl:
            put_kwargs["ACL"] = acl

        logger.info(
            "Uploading chat attachment to S3 bucket=%s key=%s content_type=%s",
            self._bucket_name,
            key,
            resolved_content_type,
        )

        await asyncio.to_thread(self._s3_client.put_object, **put_kwargs)

        url = self._object_url(key)
        logger.info("Chat attachment uploaded successfully to %s", url)
        return url

    def _resolve_audio_key(
        self,
        *,
        customer_id: int,
        folder: str | None,
        extension: str,
        key: str | None,
    ) -> str:
        if key:
            return key

        if folder and folder not in {"assets/tts", "assets/chat", "assets/chat/1"}:
            return self._build_object_key(customer_id, folder, extension)

        return self.build_chat_audio_key(
            customer_id=customer_id,
            discussion_id=DEFAULT_DISCUSSION_ID,
            extension=extension,
        )

    def _build_object_key(self, customer_id: int, folder: str, extension: str) -> str:
        """Return an S3 key for ``customer_id`` within ``folder``."""

        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        unique_id = uuid.uuid4().hex[:8]
        return f"{customer_id}/{folder}/{timestamp}_{unique_id}.{extension}"

    def build_chat_audio_key(self, *, customer_id: int, discussion_id: int, extension: str) -> str:
        """Return an S3 key matching the legacy chat audio layout."""

        return self._build_chat_asset_key(
            customer_id=customer_id,
            discussion_id=discussion_id,
            asset_category="tts",
            suffix="audio",
            extension=extension,
        )

    def _build_chat_asset_key(
        self,
        *,
        customer_id: int,
        asset_category: str,
        extension: str,
        discussion_id: int = DEFAULT_DISCUSSION_ID,
        suffix: str | None = None,
    ) -> str:
        """Return an S3 key using the legacy ``assets/chat/<id>`` layout."""

        timestamp = datetime.now(UTC).strftime("%Y%m%d")
        random_part = uuid.uuid4().hex[:8]
        segments = [timestamp, random_part]
        if asset_category:
            segments.append(asset_category)
        if suffix:
            segments.append(suffix)
        filename = "_".join(segments) + f".{extension}"
        return f"{customer_id}/assets/chat/{discussion_id}/{filename}"

    def _object_url(self, key: str) -> str:
        """Return the public URL for ``key``."""

        if self._region:
            return f"https://{self._bucket_name}.s3.{self._region}.amazonaws.com/{key}"
        return f"https://{self._bucket_name}.s3.amazonaws.com/{key}"


__all__ = ["StorageService"]
