# Lightsail staging

Host: `swe5001.seventh720.com`, DNS-only A record to the instance's attached static IPv4. The Singapore Lightsail instance runs Ubuntu 24.04 with 2 vCPU and 4 GB RAM. This is a single-host staging deployment, not a high-availability setup.

## Deploy

### Continuous deployment

`CI` deploys to the GitHub `staging` environment only for main pushes or a manual run on main, after lint, backend, frontend, database/API acceptance, source/dependency security and image security pass. PRs never deploy. The JARs and web assets come from that same CI run. CI builds all seven runtime images, scans them, verifies the application image set without rebuilding, then publishes the same images. Superseded main commits are skipped; deployments are serialized and are not cancelled by newer pushes.

The latest recorded digest deployment is [main run 39751659240](https://github.com/seventh720/SWE5001-SEMS/actions/runs/39751659240) for `fb27bbf` (PR #27). Image publication and staging deployment succeeded. Capacity measurements remain tied to the earlier `f69d49d` release; they were not repeated for the UI-only follow-up. Public and internal Catalog reads use JDBC projections with live authorization and the existing response/pagination contract. See [release status](progress.md).

Environment configuration:

- Variable `STAGING_HOST`: the instance's static IPv4.
- Secret `STAGING_SSH_KEY`: dedicated staging deployment private key.
- Secret `STAGING_KNOWN_HOSTS`: independently verified SSH host-key entry, with strict host verification.
- Deployment branch policy: only main.
- GHCR package permissions: this repository must be allowed to publish/read its packages. CI uses `GITHUB_TOKEN` with packages write for publication and read for deployment; private pulls use short-lived credentials through stdin, removed from the host on exit.

The deployment key uses ubuntu with Docker sudo access. It is a privileged server credential, separate from the personal Lightsail key; its authorized-key entry disables forwarding and PTY allocation. Rotate it by installing a replacement public key, updating the environment secret, then removing the old public key.

Releases live under `/home/ubuntu/swe5001/releases/<commit>-<run-id>-<attempt>` and link to the existing root `.env` and `.secrets`. The Compose project stays `swe5001`, preserving database/certificate volumes. The updated flow requires `deployment/compose.images.json` from the same commit, pulls immutable images, backs up PostgreSQL under `backups/`, starts the release with `--no-build --pull never`, restarts the gateway to load release configuration (Docker DNS refresh handles replica changes afterward), and checks internal health. Actions then checks the public HTTPS homepage and all three services. A brief interruption is possible on this single host.

`deployed-sha`, `previous-deployed-sha`, `current` and `previous` record releases that passed host health checks; the Actions result additionally confirms public HTTPS. Failures retain the backup and release for inspection. Database migrations are not automatically reversed. Retry the failed deployment job for the current main commit, or manually run CI on main. Before rollback, check migration compatibility; redeploy compatible binaries or explicitly restore the backup during maintenance. Never delete persistent volumes.

Backups and release directories remain on the server. Monitor disk usage and copy important backups off-host before removing old files.

### Rollback with image locks

Retain the previous release directory and its `deployment/compose.images.json`; `previous` points to its exact directory, even when the same commit was rebuilt in another workflow run. Confirm schema compatibility before running that release's `scripts/cd/deploy.sh <full-commit> <registry-user>` from its release directory, with a read-packages credential supplied through stdin from a secure source. Do not put credentials in shell arguments or docs. The lock's commit must match; all seven services must use digest references. This rolls back the application image set only, not database migrations; restoration from backup is a separate maintenance action. Releases created before image locks existed need their legacy deployment procedure and separate compatibility review. A backup or digest file is not proof of a successful rollback drill.

### Historical manual bootstrap

The following build-on-host procedure describes the initial environment bootstrap. Routine updates use the CI digest flow above; do not use these commands to claim reproducible image delivery.

Build the backend JARs with `mvn package` and the frontend with `npm --prefix apps/web run build` on the development/CI machine. Upload the service Dockerfiles and JARs, web Dockerfile/nginx.conf/dist, deployment directory and setup-local.sh while preserving relative paths. Never upload the development `.env`, `.secrets`, database, or SSH private key.

The server project directory is `/home/ubuntu/swe5001`. On first installation, run `bash scripts/setup-local.sh` there, set `SEMS_DOMAIN=swe5001.seventh720.com` in `.env`, and configure the bootstrap admin email. The setup generates independent random passwords and RSA keys. Keep `.env` private. The initial email is a login identifier; it does not provision an email inbox.

Run from the server project directory:

```bash
sudo docker compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml config --quiet
sudo docker compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml up --build -d
```

The cloud overlay adds restart policies, rotating logs, service memory limits and a Caddy HTTPS entry point. Caddy automatically obtains/renews certificates, with certificate state stored in persistent volumes. Only ports 80/443 need public website access; the existing gateway remains bound to loopback port 18080. PostgreSQL is published only on 127.0.0.1:5432 for SSH-tunnel access; Java service ports are not published. Keep SSH access available for administration.

## Check and operate

```bash
curl --fail https://swe5001.seventh720.com/health/identity
curl --fail https://swe5001.seventh720.com/health/event-catalog
curl --fail https://swe5001.seventh720.com/health/admission
sudo docker compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml ps
```

Database backup (creates a private local file on the server):

```bash
umask 077
mkdir -p backups
sudo docker compose --env-file .env -p swe5001 -f deployment/compose.yaml -f deployment/compose.cloud.yaml exec -T postgres pg_dump -U postgres -d sems -Fc > "backups/sems-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Download backups to a separate machine before deleting the instance. Preserve `.env` and `.secrets` securely as well. Do not run `down -v`, which deletes the database and certificate volumes. Stop/start alone does not avoid Lightsail instance charges.

Database migrations run on service startup. Back up before updates, and check migration compatibility before rollback. Previous organization-lifecycle changes require compatible Catalog/Identity versions; do not blindly restore older binaries.

The initial read-only inspection on 2026-10-19 confirmed readiness and HTTPS for release `c0f4600`, with 1 user and no organizations, events or bookings. That is a historical snapshot, not a current data count. JWTs now use a 3600-second lifetime; the current release evidence is linked above. See [release review](archive/2026-10-19/release-review-2026-10-19.md).

Staging API and user-reported phone checks passed. The [current capacity report](evidence/2026-10-22-cloud-capacity/README.md) records only `f69d49d`: with 50 ordinary events and 1000 accounts, read 250 VU passed; mixed 250 VU passed client thresholds but failed the server gate with four internal 504s; 500 VU targets were not run; 1000 VU targets were not run. Default pool 10 and original thresholds were retained. After product cleanup, a verified server-side backup and guarded transaction purged 1000 temporary accounts, 50 events and their cancelled orders/tickets; original 24-table fingerprints and six health checks remain intact. Superseded private performance records were removed; business acceptance remains. Ten-minute steady load, independent replica scaling/recovery, compatible rollback and off-host scheduled backups remain pending. Fault injection targets disposable stacks.

## Navicat access

Connect to PostgreSQL at 127.0.0.1:5432, database sems, using sems_viewer. Enable Navicat's SSH tunnel to ubuntu@18.139.212.35:22 with the local Lightsail private key (no passphrase). The generated database password is stored only in the ignored local `.secrets/cloud-staging/navicat.json`. This role has schema usage and SELECT on the identity, catalog and admission tables, with default SELECT grants for future tables created by each service role. It has no data modification privileges. Do not open port 5432 in the Lightsail public firewall.

The initial account creation was preceded by a database backup. Verified password authentication, denied UPDATE privilege, loopback port binding, PostgreSQL protocol through an actual SSH tunnel and all three HTTPS readiness endpoints after the database container recreation.
