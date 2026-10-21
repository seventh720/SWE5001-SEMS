# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS is a shared event and ticketing platform built with React/TypeScript, three Spring Boot services and PostgreSQL.

Implemented: organization-scoped permissions, event publication/editing/pause/cancellation, free bookings, individual QR tickets, assigned-staff check-in, saved registrations, in-app notifications and an organization-admin overview. Event and member management support server-side search, combined filters and pagination. Ended events cannot be edited or reopened.

See [project status](docs/progress.md) for release evidence and next steps, [business rules](docs/functional-guide.md) for permissions and metric definitions, and [test coverage](docs/test-coverage.md) for verification limits. JWTs last one hour. Check-in opens 15 minutes before the event starts and closes 15 minutes after it starts (exclusive), or at the event end if earlier.

## 1. Architecture and permissions

Identity owns accounts, organizations, memberships and invitations. Event Catalog owns events, visibility, publication and revisions. Admission owns inventory, bookings, tickets, check-in and notifications. Each service has separate schemas, credentials and migrations; cross-service operations use authenticated HTTP.

Platform ADMIN manages platform accounts and organization provisioning. Organization ORG_ADMIN, ORGANIZER and MEMBER roles govern business access; check-in also requires event assignment. Legacy global ORGANIZER/STAFF claims do not grant business access. Existing installations must follow the [organization upgrade](docs/organization-upgrade.md) and [notification deployment](docs/in-app-notifications.md) instructions.

## 2. Local setup

Requires Java 21, Maven 3.9+, Node.js 22, npm, OpenSSL, Python 3 and Docker Compose v2. Check `mvn -version` uses Java 21; a newer compiler with `--release 21` is not equivalent to the CI compiler.

```bash
git clone git@github.com:seventh720/SWE5001-SEMS.git
cd SWE5001-SEMS
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web test
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d
bash scripts/smoke.sh
```

Open [the local platform](http://localhost:18080). Setup generates `.env` and `.secrets/` without overwriting existing credentials. Re-running it on an existing setup appends missing internal service tokens; it does not rotate database passwords or RSA keys. The initial admin email is `admin@example.com`; read its random `SEMS_BOOTSTRAP_ADMIN_PASSWORD` from your local `.env`. Do not commit or share that file. Clear bootstrap settings after initialization; the persisted admin can still log in.

Database credentials are applied only when a new volume is initialized. Editing `.env` does not rotate existing database passwords. Stop while preserving data:

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

For frontend development, run `npm --prefix apps/web run dev`; port 15173 proxies APIs to the gateway on 18080. The production frontend is served at the gateway root. Date inputs use the application’s English calendar/time controls in Singapore time (UTC+08:00) and submit UTC timestamps. The local development override exposes PostgreSQL only at `127.0.0.1:15432`; the base Compose file used by CI does not publish a database port.

This is the local HTTP configuration. The [cloud overlay](docs/cloud-staging.md) provides HTTPS and deployment automation; runtime secrets currently use host files rather than a managed cloud secret service.

## 3. Acceptance walkthrough

1. Register administrator, organizer, member and attendee accounts; have the platform administrator provision two organizations and their initial organization administrators.
2. Invite members and accept through Notifications. Create seminar and workshop events, configure free ticket types and publish.
3. Browse, book and view QR/manual ticket codes. Verify that other attendees and other organizations cannot access private management data.
4. Assign event staff, check in a ticket twice and confirm attendance increases only once. Verify denial for unassigned staff.
5. Cancel another unstarted booking with no check-ins and confirm inventory is released once. Demonstrate pause/resume and a third organization joining through configuration.
6. Check organization-admin totals, combine event and member filters, and open event details across pages. Verify regular organizers cannot access the organization overview and ended events cannot be rescheduled to reopen.

## 4. Tests and CI

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

Database/API acceptance requires a separate disposable Compose environment; some scripts stop/restart services and inject failures. See [CI operations](docs/ci.md) for entry points, isolation and pipeline behavior. Historical evidence is retained in [docs/evidence](docs/evidence/).

## 5. Layout and documentation

- `services/` — backend services, migrations and tests.
- `apps/web/` — frontend and UI tests.
- `contracts/` — [OpenAPI contracts](contracts/README.md).
- `deployment/` — local Compose, gateway and database setup.
- `scripts/` — setup and reusable acceptance checks.
- [Documentation index](docs/README.md)
- [Proposal review and next steps](docs/implementation-plan.zh-CN.md)
- [Business rules](docs/functional-guide.md)
- [Architecture decisions](docs/adr/0001-service-boundaries.md)
- [Acceptance matrix](docs/acceptance-matrix.md)

The proposal and course illustrations are maintained separately from this repository.

## 6. Daily frontend and backend development

All commands below run from the repository root. Each teammate runs their own local database, `.env` and RSA keys; do not share a development database. Start Docker before using Compose. Ports are dedicated to this project so another application can keep using 5432, 8080 and 5173.

| Component | Host address | Purpose |
|---|---|---|
| Frontend with hot reload | `http://localhost:15173` | Vite development server; API requests proxy to the gateway |
| Gateway and built frontend | `http://localhost:18080` | API entry point and production frontend build |
| PostgreSQL for Navicat | `127.0.0.1:15432` | Enabled only by `deployment/compose.dev.yaml` |
| Backend services | Compose network only | Identity 8081, Catalog 8082, Admission 8083; no host bindings |

PostgreSQL still listens on 5432 **inside** Docker. Keep service JDBC URLs pointed at `postgres:5432`; 15432 is for host clients. The Compose project is `sems-platform`, with its own `platform-db` volume.

**Existing checkout:** pull the changes and run the two-file Compose startup command in section 2 again. This recreates the changed port mappings while retaining the existing database volume. Restart Vite and update old browser bookmarks/Navicat connections.

### Frontend

Start the full stack as in section 2, then use another terminal:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Open `http://localhost:15173`. Edit `apps/web/src/`; Vite reloads changes. It fails if 15173 is occupied rather than silently selecting another port. Login and API requests use the running services behind port 18080.

Before submitting frontend changes:

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

The build includes TypeScript checks. Coverage is in `apps/web/coverage/index.html`. To refresh the built frontend at port 18080 after building:

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d web
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml restart gateway
```

### Backend

Edit the relevant module under `services/identity`, `services/event-catalog` or `services/admission`. The standard team setup runs all three services in Docker; IDE edits do not automatically update running containers. Build the JARs first, then rebuild the service images:

```bash
mvn verify
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d identity event-catalog admission
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml restart gateway
bash scripts/smoke.sh
```

For a focused check, use `mvn -pl services/event-catalog -am verify`, substituting the module you changed. Service logs and stack status:

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml ps
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml logs --tail=100 -f identity event-catalog admission
```

Press Ctrl+C to stop following logs. API changes must update the corresponding files under `contracts/` and frontend callers. Internal service URLs and credentials are supplied by Compose; running only `mvn spring-boot:run` at the repository root is not this project's startup procedure.

## 7. Navicat and database changes

Start PostgreSQL through the development override (the full stack startup already does this):

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up -d postgres
```

In Navicat, create a **PostgreSQL** connection and select **Test Connection**, then open database `sems`. Use host `127.0.0.1`, port **15432**, and the following accounts. Passwords are values from your own local `.env`, not the variable names below.

| Suggested connection name | Username | Password variable | Schema |
|---|---|---|---|
| SEMS Platform - Identity | `identity_app` | `IDENTITY_DB_PASSWORD` | `identity` |
| SEMS Platform - Catalog | `catalog_app` | `CATALOG_DB_PASSWORD` | `catalog` |
| SEMS Platform - Admission | `admission_app` | `ADMISSION_DB_PASSWORD` | `admission` |
| SEMS Platform - Local admin | `postgres` | `POSTGRES_PASSWORD` | All schemas; local maintenance only |

Use the service account when inspecting its data so permission checks match the application. The accounts share one database but cannot read other services' schemas. The admin account can inspect all schemas and should not replace application credentials. Business tables appear when the corresponding service starts and runs Flyway, not merely when PostgreSQL starts. A query such as `SELECT current_database(), current_user;` verifies the selected connection.

Navicat is for data inspection and debugging queries. Version-controlled Flyway migrations are the source of truth for schema changes:

1. Add a new `V<number>__short_description.sql` under the owning service's `src/main/resources/db/migration/`. There are two underscores. Check that service's existing versions and coordinate the next unused number with teammates; versions are independent across services.
2. Do not edit migrations already merged or executed in a shared environment. Do not rely on table edits made only in Navicat, and do not edit `flyway_schema_history` to hide a mismatch.
3. Keep Hibernate `ddl-auto: validate`. Commit the migration with relevant Java mappings, API contracts, tests and database documentation. No cross-service foreign keys or direct cross-schema queries; use service APIs.
4. Rebuild/restart the owning service to apply migrations automatically. Before merging, verify both an empty database and upgrading existing data in a disposable environment; CI checks fresh database initialization.

The PostgreSQL initialization script creates service roles and schemas only on the first start of a new volume. Editing `.env` will not reset an existing database password. For connection failures, check Docker status, the two-file startup command, port 15432 and the credentials originally used for that volume. Use `down` to stop while retaining data; `down -v` deletes the database and is not a routine update step. Do not commit database dumps, Navicat connection exports, `.env` or `.secrets/`.

## 8. Team Git and pull request workflow

Agree on a task/Issue, scope and reviewer before starting. Coordinate shared API changes through `contracts/` and schema changes with the owning service's developer. The integration flow is: **sync main → work on your branch → test → push → PR → teammate review → passing CI → merge → sync again**. Do not push directly to `main`.

### Personal branches, including Victor

`victor` is Victor's persistent working branch. Keep it after merging; only Victor should push to it. Future Victor changes start here. Ensure the working tree is clean before switching or merging; commit unfinished work or stash it first.

```bash
# Existing local victor branch
git fetch origin
git switch victor
git merge origin/main
```

On a new clone, use `git switch --track origin/victor`. Other teammates create their own branch from the latest main, replacing the example name:

```bash
git fetch origin
git switch -c alice origin/main
git push -u origin alice
```

For separate concurrent tasks, use short-lived branches such as `alice-event-search` from `origin/main`. Do not share a personal branch between teammates.

### Commit, push and request review

Run the relevant frontend/backend checks in section 6. For database or service integration changes, also run the section 4 acceptance checks in a disposable stack. Review the diff and stage only the files belonging to your task:

```bash
git diff
git add README.md README.zh-CN.md  # Example: replace with your changed paths
git commit -m "docs: explain team development workflow"
git fetch origin
git merge origin/main
git push -u origin victor       # Other teammates use their own branch
```

Resolve merge conflicts in the affected files, stage them and run `git commit`; use `git merge --abort` to cancel the conflict merge. Re-run affected checks after resolution. Do not force-push shared history.

On GitHub, create a PR with **base `main`**, **compare your branch**. Follow the PR template: explain the task, resulting behavior, test commands/results and any database/configuration upgrade steps; include screenshots for UI changes. Invite **one other teammate** as reviewer. A comment or reviewer invitation is not approval. Use Draft PRs for unfinished work. Address feedback on the same branch and push; ask for another review after changes.

CI runs on PRs targeting `main`, pushes to `main`, or manual dispatch. Pushing `victor` alone without an open PR does not start automatic CI. Before merging, all six quality checks must pass:

- `Lint`
- `Backend · Unit Tests & Build`
- `Frontend · Tests & Build`
- `Backend · Integration Tests`
- `Security · SAST, Dependencies & Secrets`
- `Images · Scan, Smoke Test & Publish`

Require one other teammate's approval, resolve all discussions and remove merge conflicts. Telegram notification is informational, not a merge quality gate.

### Merge and continue on Victor's branch

For persistent personal branches such as `victor`, use **Create a merge commit** to preserve shared ancestry and keep the branch. After the PR is merged:

```bash
git fetch origin
git switch victor
git merge origin/main
git push
```

Start the next task only after the previous PR is merged, so unrelated changes do not accumulate in one PR. Short-lived task branches may use **Squash and merge** and be deleted afterward; start their next task from current `origin/main`. If repository settings permit only squash merges, use short-lived task branches for PRs instead of repeatedly squash-merging the persistent personal branch.

These are team conventions; README changes do not enable GitHub protection. The repository administrator should configure `main` protection/rulesets to require PRs, one approval from another teammate, renewed approval after updates, resolved discussions and the six quality checks above, and prohibit force pushes/deletion. If automatic branch deletion is enabled, disable it or preserve/restore persistent personal branches such as `victor`.
