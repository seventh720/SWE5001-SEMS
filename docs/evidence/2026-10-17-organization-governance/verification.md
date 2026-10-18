# Organization governance — 17 October 2026

Local working tree, not a cloud performance result.

- Maven verify: 29 tests passed (Identity 6, Catalog 8, Admission 15). Updated an existing mock query to include the soft-deletion condition.
- Frontend: 79 tests passed; TypeScript/Vite build passed. New tests cover request submission, deletion name confirmation/version, and mandatory review notes.
- Dedicated project/network/database volume `sems-governance-review`, gateway 18083: Identity V7 migration and organization-governance-acceptance.py passed.
- Real HTTP/PostgreSQL checks cover scoped submission, duplicate pending requests, approval/rejection, duplicate review, stale approval rejection after direct edits, organization name reflected in public offerings, closure to SUSPENDED, revoked member access, public event hiding, new booking rejection, retained historical tickets, independent organization access and soft deletion to DELETED.
- Backend review/close/delete operations lock the organization row; requests capture organization versions. No cross-schema application access was introduced.
- Existing database was backed up privately under `.secrets/backups/2026-10-17-organization-governance/`; archive listing verified before deployment. No dump or secrets included here.
