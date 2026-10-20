# Organization management and live API acceptance

Verified on 2026-10-20. Application baseline: `228633d6c2ae9ddeae4517f5294c5d94d4978fa2` (PR #19). Its [main pipeline](https://github.com/seventh720/SWE5001-SEMS/actions/runs/39312012048), including the actual staging deployment step, passed. The live run used `https://swe5001.seventh720.com`; it did not inspect host container digests or access the cloud database.

The standalone [acceptance script](../../../scripts/organization-management-acceptance.py) is wired into the CI integration job. It passed against real local services and staging public APIs. Workflow actionlint, Python syntax/target guards and diff whitespace checks passed. The remote CI result for this new script must be established by its own PR; the linked application deployment predates this test-only change.

## Scenarios

- Registration rejects invalid length, spaces and Chinese with English password guidance. Four new accounts successfully registered/logged in with a 16-character password containing letters, digits and symbols.
- Empty organization metrics, ORG_ADMIN-only overview, organizer denial, ordinary member/other organization/platform-admin denial, and blocked external internal-summary routes.
- Member name/email, role and ACTIVE/SUSPENDED/REMOVED filters combined before pagination; role/status changes and invalid queries.
- Event title, publication status, visibility and time filters before pagination; stable pages, empty/out-of-range pages and invalid queries. Local-only fixtures exercise ongoing/ended and draft editing boundaries.
- Member discovery, event detail/inventory, booking, same-key replay, private ticket retrieval, unassigned-staff denial, check-in and duplicate check-in, attendee cancellation, event cancellation, pause and attendance details. Other users cannot read the booking.
- Organization totals follow an independent fixture ledger: eight events, seven valid tickets and three check-ins after cancellations. Paused and ended events remain included; cancelled orders/events are excluded even when a cancelled event retains a historical check-in. Filters/pages do not narrow the overview.
- Staging waited for a short fixture event to end naturally, then verified revision/presentation edits return 409 and leave its version/end time unchanged. No staging SQL, time manipulation, failure injection or service restart was used.

This is HTTP/API acceptance. It does not establish physical phone camera decoding, QR rendering in a real browser, cloud load/scaling performance or a recovery SLA.

## Data retention and cleanup

The user explicitly accepted retained accounts/history and cleanup using product features. Each run created four unique accounts, two isolated organizations and eight events; only its own fixture IDs were operated on. Offerings were cancelled, fixture organizations soft-deleted and organization access verified revoked. Both successful runs reported `cleanup.complete=true` with no failed IDs. Local fixture-development failures also exercised the `finally` cleanup path successfully.

Four staging accounts and the related orders, notifications, tickets and check-in audit history remain by design. The product has no account deletion/disable API; this was not a database purge. Raw staging fixture IDs/generated emails are retained in ignored `.secrets/acceptance/` reports. Passwords, authentication tokens and ticket credentials are absent from reports and evidence.

The live run completed at **2026-10-20 16:45:52 SGT**. All three HTTPS readiness endpoints returned `UP` after cleanup. See the [credential-free summary](summary.json) for exact timestamps, fixture counts, checks and cleanup results.
