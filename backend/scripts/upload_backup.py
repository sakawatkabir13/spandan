"""Upload an encrypted snapshot from stdin to private S3-compatible storage."""

import sys

import boto3

from app.core.config import settings

if settings.S3_BACKUP_BUCKET:
    name = sys.argv[1]
    if "/" in name or not name.startswith("spandan-"):
        raise RuntimeError("Invalid backup filename")
    client = boto3.client(
        "s3", region_name=settings.S3_REGION, endpoint_url=settings.S3_ENDPOINT_URL or None
    )
    client.upload_fileobj(
        sys.stdin.buffer,
        settings.S3_BACKUP_BUCKET,
        f"backups/{name}",
        ExtraArgs={"ServerSideEncryption": "AES256"},
    )
    print("Encrypted off-site backup uploaded")
else:
    # Consume the pipe even when off-site storage is not configured.
    while sys.stdin.buffer.read(1024 * 1024):
        pass
    print("Off-site backup disabled: S3_BACKUP_BUCKET not configured")
