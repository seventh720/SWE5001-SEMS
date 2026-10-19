#!/usr/bin/env bash
set -euo pipefail
# Build and scan each runtime image. Main publishes only after this script succeeds.
repository=${GITHUB_REPOSITORY:?Required}
sha=${GITHUB_SHA:?Required}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
registry="ghcr.io/$(printf '%s' "$repository" | tr '[:upper:]' '[:lower:]')"
mkdir -p ci-logs/security release-images
for service in identity event-catalog admission web postgres gateway caddy; do
  image="$registry/$service:$sha"
  case "$service" in
    web) docker build --pull --label "org.opencontainers.image.source=https://github.com/$repository" -t "$image" apps/web ;;
    postgres|gateway|caddy) docker build --pull --label "org.opencontainers.image.source=https://github.com/$repository" -t "$image" "deployment/$service" ;;
    *) docker build --pull --label "org.opencontainers.image.source=https://github.com/$repository" -f "services/$service/Dockerfile" -t "$image" . ;;
  esac
  bash scripts/security/scan.sh image "$image" "ci-logs/security/$service.json"
done
# Publication is a separate step, after image-smoke.sh verifies these exact images.
python3 - "$registry" "$sha" <<'LOCK'
import json,sys
from pathlib import Path
services=['identity','event-catalog','admission','web','postgres','gateway']
images={s:{'image':f'{sys.argv[1]}/{s}:{sys.argv[2]}','pull_policy':'never'} for s in services}
Path('release-images/compose.test.json').write_text(json.dumps({'services':images},indent=2))
LOCK
