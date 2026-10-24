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
action_lint() {
    # Local workspaces may hold deployment credentials. Mount only workflow source.
    local task_lint_dir file status=0
    task_lint_dir=$(mktemp -d)
    mkdir -p "$task_lint_dir/.github/workflows" "$task_lint_dir/.git"
    for file in .github/workflows/*.yml .github/workflows/*.yaml; do
        if [ -f "$file" ]; then
            cp "$file" "$task_lint_dir/.github/workflows/"
        fi
    done
    for file in .github/actionlint.yaml .github/actionlint.yml; do
        if [ -f "$file" ]; then
            cp "$file" "$task_lint_dir/.github/"
        fi
    done
    docker run --rm --network none -v "$task_lint_dir:/repo:ro" -w /repo rhysd/actionlint:1.7.7 || status=$?
    rm -rf "$task_lint_dir"
    return "$status"
}
check actionlint action_lint
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
