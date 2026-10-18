# Flat organization upgrade

## Scope and authority

The platform administrator provisions organizations and appoints their first administrators. Platform ADMIN is not an implicit organization business administrator. Organization roles are ORG_ADMIN, ORGANIZER and MEMBER; membership states are ACTIVE, SUSPENDED and REMOVED. Users may belong to multiple organizations with independent roles. Global legacy ORGANIZER and STAFF claims no longer authorize business operations.

Identity owns organizations, memberships and account-bound invitations. Catalog owns event organization, creator and visibility. Admission owns inventory, event assignments, tickets and check-in. Internal organization lookup uses a new ORGANIZATION_ACCESS_TOKEN. No runtime cross-schema reads or cross-service foreign keys are added.

Existing event-specific `/api/v1/organizer/events/{id}` routes are retained to reduce client changes. List requests require `organizationId`; creation includes it in the body. Every operation derives the actual organization from the stored event and checks live membership. Query/body IDs cannot grant access. Organization transfer is unsupported. Creator ID is retained under the legacy organizer_id storage column and exposed as createdBy; it is not an authorization source.

## Behavior

- Platform admin creates an organization using an existing active account's email as administrator. Organization admin may invite registered users; invite tokens are random, hashed at rest, account-bound and expire after seven days. Recipients receive an in-app invitation and can accept or decline in Notifications; account-bound links can also be shared manually. No email delivery or SSO.
- Last active organization administrator cannot be removed/demoted. Platform admin can appoint a replacement. Membership updates use optimistic versions and serialize on the organization row.
- PUBLIC events appear in common discovery. ORGANIZATION_ONLY events require active membership for organization discovery, details, ticket availability, pre-registration and new bookings. Visibility can be changed through the versioned event revision flow, including after publication. Switching to organization-only restricts discovery and new bookings to active members; existing tickets remain valid. Ordinary public attendance does not create membership.
- Members can read their organization directory. Only ORG_ADMIN changes members/invitations. ORG_ADMIN and ORGANIZER manage all events in their organization and assign staff.
- Staff assignment is per event, only for active members of that organization. Assigned users check in by camera QR scanning, manual code or a keyboard-style scanner. Camera scanning prefers the rear camera on phones, offers camera selection on PCs, and stops after each detected ticket. HTTPS is required on phones; localhost works for local desktop testing. Membership is checked live; assignment and ticket state are checked under the same sales-row lock used by cancellation. Duplicate scans report the original result without increasing attendance.
- Existing ticket entitlements and attendee-owned booking history remain valid after membership removal. A removed member cannot view internal event details or create a new booking; request-key replay can retrieve the existing owned booking. Pre-registration snapshots remain personal history, but confirmation rechecks eligibility.
- Pausing an event does not invalidate tickets or prevent staff from checking them. New check-ins open 15 minutes before the current event start, inclusive; earlier attempts return 409. The database clock is checked under the sales-row lock. Whole-event cancellation is implemented as a separate terminal protocol; see [publication management](publication-management.md). Permanent organization closure invokes it automatically before completion. Temporary platform suspension remains reversible and does not cancel events.
- Organization suspension disables member/manager/staff permissions and hides public discovery/details/new booking eligibility. Existing personal booking history and tickets remain stored. Approved closure additionally marks all memberships REMOVED with the MEMBER role and revokes pending invitations; reactivation does not restore those roles.
- Authorization service failure returns 503 for dependent operations rather than using stale roles. Public discovery and new booking eligibility now consult the active-organization directory in Identity; Identity unavailability returns 503. An operation already authorized may finish during membership revocation; this is not a cross-service atomic revocation guarantee.

## Safe deployment and existing data

This release is a coordinated maintenance-window upgrade, not a rolling mixed-version rollout. Do not rebuild the running development stack before backing up and preparing migration.

1. Record current commit and immutable image IDs. Back up PostgreSQL using `pg_dump` and verify the backup can be read/restored in a disposable database. Preserve the existing .env and keys securely.
2. Stop new external writes (gateway maintenance/stop). Allow PUBLISHING and UPDATING operations to finish; verify no pending event revisions. Stop application services after draining.
3. Run `bash scripts/setup-local.sh` to add the missing organization service token without replacing existing credentials. Build passing backend JARs and web dist; deploy Identity, Catalog and Admission together with external access still closed. Flyway appends Identity V4, Catalog V6/V7 and Admission V8. Existing records are preserved; organization_id is nullable only for the maintenance migration.
4. Generate a mapping using the target Compose/environment files:

```bash
python3 scripts/migrate-organizations.py --plan /tmp/sems-organization-plan.json
```

The plan creates one initial organization for each legacy organizer and event owner, with the existing owner as ORG_ADMIN. Review/edit organization names and verify all owner IDs. The script refuses inactive/missing owners; assign a valid business owner deliberately before migration. It captures booking/ticket/inventory fingerprints. Do not store this plan publicly.

5. Apply only after checking the backup and maintenance state:

```bash
python3 scripts/migrate-organizations.py --plan /tmp/sems-organization-plan.json --apply --maintenance-confirmed
```

The tool uses separate service-role transactions, stable organization IDs and idempotent mapping. Interrupted work can be resumed using the same plan. It refuses pending operations, changed business fingerprints, conflicting mappings or remaining unmapped records. Do not reopen traffic after a partial failure. The maintenance administrator's final cross-schema consistency query is not application access.

6. Verify the organization administrator can manage migrated events and existing attendee tickets still work. Verify a second organization cannot access management data. Reopen the gateway only after checks pass.

A rollback after accepting new organization data must not simply run the previous owner-based application: that version cannot enforce internal visibility or organization roles. Before reopening, either fix forward or restore the pre-upgrade backup and matching old images during maintenance, explicitly reconciling any post-upgrade writes. SQL migrations do not reverse when images roll back.

## Verification

Run `mvn verify`, `npm --prefix apps/web test`, and `npm --prefix apps/web run build`. In a disposable Compose project run `python3 scripts/organization-acceptance.py`; it includes the pre-existing editor acceptance chain, publication/revision outage recovery, 100 requests for 10 places through two Admission replicas, then organization and check-in checks. Set SEMS_BASE_URL, SEMS_ENV_FILE and SEMS_COMPOSE_FILE for isolated environments; set bootstrap credentials in the process environment. Never run fault-injection acceptance against a shared working instance.

Use a distinct Compose project, network name, volume name and host port. Docker Compose's normalized config includes explicit network/volume names: changing only its `name` field does not isolate those resources.

## Demonstration

Provision Society A and Training B, invite members to A, publish an internal seminar and public workshop, browse as member and outsider, assign one staff member only to the seminar, check a ticket twice and show attendance remains one. Demonstrate a third organization onboarding without code changes. Show platform admin cannot implicitly read organization booking lists. This expands the original proposal's account ownership model; enterprise hierarchy and SSO remain excluded.

### Local frontend proxy

The unified local environment uses gateway port 18080 and PostgreSQL port 15432. Vite on 15173 proxies to 18080 by default. An optional ignored `apps/web/.env.development.local` can set `API_PROXY_TARGET`; the current local override points to 18080. The old isolated 18081 preview is stopped after migration.

### Local deployment — 15 October 2026

The original database was backed up and restored into a temporary database to verify the backup before migration. Identity V4, Catalog V6/V7 and Admission V8 were applied. Legacy activities were assigned to their existing owner's organization; existing user credentials, bookings, tickets and inventory were preserved. The original admin is also ORG_ADMIN of the migrated organization. Private backup files are under `.secrets/backups/2026-10-15-organization-upgrade` and must not be committed.

For Navicat, use a PostgreSQL connection to `127.0.0.1:15432`, database `sems`, username `postgres` and the existing local `POSTGRES_PASSWORD` value from `.env`. No SSH tunnel is required for this local connection. Expand the `identity`, `catalog` and `admission` schemas. The web admin password is unrelated to the PostgreSQL password. Existing Navicat connections with these settings can simply reconnect and refresh.

## Organization governance

Identity V7 adds organization versions, profile/closure requests and soft-deleted state. Platform ADMIN can edit name/address, appoint administrators, suspend/activate, review requests, and soft-delete. ORG_ADMIN may submit one pending request per organization, with a reason and current organization version. Review requires a note; rejected requests do not change organization data, and stale approvals fail instead of overwriting newer platform edits.

Approved closure and direct soft deletion first persist CLOSING in Identity. Workspaces and new organization operations become unavailable immediately. A durable worker calls Catalog with the organization service token, immutable operation ID and original request time. Catalog fences event writes, waits for prior publication/revision work to settle, and uses the existing cancellation protocol for events unfinished at the closure request time. Admission cancels confirmed bookings and unused tickets and notifies attendees, including people outside the organization. Historical check-ins remain intact.

Only after cancellation completes does Identity revoke memberships/invitations and finalize SUSPENDED (approved closure) or DELETED (soft deletion). Closed organizations cannot be reactivated or reassigned, while a temporary platform suspension can still be activated. The admin list exposes `closureRequested` to distinguish these cases and polls CLOSING progress. Soft-deleted organizations disappear from the list after completion. Personal accounts, historical records and unrelated organizations remain available. Closing does not remove platform ADMIN from an account. No paid-ticket/refund workflow exists.

All stages persist their intent/receipts and retry after outages or lost acknowledgments. No database transaction makes a remote HTTP call. A Catalog database trigger serializes organization event writes with the closure fence, covering requests authorized before closure. Pending publication/revision can finish, but closure waits and cancels the resulting unfinished event. New create/edit/publish work cannot reopen a fenced organization. The original request time remains the cancellation cutoff even if services are unavailable until an event ends.

Catalog filters public pagination using active organization IDs from Identity and resolves the latest organization name. Published booking eligibility also checks organization activity. This introduces an Identity dependency for anonymous discovery. A pre-authorized booking may commit before cancellation obtains the sales lock; it is then included in cancellation. CLOSING is an intermediate state, not a claim that all tickets are already invalid.

Request submissions notify active platform administrators; decisions and profile/closure changes notify affected users through the existing organization inbox. This provides persistent in-app notifications, not external messaging. Request/history API access remains permission checked.

Deploy Identity (V7), Catalog and Web after backup, then reload the gateway. Do not roll Identity back to a version unable to understand DELETED while deleted rows exist. Acceptance: scripts/organization-governance-acceptance.py in an isolated environment.

## Platform authorization and member pagination

Every platform ADMIN method checks both the signed claim and the current active account's database role through `PlatformAccess`. Removing ADMIN takes effect on subsequent requests using the same old token. Granting ADMIN still requires a new login/token. This does not grant organization business membership.

`GET /api/v1/organizations/{org}/members?page=0&size=12&search=...` returns `{items,page,size,totalElements,totalMembers,totalPages}`. The old array response is replaced. Queries are scoped to an authorized organization, search username/email case-insensitively with literal wildcard characters, and order by normalized username and user ID. Size is 1–50; search is at most 200 characters. Counts and rows use a consistent read transaction. The organization preview fetches three entries; the directory and staff picker fetch one page of twelve and ignore stale search responses. Assignment selections are stored by user ID independently of the visible page.

Upgrade order: back up, deploy Catalog V10/V11 (closure fence and fixed trigger schema), then Identity V8/V9 and Web together. Identity V9 recovers identifiable earlier approved closures and soft deletions; it leaves temporary suspensions alone. For legacy deletions without a recorded closure timestamp, migration time is the cutoff. Services remain within their owned schemas. Backward binaries cannot safely handle CLOSING or the new paged API. Inspect pending `identity.organization_closures`, `catalog.organization_closures` and event cancellation receipts when diagnosing recovery; repair connectivity/service failures and let workers continue, rather than manually clearing the fence.

Run `scripts/predeployment-fixes-acceptance.py` on an isolated stack for old-token revocation, member pagination, pending event revisions during closure, stale publication rejection, Admission outage, Identity/Catalog restart, acknowledgment replay and direct deletion. The existing governance and membership-notification scripts also use the paged member contract.
