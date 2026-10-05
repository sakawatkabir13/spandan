#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
exec 9>.runtime/release.lock
flock -n 9
RELEASE_TAG="$(cat .runtime/previous-release)"
test -n "$RELEASE_TAG"
export RELEASE_TAG
docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml up -d --no-build --wait --wait-timeout 150
printf '%s\n' "$RELEASE_TAG" > .runtime/current-release
echo "Runtime restored to $RELEASE_TAG. Database migrations are unchanged."
