# SEMS Web Application

React + TypeScript client for public discovery, free bookings and QR tickets, saved registrations, staff check-in, notifications, organization management and platform administration. Backend services enforce business permissions.

## Development and checks

From the repository root:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Vite serves `http://localhost:15173` and proxies `/api` to the gateway at `http://localhost:18080`. Start the backend stack using the [root setup guide](../../README.md). Run checks with:

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

The build includes TypeScript checks; `dist/` must exist before building the Compose web image. Container rebuild instructions are in the [development guide](../../docs/development.md).

## Interface conventions

- Business access uses current organization membership; platform-admin role changes also check the current database role. JWTs expire after one hour and expired sessions return through login.
- Date inputs and displayed event times use Singapore time (UTC+08:00); APIs receive UTC timestamps. Selects, calendars and time controls use shared custom components.
- Event and member filters apply before pagination. Organization event filters combine title, publication status, event time and visibility; member filters combine username/email, role and membership status.
- The organization-admin overview shows all-time organization totals, independent of event-list filters. Regular organizers retain shared event management and attendance access but cannot view this overview.
- Ended events remain available as history and cannot be edited or reopened. Check-in requires event assignment and an open check-in window.

Permissions, password requirements and lifecycle rules are in the [functional guide](../../docs/functional-guide.md) and [security guide](../../docs/security.md). Browser and device verification is documented in [test coverage](../../docs/test-coverage.md).
