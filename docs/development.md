# Development guide

Local setup prerequisites and first startup are in the [README](../README.md#2-local-setup). This guide covers daily development, database access and migrations. Review and merge conventions are in [CONTRIBUTING](../CONTRIBUTING.md).

## Local environment

All commands below run from the repository root. Each developer runs their own local database, `.env` and RSA keys; do not share a development database. Start Docker before using Compose. Ports are dedicated to this project so another application can keep using 5432, 8080 and 5173.

| Component | Host address | Purpose |
|---|---|---|
| Frontend with hot reload | `http://localhost:15173` | Vite development server; API requests proxy to the gateway |
| Gateway and built frontend | `http://localhost:18080` | API entry point and production frontend build |
| PostgreSQL for Navicat | `127.0.0.1:15432` | Enabled only by `deployment/compose.dev.yaml` |
| Backend services | Compose network only | Identity 8081, Catalog 8082, Admission 8083; no host bindings |

PostgreSQL still listens on 5432 **inside** Docker. Keep service JDBC URLs pointed at `postgres:5432`; 15432 is for host clients. The Compose project is `sems-platform`, with its own `platform-db` volume.

### Frontend

Start the full stack using the [local setup guide](../README.md#2-local-setup), then use another terminal:

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

Edit the relevant module under `services/identity`, `services/event-catalog` or `services/admission`. The default local setup runs all three services in Docker; IDE edits do not automatically update running containers. Build the JARs first, then rebuild the service images:

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

## Database inspection and migrations

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

1. Add a new `V<number>__short_description.sql` under the owning service's `src/main/resources/db/migration/`. There are two underscores. Check that service's existing versions and coordinate the next unused number with other contributors; versions are independent across services.
2. Do not edit migrations already merged or executed in a shared environment. Do not rely on table edits made only in Navicat, and do not edit `flyway_schema_history` to hide a mismatch.
3. Keep Hibernate `ddl-auto: validate`. Commit the migration with relevant Java mappings, API contracts, tests and database documentation. No cross-service foreign keys or direct cross-schema queries; use service APIs.
4. Rebuild/restart the owning service to apply migrations automatically. Before merging, verify both an empty database and upgrading existing data in a disposable environment; CI checks fresh database initialization.

The PostgreSQL initialization script creates service roles and schemas only on the first start of a new volume. Editing `.env` will not reset an existing database password. For connection failures, check Docker status, the two-file startup command, port 15432 and the credentials originally used for that volume. Use `down` to stop while retaining data; `down -v` deletes the database and is not a routine update step. Do not commit database dumps, Navicat connection exports, `.env` or `.secrets/`.
