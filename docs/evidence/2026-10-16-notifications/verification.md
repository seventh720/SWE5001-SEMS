# Notification verification — 16 October 2026

- Maven verify: 25 backend tests passed; all three service builds passed.
- Frontend: 60 tests passed; TypeScript and Vite production build passed.
- Isolated acceptance with two Admission instances passed: account-bound invitation inbox and accept/decline, duplicate pending rejection, booking confirmation/cancellation replay deduplication, committed event/presentation changes, rejected update exclusion, outbox replay, five-minute pre-registration opening reminder, per-user read state and access isolation.
- A pre-deployment dump of the original database was restored into a temporary database and its account/business fingerprints matched.
- Deployed schema versions: Identity V5, Catalog V8, Admission V9. Original account/password, event, booking and ticket fingerprints matched after migration.
- Original administrator login and both notification API families passed on port 18080. Runtime JAR hashes, gateway configuration and web index matched local builds; all backend readiness checks returned UP.
- Private backup: .secrets/backups/2026-10-16-notifications. No credentials or dumps are included in evidence.
- Standalone feature design and timing limits: ../../in-app-notifications.md.
