# Predeployment fixes — 2026-10-17

The three code issues found in the overall review are fixed. Validation used the independent port-18084 PostgreSQL/three-service stack with two Admission replicas. No cloud experiment or remote CI execution is claimed.

## Behavior and design

- All Identity platform-administration methods use `PlatformAccess`: a signed ADMIN claim must also match an active account's current ADMIN database role. The same old token receives 403 after demotion. Organization access remains independently membership-based. Grants still require a new token.
- Organization approval/soft deletion persists CLOSING before any remote work. The Identity worker calls Catalog with the organization token, operation ID and original request time. Catalog's transactional organization fence prevents stale authorized create/edit/publish requests from introducing new event work, while pending publication/revision is allowed to settle. The closure then uses the existing event cancellation workflow for events unfinished at the original request time. Admission cancels bookings and unused tickets and sends attendee notices, including to nonmembers. Identity removes memberships/invitations and finalizes SUSPENDED/DELETED only after completion. Receipts make outage/restart and lost-acknowledgment replay safe. Historical check-ins and personal accounts remain; temporary suspension remains reversible, permanent closure does not.
- Members are searched/paged in Identity SQL, with bounded size 1–50, literal case-insensitive username/email search, stable username/user-ID order and consistent counts. The response is now a page object rather than an array. Organization previews fetch three items; directories/staff selection fetch twelve. Selections are independent of the current page and stale search responses are ignored.

## Validation

- Maven verify: 34 tests passed (Identity 8, Catalog 11, Admission 15); no skips/failures/errors.
- Frontend: 85 tests passed, including server page changes, cross-page staff assignment, stale search responses and CLOSING controls. TypeScript (including unused-local/parameter checks) and production build passed.
- `predeployment-fixes-acceptance.py`: same-token admin demotion denied on account, organization and review APIs; 38-member stable pages/search/counts, limits and organization isolation; approved closure with an already-pending revision; stale database writer rejected by the closure fence; Identity/Catalog restarts plus Admission outage; external attendee cancellation notices exactly once; historical check-in retained; lost acknowledgment replay; direct soft deletion and personal login retained.
- Legacy upgrade fixture: before V9, created an approved old-style closure with a future confirmed ticket, plus an unrelated temporary suspension. After upgrading, the former ticket was cancelled and closure completed, while the latter had no closure operation and stayed normally suspended. V9 recovers identifiable approved closures/deletions. Legacy deletions with no recorded closure timestamp use migration time as the cutoff.
- Full regression chain passed: organization governance, membership notifications, organization acceptance (including publication, booking, editing, pre-registration, contacts, schedule and staff checks), event-wide cancellation/fault recovery and database schema isolation.
- Python scripts parse, OpenAPI local references resolve, Markdown local link targets exist, and `git diff --check` passes.

The SQL test-fixture connection initially lacked the Identity search path and was corrected. Catalog V11 pins the new trigger's schema so maintenance callers cannot accidentally resolve another schema's similarly named table. Final tests run against the corrected migrations. Fault injection was confined to the independent stack.

## Rollout

Private backup: `.secrets/backups/2026-10-17-predeployment-fixes/before-upgrade.dump`; archive listing verified. Deploy Catalog V10/V11 first, then Identity V8/V9 and Web together because the member endpoint changed from an array to a page. Admission remains V10. Local rollout completed: verified Identity V9 / Catalog V11 / Admission V10 and all three readiness endpoints through the gateway. The isolated test stack was stopped afterward. Do not roll back to binaries unaware of CLOSING, the fence or the page contract. No commit/push was performed.

The CI configuration now includes the new acceptance script. `check-db-isolation.sh` respects SEMS_ENV_FILE/SEMS_COMPOSE_FILE, so isolated verification no longer implicitly queries the shared stack. Remaining work is delivery/security gates, cloud configuration/experiments, actual phone HTTPS testing and course evidence; this change does not claim to finish those tasks.
