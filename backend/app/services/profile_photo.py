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


async def remove_profile_photo(url):
    if not url:
        return
    if url.startswith('/uploads/profiles/'):
        path = Path(settings.UPLOAD_DIR) / 'profiles' / Path(url).name
        await asyncio.to_thread(path.unlink, missing_ok=True)
    elif settings.S3_BUCKET and settings.S3_PUBLIC_URL and url.startswith(settings.S3_PUBLIC_URL.rstrip('/') + '/profiles/'):
        import boto3
        client = boto3.client('s3', region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL or None)
        await asyncio.to_thread(client.delete_object, Bucket=settings.S3_BUCKET, Key='profiles/' + url.rsplit('/', 1)[-1])


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
    if settings.S3_BUCKET:
        from urllib.parse import urlparse

        import boto3
        if not settings.S3_PUBLIC_URL or urlparse(settings.S3_PUBLIC_URL).scheme != "https":
            raise SpandanException("STORAGE_UNAVAILABLE", "An HTTPS object storage URL is required.", 503)
        client = boto3.client("s3", region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL or None)
        key = f"profiles/{filename}"
        await asyncio.to_thread(client.put_object, Bucket=settings.S3_BUCKET, Key=key, Body=data, ContentType=file.content_type, ServerSideEncryption="AES256")
        prefix = settings.S3_PUBLIC_URL.rstrip("/") + "/profiles/"
        if previous_url and previous_url.startswith(prefix):
            await asyncio.to_thread(client.delete_object, Bucket=settings.S3_BUCKET, Key="profiles/" + previous_url[len(prefix):])
        return f"{settings.S3_PUBLIC_URL.rstrip('/')}/{key}"
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
