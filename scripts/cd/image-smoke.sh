#!/usr/bin/env bash
set -euo pipefail
# Fresh CI runner only. Reuse the exact locally built/scanned tags, never rebuild/pull.
registry="ghcr.io/$(printf '%s' "${GITHUB_REPOSITORY:?Required}" | tr '[:upper:]' '[:lower:]')"
docker run --rm -e SEMS_DOMAIN=benchmark.invalid \
  -v "$PWD/deployment/caddy/Caddyfile:/etc/caddy/Caddyfile:ro" \
  "$registry/caddy:${GITHUB_SHA:?Required}" caddy validate --config /etc/caddy/Caddyfile
bash scripts/setup-local.sh
compose=(docker compose --env-file .env -f deployment/compose.yaml -f "$PWD/release-images/compose.test.json")
cleanup() {
  "${compose[@]}" logs --no-color > ci-logs/image-smoke.log 2>&1 || true
  "${compose[@]}" down
}
trap cleanup EXIT
"${compose[@]}" up -d --no-build --pull never --scale admission=2
bash scripts/smoke.sh
set -a
# shellcheck disable=SC1091
source .env
set +a
export SEMS_COMPOSE_FILE="deployment/compose.yaml:$PWD/release-images/compose.test.json"
bash scripts/performance/smoke.sh
