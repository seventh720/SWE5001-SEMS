# Development records

The current increment implements identity, role management, event drafts and a React client. Three services own separate PostgreSQL schemas and credentials. Admission now owns free ticket configuration, quota checks and sales activation. Catalog publication is durable and retry-safe. Free booking, per-place QR/manual-code tickets and attendee cancellation are implemented. Staff check-in and event-wide cancellation remain pending.

Changes must record their associated commits, affected files, design rationale, contributors and validation results. Acceptance evidence must correspond to the tested version. Retain applicable attribution and license notices when incorporating third-party code.

## Booking increment (2026-10-13)

Implemented on Victor’s branch with Codex assistance, following revised proposal §4.3 and §5.1. Admission owns booking/ticket transactions; Catalog adds historical snapshot fields; Web adds retry-safe booking, My tickets and cancellation. See [design and validation](booking-increment.md). Local validation passed the existing 13 backend tests, 25 frontend tests, builds and real PostgreSQL acceptance through two Admission replicas. The 100-request/10-place test produced 10 confirmations and 90 expected conflicts, with matching persisted inventory/order/ticket counts. Team review and actual person-day accounting remain the contributors’ responsibility; no effort estimate is reported as measured effort.

## Registration and presentation increment

Victor branch, Codex-assisted implementation: configurable booking contact fields, private organizer registrations, category filtering, independent card themes and custom English date/time/select controls. New migrations are Catalog V3 and Admission V4; old event/order rows receive backward-compatible defaults. UI time entry/display is now explicitly Singapore time. Language and theme switching remain an effort assessment. Validation includes 31 frontend tests, 15 backend tests and the full two-Admission PostgreSQL acceptance suite.

### 2026-10-13 — Profiles and pre-registration

Added in-flow Explore navigation, readable event facts, manual profile application, persisted pre-registration and live opening/closing countdowns. Identity V2 and Admission V5 preserve service-owned schemas. 34 frontend tests, 16 backend tests, production builds and full two-replica PostgreSQL/API acceptance passed. Headless Chrome verified desktop/mobile layout without horizontal overflow and profile save/reload, pre-registration save/list/load. CI now includes the complete pre-registration lifecycle.
