# CI operations

The workflow runs on main pushes and PRs targeting main. PR #20 is merged as `2f169d6`; [main run 39466717243, attempt 2](https://github.com/seventh720/SWE5001-SEMS/actions/runs/39466717243/attempts/2) passed all checks, image publication and the executed Lightsail staging deployment. The first attempt failed during Caddy's Go checksum-service download; retrying the failed jobs succeeded with verification enabled. The six quality checks are:

| Check | Work and evidence |
|---|---|
| Lint | ESLint, Checkstyle, actionlint and shell syntax; lint-report artifact |
| Backend · Unit Tests & Build | Java 21, Maven clean verify, all service unit tests, JaCoCo line/branch reports, JAR artifacts |
| Frontend · Tests & Build | Node 22, npm ci, Vitest V8 coverage, TypeScript and Vite build, web-dist artifact |
| Backend · Integration Tests | Downloads tested artifacts, runs real API/database regression with two Admission replicas, then a tiny k6 smoke and inventory audit |
| Security · SAST, Dependencies & Secrets | Strict Semgrep Java/TypeScript rules; Trivy secrets, npm lockfile and packaged Java dependency checks |
| Images · Scan, Smoke Test & Publish | Build/scan all runtime images, then run readiness and API/load smoke against those exact tags without rebuilding; only main pushes to GHCR and uploads a digest-only Compose overlay |

Backend and frontend run concurrently. Integration and source security depend on both; image scanning/publication depends on lint and all four. Deployment requires all checks. Configure all six named checks in branch protection; this change does not modify repository settings.

Reports and diagnostics are retained for seven days, including failed runs. Missing coverage is shown as N/A, never 100%. Backend coverage is unit-test coverage, reported per service and as a weighted total only when all reports exist. The real HTTP/database tests run separately and are **not included** in these percentages. No percentage threshold is imposed yet; failed tests/typechecking/builds do block their jobs. This establishes an honest baseline for later improvements.

Telegram uses repository Actions secrets `TELEGRAM_TOKEN` and `TELEGRAM_TO`. Messages use ✅ success, ❌ failure, 🚫 cancelled and ⏭️ skipped for individual checks. They include PR/branch, source commit, actor, run/attempt, unit/component coverage and a logs/artifacts link. Notification waits for staging deployment and distinguishes a skipped/superseded deployment from a successful deployment. PRs report image scanning without implying publication. Fork/Dependabot PRs and cancelled runs do not notify. Notification failure does not override build status. [GitHub secret behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) and [Telegram API](https://core.telegram.org/bots/api#sendmessage).

Local commands: `mvn verify`, `npm --prefix apps/web run test:coverage`, `npm --prefix apps/web run build`, then run Compose and `bash scripts/check-db-isolation.sh`. Load `.env` into the shell before `python3 scripts/organization-acceptance.py`. The latter creates unique test data and intentionally stops Admission and restarts Catalog/gateway; run it only against a disposable local/CI Compose environment. Use `COMPOSE_PROJECT_NAME` to select a dedicated test project.

Main-only delivery builds/scans tested artifacts in CI, publishes GHCR digests, then backs up staging, pulls the locked images and checks HTTPS. It does not rebuild images on the deployment host. The successful run above deployed `2f169d6`; staging API business acceptance and the later cloud capacity baseline are recorded separately in [project status](progress.md). Follow the [deployment procedures](cloud-staging.md), including the existing shared-proxy override. OpenAPI contract conformance and the final cloud scaling/recovery experiments remain outstanding. The main branch protection API reported no traditional branch protection on 2026-10-20; this PR does not change repository protection settings.

Integration now starts two Admission replicas and runs booking acceptance, including publication regression, 100 competing requests for 10 places, same-key races, per-attendee isolation and repeated cancellation. This is a local correctness check, not a cloud throughput or recovery-target measurement.

Registration acceptance additionally checks requested field validation, category/theme persistence, combined search/filtering, information-aware retries and cross-organizer denial. Existing booking/publication tests still run.

## Current integration entry points

Deployment-bundle validation also runs offline Python checks for release locks, result comparison, local experiment execution and the cloud capacity ladder. CI does not run the cloud load generator or use staging credentials.

The workflow runs organization-acceptance.py (including the earlier editor/booking regression chain), organization-security-acceptance.py, event-directory-acceptance.py, organization-management-acceptance.py, visibility-acceptance.py, notifications-acceptance.py, membership-notifications-acceptance.py, organization-governance-acceptance.py, event-cancellation-acceptance.py, predeployment-fixes-acceptance.py, organization-migration-acceptance.py and catalog-recovery-acceptance.py. Use the same entry points after builds, readiness and schema-isolation checks in a disposable stack with two Admission replicas. Load that stack’s environment and set SEMS_BASE_URL, SEMS_ENV_FILE and SEMS_COMPOSE_FILE as appropriate.

`organization-management-acceptance.py` is a standalone real-API regression for organization-admin totals, member/event combined filters before paging, access isolation, registration guidance, the booking/check-in/cancellation loop and ended-event editing rejection. It creates four unique accounts, two organizations and eight events. Default mode is restricted to disposable localhost Compose and uses SQL only to move its own fixture timestamps; it never stops services. CI saves the credential-free fixture/cleanup report in `integration-diagnostics`.

```bash
# Load the disposable stack's admin environment first, as above.
python3 scripts/organization-management-acceptance.py --report ci-logs/organization-management.json
```

The separate `--live --base-url https://swe5001.seventh720.com` mode uses public APIs only and waits for an event to end naturally. Use it only for an explicitly requested staging acceptance run with agreement on data retention. Both modes attempt cleanup in `finally`: cancel fixture offerings, soft-delete fixture organizations and verify organization access is revoked. Accounts, orders, notifications and check-in history remain; this is not a database purge, and the product has no account-delete/disable API. Check the report's `cleanup.complete` and `failedFixtureIds`; a process kill or service outage may require resuming cleanup manually using only those fixture IDs. Reports contain no passwords, tokens or ticket credentials. They do contain generated account emails and fixture IDs, so live reports stay in ignored `.secrets/acceptance/`.

Give the test stack distinct project, network, volume and host-port names; changing COMPOSE_PROJECT_NAME alone does not override explicitly named Compose resources. Never inject failures into the shared working instance. Historical results are retained in [evidence](evidence/); configured workflow jobs are not proof of a successful current CI run.

P1/P2 业务回归包含 `scripts/business-fixes-acceptance.py`（需先于其他验收、在全新独立数据库运行）和 `scripts/gateway-scaling-acceptance.py`。两者已接入 integration job；运行时会创建测试数据并停启/扩缩测试服务。`scripts/observe-platform.py 10m` 可采集不含凭据的日志及资源快照。

Current test counts, historical measured unit/component coverage and remaining gaps are recorded in [test coverage](test-coverage.md). The event-directory acceptance entry point is included in the workflow; both its local run and PR #14 integration job passed. It tests organization-wide title search, stable pages, literal wildcard characters, shared organizer editing/publication and live demotion.

See [security policy and scoped exceptions](security.md) and [performance/availability experiments](performance-and-availability.md). `scripts/cd/test-release.py` rejects floating image references and invalid commit IDs; `scripts/performance/test-tools.py` verifies comparison semantics. A small CI smoke proves scripts run, not cloud scaling benefit.

## Lint and check naming (2026-10-20)

The workflow is named `CI`, following SWE5006's `Area · Purpose` check naming. `Lint` runs ESLint's JavaScript/TypeScript recommended rules, a small Checkstyle correctness ruleset for main/test Java, actionlint and shell syntax checks. It uploads `lint-report` even on failure. Run `bash scripts/ci/lint.sh` locally (Docker is needed for actionlint). This does not introduce formatting-only rewrites or claim API contract conformance. Lint is a prerequisite for image publication/deployment and is included in the notification summary.

If branch protection names checks explicitly, update its required check names to match the workflow during rollout; renaming display names does not migrate repository settings automatically.

`catalog-recovery-acceptance.py` joins integration acceptance: it exercises booking, idempotent replay and current-event receipts during a Catalog cold restart, checks bounded failure with all Catalog replicas down, then checks recovered inventory. It temporarily scales Catalog and restores the original count. Use only a disposable stack. Compose passes `CATALOG_URL=http://gateway:8080`; the Docker-only listener applies bounded failover to reads. Only the read-only batch-details POST allows replay after being sent; prepare-sales does not. Port 8080 is not published and public `/internal/` stays blocked; destination service-token authentication remains required.

### IDE Maven lifecycle mapping

The Checkstyle `lint` execution carries `<?m2e ignore?>`, the [m2e execution mapping](https://eclipse.dev/m2e/documentation/release-notes-17.html) for IDE automatic builds. It prevents the “Plugin execution not covered by lifecycle configuration” marker without disabling `mvn validate`, `mvn verify` or CI lint. If an existing VS Code Java workspace retains the marker, reload its Maven projects (or run **Java: Reload Projects**). IDE marker refresh is separate from command-line build validation.
