# Contributing

Start from the [local setup guide](README.md#2-local-setup), then use the [development guide](docs/development.md) for frontend/backend rebuilds and database changes. Keep each change focused on one problem.

## Branches and review

Create a task branch from current `origin/main`:

```bash
git fetch origin
git switch -c feature/event-search origin/main
```

Coordinate API changes through `contracts/` and schema changes with the owning service. Stage only the files belonging to the change. Open a pull request targeting `main`, describe the resulting behavior and validation, and include migration/configuration steps when needed. Use the [pull request template](.github/pull_request_template.md); include screenshots for UI changes.

Request review from another contributor, address feedback and resolve all discussions before merging. Reviewer invitations and comments are not approvals. Avoid direct pushes to `main` and force pushes to shared history.

Use **Squash and merge** for short-lived task branches, then start the next change from updated `origin/main`. Existing persistent working branches should use merge commits where allowed, retain their branch after merge and merge `origin/main` back before the next task. Repeated squash merges into the same persistent branch make ancestry harder to manage. If only squash merges are available, use separate task branches for pull requests.

## Validation

Run the checks relevant to the change:

```bash
mvn verify
npm --prefix apps/web run lint
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
```

Database and service integration changes also need the applicable acceptance checks in a disposable Compose environment. Some scripts restart services or inject failures. See [CI operations](docs/ci.md) for environment setup and entry points. Documentation-only changes need link and example checks rather than rebuilding the application.

The six quality checks are:

- `Lint`
- `Backend · Unit Tests & Build`
- `Frontend · Tests & Build`
- `Backend · Integration Tests`
- `Security · SAST, Dependencies & Secrets`
- `Images · Scan, Smoke Test & Publish`

CI runs on pushes to `main`, pull requests targeting `main` and manual dispatch. A branch push without an open pull request does not trigger automatic CI. Only eligible main runs publish images and deploy staging. Notifications report results and are not merge gates.

Repository protection must be configured separately to require pull requests, another contributor's approval, renewed approval after updates, resolved discussions and the six checks above. This document does not establish that those settings are enabled.

## API, data and credentials

Update OpenAPI documents and callers when changing APIs. Add new Flyway migrations under the owning service; do not rewrite migrations already applied in shared environments. Verify both fresh initialization and an existing-data upgrade where applicable. Keep foreign keys and queries within the owning schema and use service APIs across boundaries.

Do not commit `.env`, `.secrets/`, database dumps, connection exports or private test datasets. Each developer uses their own local database and credentials. Record release-specific validation under `docs/evidence/`; current behavior belongs in the corresponding feature or operations guide.
