#!/usr/bin/env bash
set -euo pipefail
# Linux CI only: Docker host networking reaches the loopback-bound test gateway.
mkdir -p .performance ci-logs/performance
base=${SEMS_BASE_URL:-http://127.0.0.1:18080}
python3 scripts/performance/seed.py --base-url "$base" --output .performance/smoke.json --users 2 --events 4 --quota 10000
for mode in catalog booking; do
  docker run --rm --network host -u "$(id -u):$(id -g)" \
    -v "$PWD/scripts/performance:/scripts:ro" -v "$PWD/.performance:/data:ro" \
    -v "$PWD/ci-logs/performance:/results" \
    -e DATASET=/data/smoke.json -e "MODE=$mode" -e VUS=2 \
    -e WARMUP_SECONDS=2 -e DURATION_SECONDS=5 -e "RUN_ID=ci-$mode" \
    -e "SUMMARY_FILE=/results/$mode.json" -e "COMMIT=${GITHUB_SHA:-local}" \
    -e REPLICAS=catalog1-admission2 grafana/k6:1.3.0 run /scripts/load.js
done
python3 scripts/performance/audit.py --dataset .performance/smoke.json --output ci-logs/performance/inventory.json
