# In-app notifications

Notifications are available from the signed-in navigation bar and /notifications. Its badge combines actionable organization invitations and unread ticket/event updates. The inbox and badge refresh every 30 seconds; the badge also refreshes on focus and inbox actions. This is a persistent in-app inbox, not email, browser push, or a background OS notification.

## Invitations
Identity owns the existing invitation records. Registered recipients see the organization, proposed role and expiry, and can accept or decline using their authenticated account. An invitation ID alone cannot grant another account access. The account-bound sharing link remains available as an alternative to the inbox. Pending duplicates are rejected; an administrator can revoke and recreate if necessary. Accepted/revoked/declined/expired invitations remain in history. Marking business updates read does not dismiss an actionable invitation.

## Ticket and event updates
Admission writes booking confirmations and cancellation notices in the same transaction as the corresponding operation. Per-user unique delivery keys prevent request replay from producing duplicate notifications. No historical booking notices are backfilled.

Catalog queues a durable outbox record in the same transaction as a successful published/paused revision. Presentation changes also enqueue via a database trigger. Draft publication and rejected changes do not notify. A scheduled delivery worker forwards committed changes to Admission over the existing authenticated service connection; delivery retries use the outbox ID for recipient deduplication. Active booking holders and saved pre-registration users receive the event's current name, time, location, publication status and visibility. Existing ticket rights are unchanged, and notification links do not bypass access checks.

Admission checks saved pre-registrations every 15 seconds. A reminder is persisted when a ticket's opening is in the next five minutes, sales are active, the event has not started and places remain available. This refers to the registration window, not the event start time. New saves inside that window are eligible on the next check. Deduplication includes the ticket opening time, so rescheduling a future opening can produce a new reminder. Removed pre-registrations and already booked ticket types are not selected. If the entire service is offline through the window, no retroactive 'opens soon' notice is claimed.

## Storage and deployment
Identity owns invitations and membership notices, Catalog owns its event outbox, and Admission owns ticket/event notices. Schema changes use each service's Flyway migrations. Gateway routes `/api/v1/me/invitations*` to Identity and `/api/v1/me/notifications*` to Admission. Preserve credentials and data volumes during updates; follow [delivery and rollback](k3s-cd.md).

Run scripts/notifications-acceptance.py only in a disposable environment. It checks invitation identity and actions, booking replay/cancellation, stale/rejected event updates, outbox retry, reminders through two replicas, per-user read state and cross-account isolation.

## Organization role updates

Identity maintains a private membership notification inbox. An AFTER INSERT/UPDATE trigger on organization_memberships records initial administrator appointments, accepted invitations, role changes and membership status changes in the same transaction. Unchanged role/status writes and rolled-back mutations produce no notices. Existing assignments are not backfilled.

The authenticated /api/v1/me/membership-notifications endpoints provide paginated history, unread count and individual/all-read actions scoped to the JWT subject. Notifications remain readable after membership removal, but links do not restore access. The web inbox has a separate Organization role updates section and includes its unread count in the navigation badge. It refreshes every 30 seconds. This inbox covers organization memberships, not legacy platform account roles or event staff assignments.

Membership notification storage remains within Identity; it does not introduce cross-service database access or external messaging.

## Permanent organization closure

Identity records CLOSING and informs members that closure is pending. Catalog stages whole-event cancellation; Admission atomically cancels bookings/unused tickets and records attendee notices, including nonmembers of the closing organization. Identity sends completion notices and removes memberships only after those cancellations finish. Durable receipts prevent duplicate booking cancellation notices after restarts or lost acknowledgments. Personal notification history remains available after organization access ends.
