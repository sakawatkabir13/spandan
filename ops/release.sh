#!/bin/sh
# Builds tagged images, snapshots data, migrates, verifies JSON health, and rolls back runtime images on failure.
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p .runtime
exec 9>.runtime/release.lock
flock -n 9
test -f .env.production
release_sha="$(git rev-parse --short=12 HEAD)"
previous_tag="$(cat .runtime/current-release 2>/dev/null || true)"
export RELEASE_TAG="$release_sha"
compose() { docker compose -p spandan --env-file .env.production -f docker-compose.prod.yml -f docker-compose.vps.yml "$@"; }
compose config --quiet
if [ "${SKIP_BUILD:-false}" = "true" ]; then
    docker image inspect "spandan-backend:$release_sha" "spandan-frontend:$release_sha" >/dev/null
else
    compose build --pull
fi
python3 ops/backup.py
if compose up -d --wait --wait-timeout 150; then
    if python3 -c 'import json,urllib.request; r=urllib.request.urlopen("http://127.0.0.1:8082/health/ready",timeout=10); assert json.load(r)["data"]["status"] == "OK"'; then
        printf '%s\n' "$previous_tag" > .runtime/previous-release
        printf '%s\n' "$release_sha" > .runtime/current-release
        echo "Production release $release_sha is healthy."
        exit 0
    fi
fi
if [ -n "$previous_tag" ]; then
    export RELEASE_TAG="$previous_tag"
    compose up -d --no-build --wait --wait-timeout 150
    echo "Release failed; previous runtime restored. Additive migrations remain applied." >&2
else
    echo "Initial production deployment failed. Recover using the preserved pre-release source and encrypted snapshot." >&2
fi
exit 1
