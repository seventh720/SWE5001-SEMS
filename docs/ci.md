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

Local commands: `mvn verify`, `npm --prefix apps/web run test:coverage`, `npm --prefix apps/web run build`, then run Compose and `bash scripts/check-db-isolation.sh`. Load `.env` into the shell before `python3 scripts/registration-acceptance.py`. The latter creates unique test data and intentionally stops Admission and restarts Catalog/gateway; run it only against a disposable local/CI Compose environment. Use `COMPOSE_PROJECT_NAME` to select a dedicated test project.

Cloud deployment, image registry publication, security scan gates, booking consistency and check-in remain pending. Container restart recovery here is publication recovery, not evidence that the final cloud recovery/scaling targets have been achieved.

Integration now starts two Admission replicas and runs booking acceptance, including publication regression, 100 competing requests for 10 places, same-key races, per-attendee isolation and repeated cancellation. This is a local correctness check, not a cloud throughput or recovery-target measurement.

Registration acceptance additionally checks requested field validation, category/theme persistence, combined search/filtering, information-aware retries and cross-organizer denial. Existing booking/publication tests still run.
