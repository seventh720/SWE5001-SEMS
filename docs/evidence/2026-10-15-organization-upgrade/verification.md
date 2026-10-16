# Organization upgrade verification — 15 October 2026

Source: working tree based on 17c9503 (uncommitted organization upgrade). Local results, not cloud scalability measurements.

## Environment

Java 21 / Spring Boot services; React/TypeScript frontend; PostgreSQL 17; isolated Docker Compose project `sems-org-review`, network `sems-org-review_default`, volume `sems-org-review-db`, gateway 127.0.0.1:18081. Two Admission replicas. Existing platform remains on Identity V3, Catalog V5 and Admission V7; its application/database upgrade was not applied.

## Results

- `mvn -o verify`: 22 tests passed, all three JAR builds passed. Executed outside the sandbox because Mockito JVM attach requires it.
- `npm --prefix apps/web test`: 50 tests passed in 13 files, including organization switching, role-based UI, invitation acceptance and duplicate/rejected check-in feedback.
- `npm --prefix apps/web run build`: TypeScript and Vite production build passed.
- `scripts/organization-acceptance.py`: full existing acceptance chain plus organization authorization, internal-event access, invitations, last-admin protection, concurrent one-time check-in, membership removal and preserved existing ticket ownership passed. See business-acceptance.txt.
- `scripts/organization-security-acceptance.py`: invitation expiry, existing-JWT role promotion/demotion, assignment revocation, current staff task titles before bookings/after presentation changes, platform-admin business isolation passed. See security-acceptance.txt. This targeted check followed the final task-title change.
- `scripts/organization-migration-acceptance.py`: legacy-owner fixture migration and repeated application passed; booking IDs/request keys, ticket credentials and inventory preserved. See migration-acceptance.txt. This exercises pre-upgrade ownership data in the upgraded schema, not a full restore of the user's database.
- All three OpenAPI JSON files parsed and local schema references resolved. This is structural validation, not exhaustive automated OpenAPI conformance testing.
- Browser check on Chrome: sign in with a disposable account, organization selection, members/invitation controls, organization event list, staff/attendance view, task list and manual-code check-in form rendered. Final organization selector styling inspected visually. Actual mutation/concurrency checks are covered by API acceptance.
- `git diff --check` passed.

## Test setup correction

The first normalized Compose configuration retained the original network name. Before isolation was corrected, three test accounts with prefix `accept-76f9a18f64` were created in the existing platform. The run stopped at admin login, before activity/order creation and fault injection. Read-only inspection confirmed zero activity/order associations. With approval, exactly those three fixed-ID test accounts were privately backed up and deleted after checking there were also no pre-registration/profile associations or privileged roles. The original database schema versions remain unchanged. Subsequent fault tests ran only on the dedicated network/project.

## Operational boundaries

No deployment to the existing platform, no SSO, no enterprise hierarchy, no browser-camera QR scanner, and no cloud performance results are claimed. Check-in accepts manual codes or a keyboard-style scanner. Current code and test configuration are ready for a coordinated maintenance migration; see ../../organization-upgrade.md for backup, mapping, deployment and rollback requirements. The new organization service token was added to local configuration without replacing existing credentials.

## Follow-up: organization UI and editable visibility

Organization selection now uses cards with separate name/role labels; native and custom dropdowns share the same SVG chevron and inset. Published visibility changes use the existing versioned revision flow. The former publication lock was removed; registration requirements and organization ownership remain unchanged.

Validation: 52 frontend tests, production web build and Maven verify passed. The new disposable-stack visibility-acceptance.py passed public-to-internal and internal-to-public discovery/detail/inventory/booking checks, retained existing tickets, and rejected outsider/stale edits. Browser inspection covered the organization overview and the enabled visibility field. Catalog and Web were deployed to 18080 without schema changes; Catalog readiness returned UP. The isolated test stack was stopped afterward.

## Follow-up: organization Events/Members sections and custom dropdowns

All remaining native select elements were replaced with the shared custom Select component. Organization detail defaults to Events with role-scoped event cards, counts, pagination, creation and management links. Member discovery uses the public/member-authorized endpoint; manager listings use the organization management endpoint. Invitations and membership controls are separate under Members.

Validation: 54 frontend tests and production build passed; source scan found no native select/option elements. Browser inspection verified event cards, member section, mouse and keyboard dropdown opening and Escape closing. Runtime SHA-256 comparisons matched all three backend JARs, gateway configuration and the deployed web index against local artifacts; backend readiness checks returned UP. Only the web image needed updating for this increment.
