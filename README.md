# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS brings organization membership, event information, registration requirements, bookings, tickets and attendance into one shared platform. Organizers manage the event lifecycle, attendees keep their bookings and QR tickets, and assigned staff check attendance using the same current information.

- **Application:** [swe5001.seventh720.com](https://swe5001.seventh720.com)
- **Operations:** [Grafana](https://grafana.seventh720.com/d/sems-operations), with account login required.
- **Documentation:** [index](docs/README.md), [business rules](docs/functional-guide.md), [platform status](docs/progress.md).

## 1. Architecture and permissions

The frontend uses React/TypeScript. Three independently deployed Spring Boot services own their APIs, database credentials and Flyway migrations:

| Service | Responsibility | PostgreSQL schema |
| --- | --- | --- |
| Identity | Accounts, organizations, memberships, invitations and governance | `identity` |
| Event Catalog | Events, visibility, publication and revisions | `catalog` |
| Admission | Inventory, bookings, tickets, staff assignments, check-in and notifications | `admission` |

Services use authenticated HTTP across boundaries. A shared PostgreSQL instance provides separate schemas and service accounts; application code does not query another service's schema. Database locks, unique request keys and durable operation receipts protect inventory and cross-service recovery. See the [architecture decisions](docs/adr/0001-service-boundaries.md).

Production runs on two AWS EC2 nodes with K3s/containerd. Identity, Catalog, Admission, Web and Gateway each have two replicas in `sems-prod`; PostgreSQL uses a retained local volume. Prometheus, Grafana, Loki, Tempo and Telegram alerts run in `observability`. Deployment topology and operating limits are in the [K3s guide](docs/k3s.md).

Platform ADMIN provisions organizations and manages platform accounts. Organization roles `ORG_ADMIN`, `ORGANIZER` and `MEMBER` govern business access; check-in additionally requires an event assignment. Features include public/member-only events, versioned editing, pause/resume/cancellation, free bookings, individual QR tickets, saved registrations, notifications and organization summaries. [Business rules](docs/functional-guide.md) define permissions and lifecycle details.

## 2. Local setup

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

Open [localhost:18080](http://localhost:18080). Setup creates private `.env` and `.secrets/` files. The bootstrap administrator defaults to `admin@example.com`; read its generated password from your own `.env`. Do not commit credentials. Existing database passwords and RSA keys are retained when setup is repeated; changing an environment value does not change an initialized database password.

For frontend hot reload, run `npm --prefix apps/web run dev` and open port **15173**; API requests use the gateway on **18080**. The development override exposes PostgreSQL only on `127.0.0.1:15432`. Backend ports remain internal. See the [development guide](docs/development.md) for rebuilds, Navicat and migrations.

Stop the local stack while retaining its database:

```bash
docker compose --env-file .env -f deployment/compose.yaml -f deployment/compose.dev.yaml down
```

## 3. Tests and delivery

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

[CI](docs/ci.md) checks lint, backend/frontend tests, real API/database acceptance, source security and exact runtime images. Fault-injection and fixture suites require a disposable environment. [Test coverage](docs/test-coverage.md) explains what each check establishes; [test evidence](docs/evidence/README.md) retains measured results and failures.

Successful eligible `main` runs publish immutable GHCR digests and deploy to K3s through GitHub OIDC and AWS SSM. PR checks do not deploy production. [Delivery and rollback](docs/k3s-cd.md) describes the release boundary. GitHub Releases can record tagged versions and link to the application; the running website is hosted on AWS.

## 4. Documentation and layout

- [Business rules](docs/functional-guide.md) · [API contracts](contracts/README.md)
- [Development](docs/development.md) · [Contributing](CONTRIBUTING.md) · [Local Kubernetes](docs/kubernetes.md)
- [Production deployment](docs/k3s.md) · [CI/CD](docs/k3s-cd.md) · [Observability](docs/observability.md)
- [Security](docs/security.md) · [Acceptance matrix](docs/acceptance-matrix.md) · [Performance experiments](docs/performance-and-availability.md)
- [Platform status](docs/progress.md) · [Roadmap](docs/roadmap.md) · [All documentation](docs/README.md)

`services/` contains the three backends; `apps/web/` the frontend; `contracts/` the APIs; `deployment/` runtime configuration; `scripts/` setup, delivery and acceptance tools.
