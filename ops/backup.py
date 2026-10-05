#!/usr/bin/env python3
"""Encrypted DB/uploads snapshots. Run as the deployment user; never print secrets."""

import argparse
import fcntl
import hashlib
import hmac
import os
import subprocess
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("SPANDAN_ROOT", str(Path(__file__).resolve().parents[1])))
BACKUPS = ROOT / ".runtime" / "backups"
KEY = ROOT / ".runtime" / "backup.key"


def digest(path):
    mac = hmac.new(KEY.read_bytes(), digestmod=hashlib.sha256)
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            mac.update(chunk)
    return mac.hexdigest()


def restore(archive, destination):
    if not hmac.compare_digest(archive.with_suffix(".mac").read_text().strip(), digest(archive)):
        raise RuntimeError("Backup integrity check failed")
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Decrypt only to a user-selected private directory. Database restore is a separate action.
    subprocess.run(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-pass",
            f"file:{KEY}",
            "-in",
            str(archive),
            "-out",
            str(destination / "snapshot.tar"),
        ],
        check=True,
    )
    with tarfile.open(destination / "snapshot.tar") as tar:
        if set(tar.getnames()) != {"database.dump", "uploads.tar.gz"}:
            raise RuntimeError("Unexpected archive contents")
        tar.extractall(destination, filter="data")
    (destination / "snapshot.tar").unlink()


def backup():
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not KEY.exists():
        with KEY.open("x") as file:
            file.write(os.urandom(64).hex())
        KEY.chmod(0o600)
    with tempfile.TemporaryDirectory(dir=BACKUPS) as temp:
        folder = Path(temp)
        with (folder / "database.dump").open("wb") as file:
            subprocess.run(
                [
                    "docker",
                    "exec",
                    "spandan_db",
                    "sh",
                    "-c",
                    'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"',
                ],
                stdout=file,
                check=True,
            )
        with (folder / "uploads.tar.gz").open("wb") as file:
            subprocess.run(
                ["docker", "exec", "spandan_backend", "tar", "czf", "-", "-C", "/app/uploads", "."],
                stdout=file,
                check=True,
            )
        tar_path = folder / "snapshot.tar"
        with tarfile.open(tar_path, "w") as tar:
            for name in ("database.dump", "uploads.tar.gz"):
                tar.add(folder / name, arcname=name)
        destination = BACKUPS / f"spandan-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.enc"
        subprocess.run(
            [
                "openssl",
                "enc",
                "-aes-256-cbc",
                "-salt",
                "-pbkdf2",
                "-iter",
                "200000",
                "-pass",
                f"file:{KEY}",
                "-in",
                str(tar_path),
                "-out",
                str(destination),
            ],
            check=True,
        )
        destination.with_suffix(".mac").write_text(digest(destination))
        # Optional off-site upload uses credentials already configured in the backend.
        config = ROOT / ".env.production"
        offsite = config.exists() and any(
            line.startswith("S3_BACKUP_BUCKET=") and line.partition("=")[2].strip().strip("\"'")
            for line in config.read_text().splitlines()
        )
        if offsite:
            for path in (destination, destination.with_suffix(".mac")):
                with path.open("rb") as file:
                    subprocess.run(
                        [
                            "docker",
                            "exec",
                            "-i",
                            "spandan_backend",
                            "python",
                            "-m",
                            "scripts.upload_backup",
                            path.name,
                        ],
                        stdin=file,
                        check=True,
                    )
        else:
            print("Off-site storage is not configured")
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=max(2, int(os.environ.get("BACKUP_RETENTION_DAYS", "14")))
        )
        for old in BACKUPS.glob("spandan-*.enc"):
            if datetime.fromtimestamp(old.stat().st_mtime, timezone.utc) < cutoff:
                old.unlink()
                old.with_suffix(".mac").unlink(missing_ok=True)
        print(f"Encrypted snapshot saved: {destination.name}")


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore-archive", type=Path)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    (ROOT / ".runtime").mkdir(mode=0o700, exist_ok=True)
    with (ROOT / ".runtime/backup.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.restore_archive:
            if not args.destination:
                parser.error("--destination is required for decryption")
            restore(args.restore_archive, args.destination)
        else:
            backup()
