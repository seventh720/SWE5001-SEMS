# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS is a shared event and ticketing platform built with React/TypeScript, three Spring Boot services and PostgreSQL.

Implemented: organization-scoped permissions, event publication/editing/pause/cancellation, free bookings, individual QR tickets, assigned-staff check-in, saved registrations, in-app notifications and an organization-admin overview. Event and member management support server-side search, combined filters and pagination. Ended events cannot be edited or reopened.

See [release status](docs/progress.md) for the latest recorded release and known limitations, [business rules](docs/functional-guide.md) for permissions and metric definitions, and [test coverage](docs/test-coverage.md) for verification limits. JWTs last one hour. Check-in opens 15 minutes before the event starts and closes 15 minutes after it starts (exclusive), or at the event end if earlier.

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

This is the local HTTP configuration. [swe5001.seventh720.com](https://swe5001.seventh720.com) now runs on the [EC2 K3s environment](docs/k3s.md), with the original accounts and data migrated. [K3s delivery](docs/k3s-cd.md) describes main-only releases; the [cutover record](docs/evidence/2026-10-25-k3s-cutover/README.md) covers data/TLS/DNS checks. The [Lightsail guide](docs/cloud-staging.md) is retained for historical reference. Runtime credentials use restricted host files and Kubernetes Secrets.

## 3. Acceptance walkthrough

1. Register administrator, organizer, member and attendee accounts; have the platform administrator provision two organizations and their initial organization administrators.
2. Invite members and accept through Notifications. Create seminar and workshop events, configure free ticket types and publish.
3. Browse, book and view QR/manual ticket codes. Verify that other attendees and other organizations cannot access private management data.
4. Assign event staff, check in a ticket twice and confirm attendance increases only once. Verify denial for unassigned staff.
5. Cancel another unstarted booking with no check-ins and confirm inventory is released once. Verify pause/resume and another organization joining through configuration.
6. Check organization-admin totals, combine event and member filters, and open event details across pages. Verify regular organizers cannot access the organization overview and ended events cannot be rescheduled to reopen.

## 4. Tests and CI

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

Database/API acceptance requires an isolated test environment; some scripts stop/restart services and inject failures. See [CI operations](docs/ci.md) for Compose checks and [K3s operations](docs/k3s.md) for Kubernetes adapters. Historical evidence is retained in [docs/evidence](docs/evidence/).

## 5. Layout and documentation

- `services/` — backend services, migrations and tests.
- `apps/web/` — frontend and UI tests.
- `contracts/` — [OpenAPI contracts](contracts/README.md).
- `deployment/` — Compose, Kubernetes overlays, gateway and database setup.
- `scripts/` — setup and reusable acceptance checks.
- [Documentation index](docs/README.md)
- [Development and database guide](docs/development.md)
- [Kubernetes setup and cloud templates](docs/kubernetes.md)
- [EC2 K3s environment](docs/k3s.md)
- [Monitoring, alerts and distributed tracing](docs/observability.md)
- [Contributing](CONTRIBUTING.md)
- [Technical roadmap](docs/roadmap.md)
- [Business rules](docs/functional-guide.md)
- [Architecture decisions](docs/adr/0001-service-boundaries.md)
- [Acceptance matrix](docs/acceptance-matrix.md)
