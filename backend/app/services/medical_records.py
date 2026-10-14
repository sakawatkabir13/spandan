import asyncio
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import SpandanException

MAX_REPORT_BYTES = 5 * 1024 * 1024
MAX_REPORTS = 25
MAX_PATIENT_BYTES = 100 * 1024 * 1024


def private_directory():
    # Included in encrypted upload backups, but never served by PublicUploads.
    return Path(settings.UPLOAD_DIR) / ".medical"


def report_cipher():
    secret = settings.MFA_ENCRYPTION_KEY or settings.JWT_SECRET_KEY
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("medical-reports:" + secret).encode()).digest()))


async def store_report(key, content):
    folder = private_directory()
    await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True, mode=0o700)
    encrypted = await asyncio.to_thread(report_cipher().encrypt, content)
    path = folder / key
    def write():
        with path.open("xb") as file:
            path.chmod(0o600)
            file.write(encrypted)
    await asyncio.to_thread(write)


async def read_report(key):
    try:
        encrypted = await asyncio.to_thread((private_directory() / key).read_bytes)
        return await asyncio.to_thread(report_cipher().decrypt, encrypted)
    except (OSError, InvalidToken):
        raise SpandanException("REPORT_UNAVAILABLE", "This report is temporarily unavailable. Contact support.", 503)


async def remove_report(key):
    await asyncio.to_thread((private_directory() / key).unlink, missing_ok=True)


def detect_report_type(content):
    if content.startswith(b"%PDF-") and b"%%EOF" in content[-2048:]:
        return "application/pdf"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None
