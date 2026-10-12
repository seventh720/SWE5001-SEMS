# Smart Event Management and Ticketing Platform

[English](README.md) | [简体中文](README.zh-CN.md)

SEMS is a shared event and ticketing platform for independent organizers and attendees. It is designed around three independently deployable Spring Boot services and a React web application. Organizers manage their own offerings, while attendees discover events through a common catalog.

## 1. Project status

The repository currently contains three service entry points, health endpoints, Dockerfiles, a local gateway, Docker Compose configuration. Business APIs, authentication, persistence, the web application and cloud deployment are not implemented yet. There are no automated business tests at this stage.

The planned core workflow is event publication → free-ticket booking → individual ticket issuance → staff check-in → attendance summaries. Paid tickets, payment providers and external email/SMS delivery are outside the core scope.

## 2. Architecture and repository layout

| Path | Responsibility |
|---|---|
| `services/identity/` | Accounts, authentication and roles |
| `services/event-catalog/` | Event ownership, details, publication and discovery |
| `services/admission/` | Ticket types, inventory, bookings, tickets, staff assignment and check-in |
| `apps/web/` | Planned React and TypeScript application; currently documentation only |
| `contracts/` | API contract planning; business OpenAPI specifications are pending |
| `deployment/` | Local Compose configuration and Nginx gateway |
| `docs/` | Implementation plan, architecture decisions and acceptance criteria |

Each service produces its own executable JAR and container image. The planned persistence model gives each service its own PostgreSQL schema, credentials and migrations. Services must not share JPA entities, repositories or cross-schema queries. Inventory, booking and ticket changes stay within Admission transactions.

## 3. Development requirements

| Tool | Version |
|---|---|
| Java | 21 |
| Maven | 3.9+ |
| Docker Engine or Docker Desktop | With Docker Compose v2 |
| Spring Boot | 3.5.16, pinned in the root POM |

Node.js and PostgreSQL are not needed to run the current service skeleton. Their setup will be documented when the web application and persistence are added.

## 4. Getting started

Clone the repository and enter its directory:

```bash
git clone git@github.com:seventh720/SWE5001-SMES.git
cd SWE5001-SMES
```

For an existing local checkout, run the commands below from its root.

### Option A: Run with Docker

Build the JARs before building the images:

```bash
mvn verify
docker compose -f deployment/compose.yaml up --build
```

The local gateway listens at `http://localhost:8080`. Verify the services:

```bash
curl --fail http://localhost:8080/health/identity
curl --fail http://localhost:8080/health/event-catalog
curl --fail http://localhost:8080/health/admission
```

Each readiness response should report `UP`. The root URL returns 404 because there is no web interface or business routing yet. Local Compose uses HTTP and is not a production deployment configuration.

Stop the containers:

```bash
docker compose -f deployment/compose.yaml down
```

### Option B: Run services locally

Run each command in a separate terminal from the repository root:

```bash
mvn -pl services/identity spring-boot:run
```

```bash
mvn -pl services/event-catalog spring-boot:run
```

```bash
mvn -pl services/admission spring-boot:run
```

| Service | Default port | Readiness path |
|---|---|---|
| Identity | 8081 | `/actuator/health/readiness` |
| Event Catalog | 8082 | `/actuator/health/readiness` |
| Admission | 8083 | `/actuator/health/readiness` |

`SERVER_PORT` overrides a service's port. This option runs the services directly without the gateway. Stop each process with Ctrl+C.

## 5. Build and validation

```bash
mvn verify
docker compose -f deployment/compose.yaml config --quiet
```

Platform CI runs on pushes to `main`, pull requests targeting `main`, and manual dispatch. It builds the three services with Java 21, validates Compose, builds and starts containers, and checks service readiness through the gateway. Logs and successful JAR builds are retained for 7 days. Run the same smoke checks locally with `bash scripts/smoke.sh` after starting Compose.

Telegram reports the build result and run link using repository Actions secrets `TELEGRAM_TOKEN` and `TELEGRAM_TO`. Missing secrets skip delivery; notification failures do not change the build result. Fork and Dependabot pull requests skip notifications.

Cloud deployment, image publishing, security scanning and business tests remain pending. This workflow verifies the service skeleton, not business acceptance. See [CI operations](docs/ci.md).

## 6. Development roadmap

1. Define versioned API contracts, service-owned persistence, authentication and gateway routing.
2. Implement account onboarding, organizer ownership, event drafts and catalog discovery.
3. Complete free booking, inventory protection, ticket issuance, cancellation and staff check-in.
4. Integrate the web application and demonstrate two independent organizers using shared capabilities.
5. Add cloud deployment, security checks, independent scaling, concurrency and recovery experiments.

## 7. Collaboration and documentation

Use short-lived branches and pull requests. Include relevant tests, API contracts and database migrations with business changes. Keep credentials and local environment files out of version control.

- [Implementation plan (Chinese)](docs/implementation-plan.zh-CN.md)
- [Service boundaries and consistency (Chinese)](docs/adr/0001-service-boundaries.md)
- [Acceptance criteria (Chinese)](docs/acceptance-matrix.md)

The proposal and its figures are maintained separately from this code repository.
