# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS is a multi-organization platform for event publishing, free bookings, QR tickets and attendance. It supports organization membership, role-based management, event revisions and cancellation, saved registrations, notifications and attendance summaries.

[Application](https://swe5001.seventh720.com) · [Grafana](https://grafana.seventh720.com/d/sems-operations) (login required) · [Documentation](docs/README.md)

## Architecture

The frontend uses React/TypeScript. Three independently deployed Spring Boot services own their APIs, database credentials and Flyway migrations:

| Service | Responsibility | PostgreSQL schema |
| --- | --- | --- |
| Identity | Accounts, organizations, memberships, invitations and governance | `identity` |
| Event Catalog | Events, visibility, publication and revisions | `catalog` |
| Admission | Inventory, bookings, tickets, staff assignments, check-in and notifications | `admission` |

Services communicate through authenticated HTTP and use separate PostgreSQL schemas and service accounts. Database locks, unique request keys and durable operation receipts protect inventory and cross-service recovery. See the [architecture decisions](docs/adr/0001-service-boundaries.md) and [API contracts](contracts/README.md).

Production runs on two AWS EC2 nodes with K3s/containerd. Identity, Catalog, Admission, Web and Gateway each have two replicas in `sems-prod`; PostgreSQL uses a retained local volume. Prometheus, Grafana, Loki, Tempo and Telegram alerts run in `observability`. Deployment topology and operating limits are in the [K3s guide](docs/k3s.md).

Platform ADMIN provisions organizations and manages platform accounts. Organization roles `ORG_ADMIN`, `ORGANIZER` and `MEMBER` govern business access; check-in also requires an event assignment. Permissions and event lifecycles are defined in the [functional guide](docs/functional-guide.md).

## Local setup

Requires Java 21, Maven 3.9+, Node.js 22, npm, OpenSSL, Python 3 and Docker Compose v2 or later. Start Docker and check that `mvn -version` actually uses Java 21.

```bash
git clone git@github.com:seventh720/SWE5001-SEMS.git
cd SWE5001-SEMS
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml up --build -d
bash scripts/smoke.sh
```

Open [localhost:18080](http://localhost:18080). Setup creates private `.env` and `.secrets/` files. The bootstrap administrator defaults to `admin@example.com`; its generated password is in your local `.env`.

Frontend hot reload uses `npm --prefix apps/web run dev` at port **15173**. Database access, service rebuilds, credential handling and migrations are covered in the [development guide](docs/development.md).

Stop the local stack while retaining its database:

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

## Verification

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

[CI](docs/ci.md) checks lint, backend/frontend tests, API/database acceptance, source security and runtime images. Cloud validation used the deployed application with isolated test data:

| Test | Result |
| --- | --- |
| Mixed load, 100 VU for 10 minutes | 178959 steady-state requests, no unexpected client errors; slowest operation p95 about 525 ms |
| Concurrent inventory | 100 accounts competing for 10 places: 10 bookings, 90 sold-out responses; SQL totals match |
| One/two-replica comparisons | Catalog at 25/50/100 VU and Admission at 25/50 VU |
| Separate Catalog and Admission Pod failures | Business recovery target met; no acknowledged bookings lost |

Each cloud condition has one sample. Admission at 100 VU with one replica recorded 16 internal 504s during warmup and failed the server-side check; the paired two-replica trial was not run. Parameters, transient errors and data audits are in the [cloud validation record](docs/evidence/2026-11-06-cloud-validation/README.md). [Test coverage](docs/test-coverage.md) and the [acceptance matrix](docs/acceptance-matrix.md) describe the verification scope.

## Deployment and documentation

Eligible `main` CI runs publish immutable GHCR digests and deploy to K3s through GitHub OIDC and AWS SSM, with a database backup and post-deployment checks. [Delivery and rollback](docs/k3s-cd.md) covers releases; [observability](docs/observability.md) covers metrics, logs, traces and alerts.

- [Business rules](docs/functional-guide.md) · [API contracts](contracts/README.md)
- [Development](docs/development.md) · [Contributing](CONTRIBUTING.md) · [Local Kubernetes](docs/kubernetes.md)
- [Production deployment](docs/k3s.md) · [CI/CD](docs/k3s-cd.md) · [Observability](docs/observability.md)
- [Security](docs/security.md) · [Acceptance matrix](docs/acceptance-matrix.md) · [Performance experiments](docs/performance-and-availability.md)
- [Test evidence](docs/evidence/README.md) · [All documentation](docs/README.md)

`services/` contains the three backends; `apps/web/` the frontend; `contracts/` the APIs; `deployment/` runtime configuration; `scripts/` setup, delivery and acceptance tools.
