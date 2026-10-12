# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS is a shared event and ticketing platform for independent organizers and attendees, using React + TypeScript, three independent Spring Boot services and PostgreSQL.

Implemented: registration/login, RSA JWT, administrator role assignment, organizer draft creation/list/detail/edit, owner isolation and optimistic version conflicts. Publication, public discovery, booking, ticket issuance and check-in are pending.

## 1. Architecture and roles

| Service | Data ownership | Status |
|---|---|---|
| Identity | Accounts, passwords, roles | Implemented |
| Event Catalog | Organizer-owned event drafts | Implemented |
| Admission | Inventory, bookings, tickets, check-in | Database and authentication foundation only |

Each service owns a schema, database account and Flyway migrations, with no cross-service foreign keys or queries. Only Identity holds the RSA private key; the other services validate signatures, issuer, audience and token lifetime using the public key.

Roles are `ATTENDEE`, `ORGANIZER`, `STAFF` and `ADMIN`. Registration grants ATTENDEE; administrators assign roles. ADMIN does not bypass event ownership. Sign in again after role changes; existing tokens remain valid for up to 30 minutes. Immediate revocation is not implemented.

## 2. Local setup

Requires Java 21, Maven 3.9+, Node.js 22, npm, OpenSSL, Python 3 and Docker Compose v2.

```bash
git clone git@github.com:seventh720/SWE5001-SMES.git
cd SWE5001-SMES
bash scripts/setup-local.sh
mvn verify
npm --prefix apps/web ci
npm --prefix apps/web test
npm --prefix apps/web run build
docker compose --env-file .env -f deployment/compose.yaml up --build -d
bash scripts/smoke.sh
```

Open [the local platform](http://localhost:8080). Setup generates `.env` and `.secrets/` without overwriting existing configuration. The initial admin email is `admin@example.com`; read its random `SEMS_BOOTSTRAP_ADMIN_PASSWORD` from your local `.env`. Do not commit or share that file. Clear bootstrap settings after initialization; the persisted admin can still log in.

Database credentials are applied only when a new volume is initialized. Editing `.env` does not rotate existing database passwords. Stop while preserving data:

```bash
docker compose --env-file .env -f deployment/compose.yaml down
```

For frontend development, run `npm --prefix apps/web run dev`; port 5173 proxies APIs to the gateway on 8080. The production frontend is served at the gateway root. Date inputs use the browser timezone and submit UTC timestamps. PostgreSQL is not exposed to the host.

This is local HTTP configuration. Cloud HTTPS, secret management and deployment remain pending.

## 3. Acceptance walkthrough

1. Register two accounts.
2. Sign in as admin, open “Manage users and roles”, grant ORGANIZER to both accounts and save.
3. Sign in again as each organizer and open “My events”.
4. Create a draft, refresh and edit it. The second organizer must not see the first organizer’s draft.
5. Edit one draft in two windows: a stale submission returns a conflict and can reload the latest version.

Publication is unavailable until Admission sales coordination is implemented.

## 4. Tests and CI


```bash
mvn verify
npm --prefix apps/web test
npm --prefix apps/web run build
bash scripts/check-db-isolation.sh
set -a
source .env
set +a
python3 scripts/acceptance.py
```

The last two checks need a running Compose stack. Acceptance creates uniquely named test accounts and drafts; use an isolated test volume. CI runs these checks in an ephemeral environment, covering authentication, authorization, schema isolation, validation, persistence and concurrent version conflicts. Telegram reports results; logs/JARs are retained for seven days. See [CI operations](docs/ci.md).

## 5. Layout and documentation

- `services/`: independent backend services and migrations.
- `apps/web/`: React application and UI tests.
- `contracts/`: current OpenAPI specifications.
- `deployment/`: gateway, database initialization and Compose.
- `scripts/`: local setup, readiness and acceptance checks.
- [Implementation plan](docs/implementation-plan.zh-CN.md)
- [API contracts](contracts/README.md)
- [Architecture](docs/adr/0001-service-boundaries.md)
- [Acceptance targets](docs/acceptance-matrix.md)

Use short-lived branches and pull requests with corresponding tests and contracts. The proposal and its figures are maintained separately.
