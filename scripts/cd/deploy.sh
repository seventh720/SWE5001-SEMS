#!/usr/bin/env bash
set -euo pipefail
umask 077
sha=${1:?Usage: deploy.sh commit-sha}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA'; exit 1; }
root=/home/ubuntu/swe5001
release=$(pwd -P)
release_id=${release##*/}
[[ "$release_id" =~ ^$sha(-[0-9]+-[0-9]+)?$ ]] || { echo 'Invalid release directory'; exit 1; }
test "$release" = "$root/releases/$release_id"
test -s "$root/.env"
test -s "$root/.secrets/jwt-private.pem"
mkdir -p "$root/backups"
# Serialize manual and Actions deployments on the host, too.
exec 9>"$root/.deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
ln -sfn "$root/.env" .env
ln -sfn "$root/.secrets" .secrets
test -s deployment/compose.images.json
# Registry credentials exist only for this invocation, including failed deployments.
auth_dir=$(mktemp -d)
cleanup() { sudo -n rm -rf "$auth_dir"; }
trap cleanup EXIT
if [ -n "${2:-}" ]; then
  sudo -n docker --config "$auth_dir" login ghcr.io -u "$2" --password-stdin
fi
python3 - "$sha" <<'CHECK'
import json,re,sys
lock=json.load(open('deployment/compose.images.json'))
assert lock['x-release-commit']==sys.argv[1], 'Release/image commit mismatch'
assert set(lock['services'])=={'identity','event-catalog','admission','web','postgres','gateway','caddy'}
assert all(re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}', s['image']) for s in lock['services'].values())
CHECK
compose=(sudo -n docker --config "$auth_dir" compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml -f deployment/compose.images.json)
# Host-owned shared proxy settings survive replacement of release directories.
if [ -f "$root/shared-proxy.compose.yaml" ]; then
  compose+=(-f "$root/shared-proxy.compose.yaml")
fi
"${compose[@]}" config --quiet
"${compose[@]}" pull
backup="$root/backups/pre-deploy-$sha-$(date -u +%Y%m%dT%H%M%SZ).dump"
"${compose[@]}" exec -T postgres pg_dump -U postgres -d sems -Fc > "$backup.partial"
test -s "$backup.partial"
mv "$backup.partial" "$backup"
trap 'echo "Deployment failed. Backup and release retained; inspect before retrying. Database rollback is manual." >&2' ERR
"${compose[@]}" up -d --no-build --pull never
# Nginx must resolve the new application container addresses.
"${compose[@]}" restart gateway
for service in identity event-catalog admission; do
  curl --fail --silent --show-error --retry 30 --retry-all-errors --retry-delay 3 --max-time 5 \
    "http://127.0.0.1:18080/health/$service" > /dev/null
done
if [ -f "$root/deployed-sha" ]; then
  cp "$root/deployed-sha" "$root/previous-deployed-sha"
fi
printf '%s\n' "$sha" > "$root/deployed-sha"
if [ -L "$root/current" ]; then
  ln -sfn "$(readlink "$root/current")" "$root/previous"
fi
ln -sfn "$release" "$root/current"
echo "Deployed $sha; database backup: $backup"
