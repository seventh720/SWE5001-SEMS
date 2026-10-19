#!/usr/bin/env bash
set -euo pipefail
repository=${GITHUB_REPOSITORY:?Required}
sha=${GITHUB_SHA:?Required}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 2
registry="ghcr.io/$(printf '%s' "$repository" | tr '[:upper:]' '[:lower:]')"
for service in identity event-catalog admission web postgres gateway caddy; do
  image="$registry/$service:$sha"
  docker push "$image"
  docker image inspect "$image" --format '{{index .RepoDigests 0}}' > "release-images/$service.ref"
done
python3 scripts/cd/lock-images.py release-images "$sha" deployment/compose.images.json
