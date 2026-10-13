# Free booking and individual tickets

This increment implements revised proposal §4.3 and §5.1 items 4–5 through the attendee workflow. Staff assignment/check-in, event cancellation and organizer summaries remain separate work. Category browsing and a forum are not part of this increment.

## State and concurrency

- `ticket_types.reserved` is the number of places committed by confirmed bookings. Available = quota − reserved.
- Booking: `CONFIRMED → CANCELLED`. Each confirmed quantity creates that many separate `VALID` ticket credentials in the same transaction. A cancellation sets all of those tickets to `CANCELLED`. `CHECKED_IN` is reserved for the next staff workflow; cancellation already rejects bookings containing such tickets.
- A PostgreSQL advisory lock serializes the same `(user, requestKey)` before acquiring the sales row lock. The database also has a unique `(user_id, request_key)` constraint. Different payloads on the same key return 409.
- Catalog publication is checked over authenticated HTTP before starting the local transaction. Admission then locks its sales row and checks active state, event start, sales window and capacity. All booking/cancellation writers use the sales row lock; future staff/event-cancellation writers must use the same lock before changing tickets. A conditional SQL update and database bounds protect inventory.
- Completed same-key requests return the existing order without needing Catalog, including cancelled orders. Frontend session storage retains the same key and payload after ambiguous network/server failures and across refreshes. Starting a new intentional order uses a new key.
- Cancellation re-reads after acquiring the lock, rejects started events or checked-in tickets, and releases inventory once. Cancelled records remain for history. Retrying their creation key never resurrects them.
- Owner checks use the JWT subject, never a caller-supplied user ID. Other users (including admins) receive 404. Booking APIs use `Cache-Control: no-store`.

## API and data

Admission adds `POST/GET /api/v1/bookings`, `GET /api/v1/bookings/{id}` and `POST /api/v1/bookings/{id}/cancel`. Creation and replay both return 200. Lists are paginated with bounded size. See the Admission OpenAPI specification for fields and errors.

`V3__bookings_and_tickets.sql` is additive and owns all new tables in Admission. Existing V1/V2 migrations are unchanged. Local foreign keys connect bookings, ticket types and tickets; user IDs are cross-service identifiers. Catalog's internal snapshot adds title/location so historical bookings do not need live cross-schema joins or an available Catalog to render.

Deploy the updated Catalog before Admission so title/location are present; then update gateway/Web. Run the existing build and Compose instructions. Existing database data is retained and Flyway applies V3 automatically. Rolling an image back does not undo V3; once bookings exist, do not run an older inventory writer without checking migration/data compatibility.

QR codes are generated locally using [node-qrcode](https://github.com/soldair/node-qrcode), with the exact unique 192-bit hexadecimal ticket credential as payload. Manual entry uses the same code. No external QR service receives credentials. The attendee detail page hides QR/manual codes for cancelled tickets. Staff validation is not implemented in this increment and QR display alone does not prove admission validity.

## Verification

Run `python3 scripts/booking-acceptance.py` only on a disposable Compose stack after loading `.env`. It also runs publication regression, stops/restarts dependencies, creates test users/orders and seeds checked-in/start-time guard conditions directly in its isolated database. Never run it on a personal/shared data volume you want to preserve.

CI starts two Admission replicas. Acceptance verifies 100 distinct requests for 10 places, identical-key concurrent requests, payload mismatch, per-attendee isolation, sales windows, per-place credentials, concurrent cancellation, and replay during Catalog outage. It independently checks persisted reserved quantity, confirmed booking quantity and valid-ticket count. These checks do not claim cloud performance, autoscaling, measured recovery targets or a completed check-in workflow.

Frontend tests cover uncertain-response retry across remount, definitive capacity rejection, QR/manual-code visibility and confirmed cancellation. Existing authentication, publication and UI tests continue to run.
