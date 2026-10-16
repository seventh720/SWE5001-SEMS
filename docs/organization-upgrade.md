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
- Staff assignment is per event, only for active members of that organization. Assigned users check in by manual code or a scanner that enters the QR value. Browser camera capture is not included. Membership is checked live; assignment and ticket state are checked under the same sales-row lock used by cancellation. Duplicate scans report the original result without increasing attendance.
- Existing ticket entitlements and attendee-owned booking history remain valid after membership removal. A removed member cannot view internal event details or create a new booking; request-key replay can retrieve the existing owned booking. Pre-registration snapshots remain personal history, but confirmation rechecks eligibility.
- Pausing an event does not invalidate tickets or prevent staff from checking them. No check-in time window is enforced in this increment. Event-wide cancellation remains separate pending work.
- Organization suspension disables member/manager/staff permissions. It does not unpublish public offerings or revoke existing ticket entitlements; pause events before suspending if public sales should stop.
- Authorization service failure returns 503 for dependent operations rather than using stale roles. Anonymous public discovery does not depend on Identity. An operation already authorized may finish during membership revocation; this is not a cross-service atomic revocation guarantee.

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
