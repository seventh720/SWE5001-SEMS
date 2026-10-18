#!/usr/bin/env bash
set -euo pipefail
# Run from the repository root after downloading this run's CI artifacts.
archive=${1:?Usage: package.sh output.tar.gz}
for service in identity event-catalog admission; do
  test -s "services/$service/target/$service-service-0.1.0-SNAPSHOT.jar"
done
test -s apps/web/dist/index.html
COPYFILE_DISABLE=1 tar -czf "$archive" \
  .dockerignore deployment \
  services/identity/Dockerfile services/identity/target/identity-service-0.1.0-SNAPSHOT.jar \
  services/event-catalog/Dockerfile services/event-catalog/target/event-catalog-service-0.1.0-SNAPSHOT.jar \
  services/admission/Dockerfile services/admission/target/admission-service-0.1.0-SNAPSHOT.jar \
  apps/web/Dockerfile apps/web/nginx.conf apps/web/dist scripts/cd/deploy.sh
