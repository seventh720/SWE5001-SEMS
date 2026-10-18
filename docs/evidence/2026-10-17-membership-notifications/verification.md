# Organization role notifications — 17 October 2026

Local working-tree validation; not a cloud measurement.

- Identity Maven verify passed (6 existing tests); first sandbox run could not attach Mockito, rerun outside sandbox passed.
- Frontend: 76 tests passed; TypeScript and Vite build passed. Notification tests cover the third unread-count source and role-notice read action.
- Disposable Compose project `sems-role-review`, dedicated network/volume and gateway port 18082: fresh Identity V6 migration and `scripts/membership-notifications-acceptance.py` passed.
- API/database acceptance covers initial organization administrator assignment, invitation acceptance/replay, role/status changes, unchanged and stale updates, notice ownership, per-user read/all-read, retained inbox access after removal and administrator reappointment.
- Membership events are written in the membership transaction via a database trigger. Existing memberships are not backfilled. Notification endpoints require JWT and scope all queries/updates to its subject.
- Pre-deployment database dump retained privately in `.secrets/backups/2026-10-17-membership-notifications/`; pg_restore archive listing validated. No credentials or dumps are committed.
