#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p .runtime
exec flock -n .runtime/maintenance.lock docker compose --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml exec -T backend python -m scripts.worker < /dev/null
