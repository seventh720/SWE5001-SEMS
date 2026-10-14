# Platform positioning and producer onboarding

## What is being built

The revised proposal (sections 3.1–3.3, 5.2 and 5.5) defines a shared event/ticketing platform plus one Web Application. Producers are independent organizers, consumers are participants, and the reusable offering is a published event with ticket types and limited capacity. Identity, Event Catalog and Admission expose shared APIs; the Web Application composes these APIs into role-specific workflows. Business rules live on the server and persist to service-owned schemas.

This is a functioning platform increment with a demonstration application. It is not yet the complete proposed delivery: staff assignment/check-in, event-wide cancellation, attendance summaries, cloud deployment and measured scaling/failure/security evidence remain pending. Local CI/concurrency results do not substitute for measured cloud results.

## What an organization can do today

1. A representative registers a normal account.
2. A platform administrator grants the ORGANIZER role.
3. That organizer creates its own event, selects a category and artwork, configures requested contact fields, then saves free ticket types, quotas and sales windows.
4. Publication exposes the offering in the common catalog. Participants register through the same booking and ticket APIs as for other organizers.
5. The owner manages its own drafts, published presentation and confirmed registration list. A different organizer cannot manage these records, including through direct API calls.

A new organizer or offering needs configuration, not a code change or another deployment. Its content is entered through forms/API requests. There is no automatic import of the organization's existing website, CRM or event database. Reusing a template currently copies the current user's event content, capacity, category/theme and registration requirements into a new unsaved draft. New dates, ticket configuration and publication are explicit; attendees, tickets, ownership, inventory and old publication state are not copied.

## Two demonstration scenarios

| Shared capability | Student society seminar | Training provider workshop |
|---|---|---|
| Identity and authorization | Society representative receives organizer role | Training representative receives organizer role |
| Offering configuration | Seminar description, campus venue, student contact requirements | Workshop description, training venue, contact requirements/custom question |
| Ticketing | Free general/student quotas and a sales window | Free workshop quota and a sales window |
| Consumer workflow | Discover, optionally pre-register, confirm, view QR/manual tickets | The same APIs and workflow |
| Ownership | Society sees only its own management records | Provider sees only its own management records |
| Remaining core work | Assigned staff/check-in and attendance summary | Reuse the same forthcoming capabilities |

Record account onboarding, configuration steps, elapsed setup time and actual code changes (expected zero for a second ordinary offering), then run cross-organizer negative tests. This is the platform demonstration, rather than displaying unrelated UI features in isolation.

## Enterprise integration is a different scope

Current isolation is organizer-account ownership. It does not model a company tenant with multiple employees, organization-scoped roles, delegated management, a branded company storefront, custom domains or enterprise SSO. Enterprise hierarchies and separate organizer databases are explicitly excluded by the revised proposal.

Supporting those capabilities would require an organization/membership model and authorization rules, onboarding/admin workflows, content visibility and branding, migration of existing owner records, and tenant-isolation tests. External integrations additionally need an explicit import/API authorization contract and synchronization/error handling. These are separate follow-on requirements, not functionality implied by today's registration page. The current project should complete the two organizer scenarios and core cloud evidence before promising enterprise SaaS integration.

## Presentation editing contract

Published presentation updates use PATCH /api/v1/organizer/events/{id}/presentation with owner/role and optimistic-version checks. Only title, description, venue, category and artwork can change. Dates, capacity, sales windows, registration fields and existing tickets remain unchanged. Historical booking snapshots retain the details confirmed at booking time; the public event page shows the current venue. No automatic change-notification delivery is implemented. Schedule/capacity edits are now available through the separate recoverable revision workflow described in [schedule revision](schedule-revision.md). The presentation-only PATCH contract above remains available.

## Dashboard and navigation

Signed-in users see upcoming confirmed bookings (server-filtered, ordered by start, maximum five) and their latest four saved pre-registrations, with links to full lists. A separate community section shows the next three published offerings from the shared catalog. Organizer/admin roles add organizer tools; admins additionally get account/role management. Staff see an accurate pending-workflow notice, not invented assignments. Anonymous visitors retain the public landing page. The right-anchored Explore disclosure leaves the page visible, closes on Escape/outside click/navigation, and has no modal scrim or page scroll lock.
