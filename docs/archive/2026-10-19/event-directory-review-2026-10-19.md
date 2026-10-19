# Event directory and organizer collaboration review

> 分阶段检查记录，保留当时的版本、测试数与发布状态。当前进度以[项目进度](../../progress.md)和[测试覆盖情况](../../test-coverage.md)为准。

## Changes

- Camera preview uses the source video's aspect ratio and updates when video dimensions change. A 420px height limit keeps a portrait feed manageable; the complete frame remains visible without artificial sidebars. Destructive cancellation buttons now use semibold text.
- Organization overview (6 per page) and My events (10 per page) already had backend pagination. Both now offer title search across the complete organization, rather than filtering only the current page. Organizer search is case-insensitive and treats `%` and `_` literally.
- Search resets pagination; a shrinking result set returns to a valid page. Failed list loads clear stale results and offer retry. Empty search results are distinguished from an organization with no events.

## Collaboration rules confirmed

There is no configured maximum number of ORGANIZER memberships per organization. Organization administrators assign these roles; the legacy global ORGANIZER role does not itself grant organization access.

All active ORG_ADMIN and ORGANIZER members manage the organization's shared events, including drafts created by another organizer. They can edit, publish, pause/cancel, inspect registrations, and assign staff. Creating an event does not grant exclusive ownership. Other organizations remain isolated. Concurrent writes use version checks; a stale save returns 409. Live membership checks revoke management access after demotion without waiting for JWT expiry. Scanning additionally requires an active event staff assignment.

## Validation and scope

- Frontend: typecheck, production build and 100 tests passed.
- Backend: Maven verify passed, 43 tests.
- Real local PostgreSQL/API acceptance: multi-page search, case-insensitive matching, literal wildcard characters, organization isolation, two collaborating organizers, cross-account editing/publication, stale-write rejection and immediate demotion enforcement passed. Added this acceptance script to CI.
- Browser: at 390×844, a simulated 720×1280 stream displayed at 236.25×420 with both top/bottom markers visible. This verifies geometry, not physical iPhone hardware.
- Cloud read-only check: deployed SHA `32d9344c92380b1d0b442f4b4af258d9ae4b4e5b`; health checks passed and a fresh login returned `expiresIn: 3600`. Cloud business data was unchanged.

Personal bookings, pre-registrations, organization registration lists, member directories, governance records and check-in tasks already have pagination. This change focuses search on event management. The organization invitation history still returns a complete array; pagination there is a separate remaining usability improvement if invitation volume grows.

No additional blocker was found in the scoped collaboration, search and camera review. This is not a claim that all system paths are defect-free. These changes remain in the working tree and are not yet deployed.
