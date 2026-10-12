# CI operations

## Included

`Platform CI` builds the three services with Java 21, runs Maven verification, validates Compose, builds and starts containers, then checks all three readiness endpoints through Nginx. `scripts/smoke.sh` also runs locally and accepts `SEMS_BASE_URL` when the gateway uses another address. No business tests exist yet; Maven will run them when they are added.

Container logs and test reports are retained for seven days, including failed runs. JARs are uploaded only after successful smoke checks. Containers are cleaned up after each job. CI does not deploy to a cloud environment or publish container images yet.

## Telegram

Configure repository Actions secrets `TELEGRAM_TOKEN` (bot token) and `TELEGRAM_TO` (destination chat ID). The notification contains repository, ref, commit, build result and run URL. It runs after successful or failed verification; cancelled runs, fork PRs and Dependabot PRs do not notify. Missing secrets skip sending, and delivery errors do not mask the build result. Do not place either secret value in source files.

GitHub does not provide ordinary repository secrets to fork PR workflows: [GitHub secrets documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets). Messages use the [Telegram sendMessage API](https://core.telegram.org/bots/api#sendmessage).

## Reviewing and troubleshooting

Use the `Build and smoke test` job as the required check when branch protection is configured. Branch protection is not changed by this commit. A failed readiness check should be diagnosed using the diagnostics artifact, starting with container status and startup logs. Re-run after addressing the cause.

Next delivery work: choose a cloud environment and registry, configure deployment credentials, publish versioned images, and implement deployment/rollback smoke checks. Add service contract/database tests and security gates alongside the relevant implementation. Do not describe the current workflow as completed production CD.
