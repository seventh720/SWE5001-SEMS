# Editable schedule and capacity

**Ended events:** once the current `endsAt` is at or before the server time, new detail, presentation and combined revision edits are rejected. Changing dates cannot reopen the event; create a new event, optionally from its template. UI controls follow the same rule. Existing durable operations retain their receipt-based recovery behavior.

The event editor permits date and capacity changes after ticket configuration and publication. Published registration requirements remain fixed. The editor saves details and ticket configuration together through PUT /api/v1/organizer/events/{id}/revision, including unconfigured drafts; see [unified editing](publication-management.md). Legacy detail-only commands remain compatible.

## User-visible rules

- A new start, when changed, must be in the future and the end must follow it. An unchanged start may remain in the past for a still-ongoing published or paused event. An event with a checked-in ticket cannot be rescheduled; an ended event cannot be edited at all.
- Capacity must be at least the sum of allocated ticket-type quotas, which already bounds reserved places. An increase does not silently increase ticket quotas. The combined editor can reduce capacity and quotas together, as long as each quota covers its issued places.
- For legacy detail-only revisions, moving the start shifts ticket windows by the same duration. The combined editor submits explicit ticket windows instead: review them alongside the new event time.
- Confirmed booking start/end times follow the revised event schedule. Credentials, quantities, inventory counts and contact snapshots remain unchanged. Cancelled orders retain their historical dates. Venue/title snapshots on older orders remain historical; the public event link shows current details. No external change notifications are sent.
- During synchronization the event is UPDATING and cannot be discovered or newly booked. The organizer list refreshes pending updates. A definitive business rejection restores the previous status/settings and reports the reason.

## Persistence and recovery

Catalog stores a durable revision intent before contacting Admission and adds UPDATING. Admission stores a receipt in the same transaction as changing sales, sales windows and confirmed booking times. Matching operation retries never apply a second shift. Catalog finishes its own event update after Admission acknowledges; its scheduled worker resumes pending intents after network failures or restart. Owner/version/registration-rule checks run before staging.

Admission serializes revisions with configuration/activation through the event advisory lock and with bookings/cancellations through the sales row lock. Configuration, booking and pre-registration reject stale schedule/capacity snapshots. The full inventory invariant is preserved; no cross-schema access is introduced. The first ticket configuration can race with a revision, so a missing draft sales row is initialized using the new metadata and stale configuration is rejected.

Review the persisted UPDATING state and service-owned Flyway migrations before rollback. Older binaries may not reconcile pending intents; normal application rollback does not reverse database migrations. See [delivery and rollback](k3s-cd.md).

## Verification

`scripts/schedule-acceptance.py` includes all existing workspace/booking regressions, then verifies owner isolation, version conflict, successful rescheduling, unchanged available places, confirmed-ticket dates, sales-window shifts, rejection below allocated capacity, locked published requirements, configured draft updates and recovery after Admission outage plus Catalog restart. A repeated pending request cannot shift dates twice. Run only in an isolated test stack.
