import asyncio
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import SpandanException

IMAGE_SIGNATURES = {
    "jpg": lambda data: data.startswith(b"\xff\xd8\xff"),
    "png": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "webp": lambda data: data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}


def _detect_extension(data: bytes) -> Optional[str]:
    return next((extension for extension, matches in IMAGE_SIGNATURES.items() if matches(data)), None)


async def store_profile_photo(file: UploadFile, previous_url: Optional[str]) -> str:
    maximum_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    data = await file.read(maximum_bytes + 1)
    await file.close()
    if not data:
        raise SpandanException(code="VALIDATION_ERROR", message="The image file is empty.")
    if len(data) > maximum_bytes:
        raise SpandanException(
            code="PAYLOAD_TOO_LARGE",
            message=f"Profile photos must be {settings.MAX_UPLOAD_SIZE_MB} MB or smaller.",
            status_code=413,
        )

    extension = _detect_extension(data)
    allowed_content_types = {"image/jpeg", "image/png", "image/webp"}
    if extension is None or file.content_type not in allowed_content_types:
        raise SpandanException(
            code="VALIDATION_ERROR",
            message="Upload a valid JPEG, PNG, or WebP image.",
        )

    directory = Path(settings.UPLOAD_DIR) / "profiles"
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    destination = directory / filename
    await asyncio.to_thread(destination.write_bytes, data)

    if previous_url and previous_url.startswith("/uploads/profiles/"):
        previous_path = directory / Path(previous_url).name
        if previous_path != destination:
            try:
                await asyncio.to_thread(previous_path.unlink, missing_ok=True)
            except OSError:
                pass

    return f"/uploads/profiles/{filename}"
