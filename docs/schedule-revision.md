# Editable schedule and capacity

The event editor now permits date and capacity changes after ticket configuration and publication. Published registration requirements remain fixed. The editor now saves details and ticket configuration together through PUT /api/v1/organizer/events/{id}/revision, including unconfigured drafts; see [unified editing](publication-management.md). Legacy detail-only commands remain compatible.

## User-visible rules

- Choose a future start and an end after it. An event with a checked-in ticket cannot be rescheduled.
- Capacity must be at least the sum of allocated ticket-type quotas, which already bounds reserved places. An increase does not silently increase ticket quotas. The combined editor can reduce capacity and quotas together, as long as each quota covers its issued places.
- For legacy detail-only revisions, moving the start shifts ticket windows by the same duration. The combined editor submits explicit ticket windows instead: review them alongside the new event time.
- Confirmed booking start/end times follow the revised event schedule. Credentials, quantities, inventory counts and contact snapshots remain unchanged. Cancelled orders retain their historical dates. Venue/title snapshots on older orders remain historical; the public event link shows current details. No external change notifications are sent.
- During synchronization the event is UPDATING and cannot be discovered or newly booked. The organizer list refreshes pending updates. A definitive business rejection restores the previous status/settings and reports the reason.

## Persistence and recovery

Catalog V4 stores a durable revision intent before contacting Admission and adds UPDATING. Admission V6 stores a receipt in the same transaction as changing sales, sales windows and confirmed booking times. Matching operation retries never apply a second shift. Catalog finishes its own event update after Admission acknowledges; its scheduled worker resumes pending intents after network failures or restart. Owner/version/registration-rule checks run before staging.

Admission serializes revisions with configuration/activation through the event advisory lock and with bookings/cancellations through the sales row lock. Configuration, booking and pre-registration reject stale schedule/capacity snapshots. The full inventory invariant is preserved; no cross-schema access is introduced. The first ticket configuration can race with a revision, so a missing draft sales row is initialized using the new metadata and stale configuration is rejected.

Deploy Admission before enabling the new Catalog command, followed by Web. The migration is additive except for extending Catalog's status check. Do not roll Catalog back while UPDATING intents remain: older versions cannot reconcile them. Normal image rollback does not reverse migrations.

## Verification

`scripts/schedule-acceptance.py` includes all existing workspace/booking regressions, then verifies owner isolation, version conflict, successful rescheduling, unchanged available places, confirmed-ticket dates, sales-window shifts, rejection below allocated capacity, locked published requirements, configured draft updates and recovery after Admission outage plus Catalog restart. A repeated pending request cannot shift dates twice. Run only in an isolated test stack.

Browser checks measure search input/button/category alignment, two equal-width desktop card columns, mobile overflow and checkbox dimensions/focus behavior. Checkbox labels remain on one line each; options wrap as complete items on narrow screens. Mouse selection has no focus box, while keyboard navigation retains a subtle violet focus indicator.
