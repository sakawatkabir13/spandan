#!/usr/bin/env python3
"""Restore a snapshot in an isolated disposable database; never target the application DB."""
import argparse
import os
import secrets
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

import backup


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], check=True, capture_output=True, **kwargs)


def verify(archive):
    name = "spandan-restore-check-" + secrets.token_hex(5)
    with tempfile.TemporaryDirectory(prefix="spandan-restore-check-") as temp:
        root = Path(temp)
        backup.restore(archive, root / "snapshot")
        environment = root / "postgres.env"
        environment.write_text("POSTGRES_USER=postgres\nPOSTGRES_DB=spandan_restore_check\nPOSTGRES_PASSWORD=" + secrets.token_urlsafe(32) + "\n")
        environment.chmod(0o600)
        try:
            # No published port, mounted application volume, or network access.
            docker("run", "--detach", "--name", name, "--network", "none", "--env-file", str(environment), "postgres:16-alpine")
            for _ in range(45):
                # The entrypoint briefly starts a Unix-socket-only server during initialization.
                # TCP becomes ready only after that server stops and the final database starts.
                if subprocess.run(["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres", "-d", "spandan_restore_check"], capture_output=True).returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Isolated restore database did not become ready")
            with (root / "snapshot/database.dump").open("rb") as source:
                docker("exec", "-i", name, "pg_restore", "--exit-on-error", "--no-owner", "--no-privileges", "-U", "postgres", "-d", "spandan_restore_check", stdin=source)
            def query(sql):
                return docker("exec", name, "psql", "-At", "-U", "postgres", "-d", "spandan_restore_check", "-c", sql).stdout.decode().strip()
            revision = query("SELECT version_num FROM alembic_version")
            counts = query("SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM appointments), (SELECT count(*) FROM medical_reports)")
            keys = set(query("SELECT storage_key FROM medical_reports").splitlines())
            with tarfile.open(root / "snapshot/uploads.tar.gz") as uploads:
                names = set()
                for member in uploads.getmembers():
                    path = PurePosixPath(member.name)
                    if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                        raise RuntimeError("Unsafe upload archive entry")
                    if member.isfile():
                        names.add(str(path))
                        stream = uploads.extractfile(member)
                        while stream.read(1024 * 1024):
                            pass
                if any(f".medical/{key}" not in names for key in keys):
                    raise RuntimeError("Restored report metadata references missing upload files")
            return {"migration": revision, "users_appointments_reports": counts, "upload_files": len(names)}
        finally:
            subprocess.run(["docker", "rm", "--force", "--volumes", name], capture_output=True)


if __name__ == "__main__":
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    archive = args.archive or max(backup.BACKUPS.glob("spandan-*.enc"), key=lambda p: p.stat().st_mtime, default=None)
    if not archive:
        parser.error("Create a backup first, or provide --archive")
    try:
        print("Isolated restoration verified:", verify(archive.resolve()))
    except Exception as exc:
        # Never include command arguments or environment secrets in failure output.
        raise SystemExit(f"Restoration check failed ({type(exc).__name__}). Original application data was not modified.") from None
