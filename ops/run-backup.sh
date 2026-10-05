#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if ! python3 ops/backup.py; then
    printf '%s' 'Encrypted backup job failed. Review the private backup job log.' | docker exec -i spandan_backend python -m scripts.operator_alert
    exit 1
fi
