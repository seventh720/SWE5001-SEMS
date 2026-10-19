#!/usr/bin/env bash
set -euo pipefail
# Run in a clean CI checkout; do not mount a workstation's .env/.secrets into scanners.
mkdir -p ci-logs/security
python3 scripts/security/check-spring-scope.py
case "${1:-source}" in
  source)
    for service in identity event-catalog admission; do
      test -s "services/$service/target/$service-service-0.1.0-SNAPSHOT.jar"
    done
    docker run --rm -v "$PWD:/src" -w /src semgrep/semgrep:1.181.0 \
      semgrep scan --config p/java --config p/typescript --error --strict --metrics=off \
      --exclude '**/target/**' --exclude '**/dist/**' --exclude '**/node_modules/**' \
      --json --output ci-logs/security/semgrep.json services apps/web/src
    docker run --rm -v "$PWD:/src" -v sems-trivy-cache:/root/.cache/trivy -w /src aquasec/trivy:0.75.0 fs \
      --scanners vuln,secret --severity HIGH,CRITICAL --exit-code 1 \
      --skip-dirs .git --skip-dirs apps/web/node_modules --skip-dirs ci-logs \
      --skip-files '**/pom.xml' --skip-files pom.xml --offline-scan --quiet \
      --format json --output ci-logs/security/trivy-source.json .
    # rootfs discovers nested Maven packages inside the tested Spring Boot JARs.
    docker run --rm -v "$PWD:/src" -v sems-trivy-cache:/root/.cache/trivy -w /src aquasec/trivy:0.75.0 rootfs \
      --ignorefile scripts/security/trivyignore.yaml --show-suppressed \
      --scanners vuln --severity HIGH,CRITICAL --exit-code 1 --offline-scan --quiet \
      --skip-files '**/pom.xml' --format json --output ci-logs/security/trivy-java.json services
    ;;
  image)
    image=${2:?Image reference required}
    report=${3:?Report file required}
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$PWD:/src" \
      -v sems-trivy-cache:/root/.cache/trivy -w /src \
      aquasec/trivy:0.75.0 image --ignorefile scripts/security/trivyignore.yaml --show-suppressed --scanners vuln,secret --severity HIGH,CRITICAL \
      --exit-code 1 --quiet --format json --output "$report" "$image"
    ;;
  *) echo 'Usage: scan.sh source | image reference report.json' >&2; exit 2 ;;
esac
