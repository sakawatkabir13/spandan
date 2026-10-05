#!/usr/bin/env python3
"""Public readiness, disk, backup freshness and recent server-error monitoring."""

import json
import os
import shutil
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
issues = []
try:
    with urllib.request.urlopen(
        "https://spandan.cuetinsights.dev/health/ready", timeout=12
    ) as response:
        payload = json.load(response)
        if response.status != 200 or payload.get("data", {}).get("status") != "OK":
            issues.append("Readiness response is not healthy JSON")
except Exception:
    issues.append("Public database readiness check failed")
disk = shutil.disk_usage(root)
if disk.free < 1024**3:
    issues.append("Less than 1 GiB free disk space")
backups = list((root / ".runtime/backups").glob("spandan-*.enc"))
if (
    not backups
    or datetime.now(timezone.utc).timestamp() - max(p.stat().st_mtime for p in backups) > 26 * 3600
):
    issues.append("Encrypted snapshot is missing or older than 26 hours")
logs = subprocess.run(
    ["docker", "logs", "--since", "5m", "spandan_backend"],
    capture_output=True,
    text=True,
    check=False,
)
errors = sum(
    "request_complete" in line and any(f"status={status}" in line for status in range(500, 600))
    for line in (logs.stdout + logs.stderr).splitlines()
)
if errors:
    issues.append(f"{errors} server errors in the last five minutes")
summary = json.dumps(
    {
        "time": datetime.now(timezone.utc).isoformat(),
        "healthy": not issues,
        "issues": issues,
        "disk_free_bytes": disk.free,
    }
)
os.umask(0o077)
folder = root / ".runtime"
folder.mkdir(mode=0o700, exist_ok=True)
previous = folder / "monitor-issues.json"
old = json.loads(previous.read_text()) if previous.exists() else []
if issues != old:
    if issues:
        subprocess.run(
            ["docker", "exec", "-i", "spandan_backend", "python", "-m", "scripts.operator_alert"],
            input="; ".join(issues),
            text=True,
            check=True,
        )
    previous.write_text(json.dumps(issues))
(folder / "monitor.json").write_text(summary)
print(summary)
