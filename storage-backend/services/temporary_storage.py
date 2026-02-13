"""
Utility helpers for persisting temporary uploads for downstream services.
Used for example when audio file is being uploaded temporarily for transcription
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fastapi import UploadFile

_TEMP_DIR: Final[Path] = Path(tempfile.gettempdir()) / "storage-backend-ng"


@dataclass(slots=True)
class StoredUpload:
    """Represents a file written to disk from an incoming upload."""

    path: Path
    filename: str
    content_type: str | None

    def open(self, mode: str = "rb"):
        """Open the stored file for downstream consumers."""

        return self.path.open(mode)


async def persist_upload_file(
    upload: UploadFile,
    *,
    customer_id: int,
    category: str = "audio",
    prefix: str = "upload_",
) -> StoredUpload:
    """Write an :class:`UploadFile` to a temporary location on disk.

    Files are organised under a customer specific directory to keep the temporary
    storage predictable during development and testing. The function returns a
    :class:`StoredUpload` instance describing the stored file.
    """

    suffix = Path(upload.filename or "").suffix
    customer_dir = _TEMP_DIR / str(customer_id) / category
    await asyncio.to_thread(customer_dir.mkdir, parents=True, exist_ok=True)
    await upload.seek(0)

    def _write() -> Path:
        fd, temp_path = tempfile.mkstemp(
            suffix=suffix or ".bin", prefix=prefix, dir=customer_dir
        )
        os.close(fd)
        destination = Path(temp_path)
        with destination.open("wb") as target:
            data = upload.file.read()
            if isinstance(data, str):
                data = data.encode()
            target.write(data)
        return destination

    path = await asyncio.to_thread(_write)
    return StoredUpload(
        path=path,
        filename=upload.filename or path.name,
        content_type=upload.content_type,
    )


__all__ = ["persist_upload_file", "StoredUpload"]
