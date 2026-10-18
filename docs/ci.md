# CI operations

Three independently visible checks run on main pushes and PRs targeting main:

| Check | Work and evidence |
|---|---|
| Backend tests and build | Java 21, Maven clean verify, all service unit tests, JaCoCo line/branch reports, JAR artifacts |
| Frontend tests and build | Node 22, npm ci, Vitest V8 coverage, TypeScript and Vite build, web-dist artifact |
| PostgreSQL and API acceptance | Downloads the tested JARs/web bundle, builds Compose images, runs readiness, schema isolation, authentication, draft, ticket/publication and restart recovery checks |

Backend and frontend run concurrently. Integration runs only after both succeed. Use all three named checks when configuring branch protection; this change does not modify repository protection settings.

Reports and diagnostics are retained for seven days, including failed runs. Missing coverage is shown as N/A, never 100%. Backend coverage is unit-test coverage, reported per service and as a weighted total only when all reports exist. The real HTTP/database tests run separately and are **not included** in these percentages. No percentage threshold is imposed yet; failed tests/typechecking/builds do block their jobs. This establishes an honest baseline for later improvements.

Telegram uses repository Actions secrets `TELEGRAM_TOKEN` and `TELEGRAM_TO`. Messages list backend, frontend and integration status plus available line/branch coverage and a run link. Fork/Dependabot PRs and cancelled runs do not notify. Notification failure does not override build status. [GitHub secret behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) and [Telegram API](https://core.telegram.org/bots/api#sendmessage).

Local commands: `mvn verify`, `npm --prefix apps/web run test:coverage`, `npm --prefix apps/web run build`, then run Compose and `bash scripts/check-db-isolation.sh`. Load `.env` into the shell before `python3 scripts/organization-acceptance.py`. The latter creates unique test data and intentionally stops Admission and restarts Catalog/gateway; run it only against a disposable local/CI Compose environment. Use `COMPOSE_PROJECT_NAME` to select a dedicated test project.

The first [cloud staging deployment](cloud-staging.md) is live. A main-only deployment job now packages the tested JARs/web assets, backs up the staging database, builds images on the host, deploys and checks HTTPS. See [deployment procedures](cloud-staging.md). Image registry publication, lint/contract conformance checks and security scan gates remain pending. Booking consistency, staff check-in and summaries have local acceptance coverage. Container restart recovery includes publication and whole-event cancellation recovery, not evidence that the final cloud recovery/scaling targets have been achieved.

Integration now starts two Admission replicas and runs booking acceptance, including publication regression, 100 competing requests for 10 places, same-key races, per-attendee isolation and repeated cancellation. This is a local correctness check, not a cloud throughput or recovery-target measurement.

Registration acceptance additionally checks requested field validation, category/theme persistence, combined search/filtering, information-aware retries and cross-organizer denial. Existing booking/publication tests still run.

## Current integration entry points

The workflow runs organization-acceptance.py (including the earlier editor/booking regression chain), organization-security-acceptance.py, event-directory-acceptance.py, visibility-acceptance.py, notifications-acceptance.py, membership-notifications-acceptance.py, organization-governance-acceptance.py, event-cancellation-acceptance.py, predeployment-fixes-acceptance.py and organization-migration-acceptance.py. Use the same entry points after builds, readiness and schema-isolation checks in a disposable stack with two Admission replicas. Load that stack’s environment and set SEMS_BASE_URL, SEMS_ENV_FILE and SEMS_COMPOSE_FILE as appropriate.

Give the test stack distinct project, network, volume and host-port names; changing COMPOSE_PROJECT_NAME alone does not override explicitly named Compose resources. Never inject failures into the shared working instance. Historical results are retained in [evidence](evidence/); configured workflow jobs are not proof of a successful current CI run.

P1/P2 业务回归新增 `scripts/business-fixes-acceptance.py`（需先于其他验收、在全新独立数据库运行）和 `scripts/gateway-scaling-acceptance.py`。两者已接入 integration job；运行时会创建测试数据并停启/扩缩测试服务。`scripts/observe-platform.py 10m` 可采集不含凭据的日志及资源快照。

Current measured unit/component coverage and gaps are recorded in [test coverage](test-coverage.md). The event-directory acceptance entry point is added in the current working tree; its local run passed, but its CI run is pending the PR checks and merge. It tests organization-wide title search, stable pages, literal wildcard characters, shared organizer editing/publication and live demotion.
