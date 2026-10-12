# API contracts

- `identity.openapi.json`: registration, login, current account and ADMIN role management.
- `event-catalog.openapi.json`: organizer draft list/create/read/update with owner isolation and optimistic versions.

Both are OpenAPI 3.0.3 contracts for the current release. The gateway routes `/api/v1/auth/*` and `/api/v1/admin/*` to Identity, and draft event operations to Catalog. Future ticket types/check-ins under an event path must be routed to Admission rather than matching all event paths indiscriminately.

Admission has no public business API in this release; its contract will be added with ticketing. `/internal` is not exposed by the gateway. Never accept owner IDs from clients as authorization evidence.
