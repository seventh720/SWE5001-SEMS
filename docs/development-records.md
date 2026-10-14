# Development records

The current increment implements identity, role management, event drafts and a React client. Three services own separate PostgreSQL schemas and credentials. Admission now owns free ticket configuration, quota checks and sales activation. Catalog publication is durable and retry-safe. Free booking, per-place QR/manual-code tickets and attendee cancellation are implemented. Staff check-in and event-wide cancellation remain pending.

Changes must record their associated commits, affected files, design rationale, contributors and validation results. Acceptance evidence must correspond to the tested version. Retain applicable attribution and license notices when incorporating third-party code.

## Booking increment (2026-10-13)

Implemented on Victor’s branch with Codex assistance, following revised proposal §4.3 and §5.1. Admission owns booking/ticket transactions; Catalog adds historical snapshot fields; Web adds retry-safe booking, My tickets and cancellation. See [design and validation](booking-increment.md). Local validation passed the existing 13 backend tests, 25 frontend tests, builds and real PostgreSQL acceptance through two Admission replicas. The 100-request/10-place test produced 10 confirmations and 90 expected conflicts, with matching persisted inventory/order/ticket counts. Team review and actual person-day accounting remain the contributors’ responsibility; no effort estimate is reported as measured effort.

## Registration and presentation increment

Victor branch, Codex-assisted implementation: configurable booking contact fields, private organizer registrations, category filtering, independent card themes and custom English date/time/select controls. New migrations are Catalog V3 and Admission V4; old event/order rows receive backward-compatible defaults. UI time entry/display is now explicitly Singapore time. Language and theme switching remain an effort assessment. Validation includes 31 frontend tests, 15 backend tests and the full two-Admission PostgreSQL acceptance suite.

### 2026-10-13 — Profiles and pre-registration

Added in-flow Explore navigation, readable event facts, manual profile application, persisted pre-registration and live opening/closing countdowns. Identity V2 and Admission V5 preserve service-owned schemas. 34 frontend tests, 16 backend tests, production builds and full two-replica PostgreSQL/API acceptance passed. Headless Chrome verified desktop/mobile layout without horizontal overflow and profile save/reload, pre-registration save/list/load. CI now includes the complete pre-registration lifecycle.

### 2026-10-14 — Role workspaces and offering reuse

Replaced signed-in marketing with Dashboard plans/pre-registrations and role-specific management; added community upcoming events, right-anchored navigation, category artwork and a ticket favicon. Published presentation edits preserve time/capacity/registration requirements and historical order snapshots. Own-event templates reset dates and require fresh sales configuration. 39 frontend tests and 17 backend tests passed with the full PostgreSQL/API regression. Headless Chrome verified organizer Dashboard, published edit, template date reset, setup spacing and mobile overflow. Platform positioning is documented against revised proposal sections 3 and 5.

### 2026-10-14 — Schedule editing and form alignment (local review)

Opened event dates/capacity with durable cross-service synchronization and locked published registration rules. Corrected checkbox width/wrapping/focus and aligned discovery search controls; desktop cards use exactly two columns. 39 frontend tests, 17 backend tests and full PostgreSQL/API acceptance passed, including Admission outage/Catalog restart recovery and confirmed-booking schedule propagation. Browser measurements confirmed alignment and mobile layout. Changes are intentionally not committed or pushed pending local review.

## 2026-10-14 — Named contacts and unified event editor (local review)

Added multiple saved contacts without reusable Student IDs, selected-contact application, username editing with shared signup validation and uniqueness enforcement, and inline ticket configuration with a separate publication preview. Identity V3 migrates the default profile and removes its Student ID column; gateway routes the new profile endpoints. Verified 42 frontend tests, 19 backend tests, full two-replica PostgreSQL/API acceptance, and desktop/mobile Chrome workflows. Changes remain uncommitted and unpushed for local review.

## 2026-10-14 — Unified save and publication management (local review)

Moved the single save action below ticket settings and isolated the editor to the selected event. Added recoverable combined detail/ticket revisions with stable ticket IDs, reserved-quota validation, reference-safe removal and deferred name uniqueness. Published edits update automatically; explicit pause/resume preserves existing tickets and rejects stale first-publication retries. Catalog V5/Admission V7 add PAUSED states. Validation passed: 40 frontend tests, 19 backend tests, full real PostgreSQL/API acceptance and desktop/mobile browser editing/publication flows. No commit or push.

## 2026-10-14 — Detail layout, save feedback and dashboard registration (local review)

Grouped event context into a compact left column with a subdued category strip and aligned admission on the right; mobile stacks the sections. Added viewport-level dismissible save feedback for events, contacts, usernames, pre-registrations and role updates; event saves no longer invoke the open-editor scroll. Pending publication/revision notices resolve on completion. Dashboard opening transitions refresh the reservation and expose Register now, linking and focusing its ticket while retaining saved quantity/contact details. Verified 43 frontend tests, production build and desktop/mobile browser flows with intercepted fixtures (no production data changes). No backend changes, commit or push.

### Consistent return navigation and booking history

- Shared return link across public, attendee and organizer/admin pages: guests see “Back to home”; signed-in users see “Back to dashboard”. Detail pages retain a separate return to their parent list.
- My tickets defaults to Confirmed with a separate Cancelled view and explicit invalid-ticket guidance. Switching status resets pagination; API filtering applies to both records and totals while retaining account ownership and unfiltered API compatibility. Saved pre-registrations remain separate from confirmed bookings.
- Validation: 45 frontend tests, frontend production build, 11 admission unit tests and package build. Browser fixtures verified navigation on six pages, status switching, pagination reset and mobile width. No production booking records were changed.

### Pre-push review — 14 October 2026

- Fixed premature save-success feedback during asynchronous event revisions: the editor now polls the selected event instead of accepting stale list data as completion. Added a regression test.
- Documented the optional booking `status` query parameter and added real PostgreSQL/API acceptance checks for filtered totals, pagination and account isolation.
- Verified 46 frontend tests with coverage, the production frontend build and 22 backend tests with a full Maven clean verify. Locally, Mockito was explicitly loaded as a test agent to avoid sandbox process-attachment restrictions.
- Passed the complete editor acceptance chain on a separate Compose project with two Admission instances: database isolation, authentication/ownership, concurrent booking limits, cancellation, profiles, pre-registration, event revision recovery, saved contacts, username uniqueness, combined ticket editing and publication pause/resume.
