#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p lint-reports
summary=lint-reports/summary.txt
printf 'Lint report\nCommit: %s\nUTC: %s\n\n' "$(git rev-parse HEAD)" "$(date -u +%FT%TZ)" > "$summary"
result=0
check() {
    local name=$1
    shift
    local status=0
    "$@" > "lint-reports/$name.txt" 2>&1 || status=$?
    cat "lint-reports/$name.txt"
    if [ "$status" -eq 0 ]; then
        printf '%s: PASS\n' "$name" >> "$summary"
    else
        printf '%s: FAIL (exit %s)\n' "$name" "$status" >> "$summary"
        result=1
    fi
}
check eslint npm --prefix apps/web run lint
check checkstyle mvn -B -ntp validate
check actionlint docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.7
shell_syntax() {
    local file
    for file in scripts/*.sh scripts/*/*.sh; do
        bash -n "$file" || return
    done
}
check shell-syntax shell_syntax
cat "$summary"
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
    cat "$summary" >> "$GITHUB_STEP_SUMMARY"
fi
exit "$result"
