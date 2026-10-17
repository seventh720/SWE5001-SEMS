# API contracts

OpenAPI 3.0.3; these documents describe the current organization-scoped APIs.

- `identity.openapi.json`: accounts, platform administration, organizations, membership/invitations, organization change/closure requests, soft deletion and membership notifications.
- `event-catalog.openapi.json`: event drafts, discovery, durable publication/revision, pause/resume, terminal whole-event cancellation and internal eligibility snapshots.
- `admission.openapi.json`: ticket configuration, availability, retry-safe bookings, ticket credentials, attendee cancellation, pre-registration, assigned-staff check-in, summaries, notifications and internal activation/revision/cancellation.

Event metadata routes to Catalog. Ticket types, bookings, staff assignments and attendance route to Admission. Organization and account administration routes to Identity. The gateway blocks `/internal`; authenticated service-to-service HTTP uses `X-Service-Token` with separate credentials per direction.

Organization membership controls business access; platform ADMIN and legacy global ORGANIZER/STAFF claims do not replace membership or event assignment. Published ticket settings are edited through the recoverable revision protocol. Pause preserves tickets; whole-event cancellation invalidates unused tickets and retains check-in history. See [business rules](../docs/functional-guide.md) and [publication/cancellation](../docs/publication-management.md).

The files parse and their local schema references resolve. Automated request/response conformance testing against OpenAPI is not yet wired into CI; API acceptance tests are separate and do not establish full contract conformance.
