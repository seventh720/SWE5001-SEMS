# Whole-event cancellation — 2026-10-17

Verified locally against an isolated PostgreSQL stack at port 18084, with two Admission instances. No cloud SLA or deployed CI run is claimed.

## Review findings and changes

- Pause hid discovery and stopped sales but retained tickets; it could not represent permanent cancellation. Added separate durable CANCELLING → CANCELLED protocol and explicit UI confirmation/reason.
- Check-in lacked a terminal sales-state guard. Cancellation and check-in now serialize on the sales row and cancelled events reject all subsequent scans, including replay of a historical scan.
- Mixed checked-in bookings need consistent history: all confirmed bookings are cancelled, unused tickets invalidated, CHECKED_IN records/attribution retained. Available/confirmed counts become zero; the dashboard displays historical attendance without misleading progress.
- Retry and delayed command handling must not reopen events. Terminal state guards prevent publishing/revising/configuring cancelled sales; matching cancellation receipts avoid repeated inventory and notification effects.
- Cancellation UI state now loads independently of Admission inventory availability. Booking detail shows the organizer's cancellation reason and no usable QR codes.

## Validation

- `mvn verify -q`: 32 tests passed (Identity 6, Catalog 11, Admission 15), no skipped tests. Mockito attach required running outside the filesystem/process sandbox.
- Frontend: 82 tests passed across 20 files; TypeScript and production build passed.
- `scripts/event-cancellation-acceptance.py`: 100 booking requests competed with staff check-in, attendee cancellation and six identical event cancellations across two Admission replicas. No CONFIRMED bookings, VALID tickets or reserved places remained; prior check-in history remained. Confirmed/available statistics were zero. Saved registrations were closed and notifications were deduplicated.
- Permission, stale version, changed cancellation payload, pause-versus-cancel and post-cancellation publish/edit/staff/booking/check-in rejection checks passed.
- A test-only trigger failed the final receipt insert, proving that sales/order/ticket/inventory/notification changes all roll back. Removing the fault allowed automatic completion.
- Both Admission replicas were stopped after preparing a fresh event. Catalog accepted a durable 202 request and was restarted; cancellation completed after services returned. A previously completed cancellation returned successfully while Admission was offline.
- A test-only Catalog acknowledgment rewind simulated a crash after Admission commit. Recovery replayed the receipt without duplicate notices or inventory effects.
- Existing `organization-acceptance.py` regression chain passed: publication, booking contention/idempotency, contacts, pre-registration, schedule edits, ticket edits, pause/resume recovery, organization isolation and staff check-in.
- Initial test-container build used the previously packaged JAR while Maven was still pending; rebuilt after successful packaging. A subsequent gateway startup connection reset exposed missing readiness wait in the test harness; readiness now precedes recovery assertions and the final run passed.

## Local rollout and limits

A private pre-upgrade PostgreSQL archive was created and its archive listing verified at `.secrets/backups/2026-10-17-event-cancellation/before-upgrade.dump`. Admission was updated before Catalog and Web. The shared working instance was not used for fault injection. Database records were retained; no live event was cancelled as part of verification.

Migration versions: Identity V7, Catalog V9, Admission V10. Older binaries do not implement the cancellation protocol and must not be used to reopen terminal events. CANCELLING means Admission effects are pending; requests that acquired the sales lock first can finish and are then included in cancellation. New Catalog eligibility is already closed. Persistent connectivity/configuration failures require repair before the durable worker can complete. All tickets in this platform are free; no payment/refund workflow was added.

See [publication protocol](../../publication-management.md) for recovery and deployment boundaries. The new acceptance script is included in CI configuration, but a remote CI run was not triggered.
