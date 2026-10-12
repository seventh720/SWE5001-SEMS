#!/usr/bin/env bash
set -euo pipefail
for service in identity catalog admission; do
  for other in identity catalog admission; do
    [[ "$service" == "$other" ]] && continue
    result=$(docker compose --env-file .env -f deployment/compose.yaml exec -T postgres \
      psql -U postgres -d sems -tAc "SELECT has_schema_privilege('${service}_app', '${other}', 'USAGE')")
    [[ "$result" == "f" ]] || { echo "Unexpected schema access: $service -> $other"; exit 1; }
  done
  result=$(docker compose --env-file .env -f deployment/compose.yaml exec -T postgres \
    psql -U postgres -d sems -tAc "SELECT has_schema_privilege('${service}_app', 'public', 'CREATE')")
  [[ "$result" == "f" ]] || exit 1
done
# Check an actual query as the Catalog role, not only metadata.
if docker compose --env-file .env -f deployment/compose.yaml exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U postgres -d sems -c 'SET ROLE catalog_app; SELECT * FROM identity.users' >/dev/null 2>&1; then
  echo 'Catalog unexpectedly read Identity data'; exit 1
fi
echo 'PASS: service schema isolation and denied cross-service query'
