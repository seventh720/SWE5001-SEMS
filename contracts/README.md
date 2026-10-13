# API contracts

- `identity.openapi.json`: registration, login, current account and ADMIN role management.
- `event-catalog.openapi.json`: owned drafts, durable publication, public search/detail and internal event snapshots.
- `admission.openapi.json`: free ticket configuration, availability, retry-safe bookings, individual ticket credentials, attendee cancellation and internal sales activation.

OpenAPI 3.0.3. `/api/v1/events/{id}/ticket-types` and the organizer equivalent route to Admission, while event metadata routes to Catalog. `/internal` is blocked by the gateway; service-only paths use their own network addresses and `X-Service-Token`. The two call directions have separate credentials.

Starting ticket setup fixes event capacity and time. Other draft details can still be edited. Publication freezes ticket configuration. Bookings and attendee cancellation are implemented; event-wide cancellation and staff check-in remain pending. `/api/v1/bookings` and its subpaths route to Admission.
