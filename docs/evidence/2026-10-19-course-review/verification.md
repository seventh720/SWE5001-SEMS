# Course review verification

Review date: 2026-10-19, Asia/Singapore (work began on 18 October). Source baseline: `0f0b0a8`, plus the documented local cleanup. Existing `.gitignore` change belongs to the user and was preserved.

## Checks completed

- Read all three supplied course/proposal PDFs; visually inspected presentation outline/schedule, briefing requirements and proposal architecture/quality-attribute tables.
- `mvn -q verify`: 34 tests passed (Identity 8, Catalog 11, Admission 15), zero failures/errors. Initial sandbox attempt could not attach the Mockito JVM agent; the approved unrestricted rerun passed. JVM dynamic-agent warnings remain diagnostic, not product logging.
- `npm --prefix apps/web test`: 85 tests in 20 files passed.
- `npm --prefix apps/web run build`: TypeScript and production build passed.
- After removing four unused EventRepository methods: `mvn -q -pl services/event-catalog -am verify` passed (11 Catalog tests).
- New gateway configuration passed `nginx -t` using a temporary copy inside the running gateway. The original Docker Desktop bind mount initially exposed a stale file length; the local gateway alone was recreated to refresh the mount. The remounted `/etc/nginx/nginx.conf` then passed `nginx -t`, and the Admission readiness request through the gateway returned `UP`. No database or application container was restarted.
- Source scan found no stray `.log` files or debug `console.log`/`System.out` statements to delete. Runtime error/retry logs and historical acceptance evidence were retained.

## Local API probes

See [raw observations](api-probes.txt). The probes created uniquely named review accounts and activities on the existing local `sems-platform` stack at `localhost:18080`. That stack had one Admission replica. Application images were pre-existing; this was not a fresh-build isolated acceptance run or a cloud performance test. Existing user activities and cloud data were not modified. Review fixtures remain in the local database.

Passed: publication, free booking, same-key replay, changed-payload rejection, cross-user booking isolation, unauthorized organizer access, assigned-staff check-in, repeated check-in, cancellation refusal after check-in, concurrent quota enforcement and duplicate cancellation inventory release.

The concurrent run used 20 client workers to send 100 requests for 10 places: 10 HTTP 200, 90 HTTP 409. After cancelling one successful booking twice, summary reported 9 confirmed, 1 available, 0 attendance. This is a bounded correctness probe, not 100 VU sustained load.

Two observations require product fixes:

1. After a published event's location changed from `Original venue` to `Updated venue`, the public event detail showed the new location but its existing booking still returned the old location.
2. For a newly created review fixture only, SQL moved the Catalog and Admission start/end into the past to simulate an ended event. The first check-in of its remaining valid ticket returned HTTP 200 with `CHECKED_IN`. No waiting for elapsed real event time was involved.

The last-platform-admin issue, missing 401 session handling, unbounded queries and routing/scaling limits were identified by source inspection; no destructive last-admin test or cloud failure trial was executed.

## Browser coverage

- Cloud HTTPS landing page loaded; public events list displayed `No upcoming events found` at the time of review. This describes the visible public directory, not whether unpublished/private events exist.
- Local login with a review attendee succeeded; Dashboard displayed bookings/notifications; booking detail displayed the QR image, manual code, event information and cancellation controls.
- Ticket layout was visually checked on desktop. Actual phone camera capture and a full browser organizer/staff workflow remain rehearsal tasks. The business mutation probes above used HTTP APIs.

## Scope of changes

Removed unused Catalog queries, filtered only successful readiness access logging, corrected outdated deployment status in README/CI documentation and updated the course review/action plan. No business-rule fix, new theme, translation layer, cloud deployment, push or commit was performed. Current source findings are tracked in the plan; historical evidence is not relabelled as current cloud acceptance.
