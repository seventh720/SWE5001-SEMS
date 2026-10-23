# SEMS Web Application

React + TypeScript client for public discovery, free bookings and QR tickets, saved registrations, staff check-in, notifications, organization management and platform administration. Backend services enforce business permissions.

## Development and checks

From the repository root:

```bash
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Vite serves `http://localhost:15173` and proxies `/api` to the running gateway at `http://localhost:18080`. Start the backend stack using the [root setup guide](../../README.md). Before submitting changes:

```bash
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

The build includes TypeScript checks; `dist/` must exist before building the Compose web image. Container rebuild instructions are in the root guide.

## Interface conventions

New registration passwords must contain 8–16 printable ASCII characters (U+0021–U+007E): English letters, digits or symbols, alone or in any combination. Spaces, control characters and non-ASCII characters are rejected by both the form and Identity. Existing-account login remains compatible with previous passwords.

- Business access uses current organization membership; platform-admin role changes also check the current database role. JWTs expire after one hour and expired sessions return through login.
- Date inputs and displayed event times use Singapore time (UTC+08:00); APIs receive UTC timestamps. Selects, calendars and time controls use shared custom components. Decorative asterisks use SVG to avoid mobile emoji substitution.
- Organization events show six per page; My events and the public directory show ten. Management filters combine title, publication status, event time and visibility before pagination. Member search combines username/email, role and membership status; the full directory shows twelve per page.
- The organization-admin overview shows all-time organization totals, independent of event-list filters. Regular organizers retain shared event management and attendance access but cannot view this overview.
- Ended events remain available as history and cannot be edited or reopened. Check-in requires event assignment and an open check-in window.

See [business rules](../../docs/functional-guide.md) and [test coverage](../../docs/test-coverage.md). Desktop and 390px mobile browser checks cover the overview and filters. Phone camera check-in has also received a manual device check; device-specific decoding success rates have not been measured.
