#!/usr/bin/env bash
set -euo pipefail
umask 077
sha=${1:?Usage: deploy.sh commit-sha}
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA'; exit 1; }
root=/home/ubuntu/swe5001
release="$root/releases/$sha"
test "$(pwd -P)" = "$release"
test -s "$root/.env"
test -s "$root/.secrets/jwt-private.pem"
mkdir -p "$root/backups"
# Serialize manual and Actions deployments on the host, too.
exec 9>"$root/.deploy.lock"
flock -n 9 || { echo 'Another deployment is running'; exit 1; }
ln -sfn "$root/.env" .env
ln -sfn "$root/.secrets" .secrets
compose=(sudo -n docker compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml)
"${compose[@]}" config --quiet
"${compose[@]}" build
backup="$root/backups/pre-deploy-$sha-$(date -u +%Y%m%dT%H%M%SZ).dump"
"${compose[@]}" exec -T postgres pg_dump -U postgres -d sems -Fc > "$backup.partial"
test -s "$backup.partial"
mv "$backup.partial" "$backup"
trap 'echo "Deployment failed. Backup and release retained; inspect before retrying. Database rollback is manual." >&2' ERR
"${compose[@]}" up -d --no-build
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
ln -sfn "$release" "$root/current"
echo "Deployed $sha; database backup: $backup"
