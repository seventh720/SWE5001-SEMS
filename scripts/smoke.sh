#!/usr/bin/env bash
set -euo pipefail
base_url="${SEMS_BASE_URL:-http://localhost:8080}"
for service in identity event-catalog admission; do
  ready=false
  for attempt in {1..30}; do
    if body=$(curl --fail --silent --max-time 3 "$base_url/health/$service") &&
       python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("status") == "UP" else 1)' <<< "$body"; then
      ready=true
      break
    fi
    sleep 2
  done
  if [[ "$ready" != true ]]; then
    echo "Readiness check failed: $service" >&2
    exit 1
  fi
  echo "Ready through gateway: $service"
done
