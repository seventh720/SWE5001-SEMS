# Lightsail staging

Host: `swe5001.seventh720.com`, DNS-only A record to the instance's attached static IPv4. The Singapore Lightsail instance runs Ubuntu 24.04 with 2 vCPU and 4 GB RAM. This is a single-host staging deployment, not a high-availability setup.

## Deploy

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

Remaining work: automated image publication/deployment, security gates, off-host scheduled backups, real-device camera checks, and cloud load/recovery measurements. Existing fault-injection acceptance scripts are intended for disposable stacks, not this shared staging instance.

## Navicat access

Connect to PostgreSQL at 127.0.0.1:5432, database sems, using sems_viewer. Enable Navicat's SSH tunnel to ubuntu@18.139.212.35:22 with the local Lightsail private key (no passphrase). The generated database password is stored only in the ignored local `.secrets/cloud-staging/navicat.json`. This role has schema usage and SELECT on the identity, catalog and admission tables, with default SELECT grants for future tables created by each service role. It has no data modification privileges. Do not open port 5432 in the Lightsail public firewall.

The initial account creation was preceded by a database backup. Verified password authentication, denied UPDATE privilege, loopback port binding, PostgreSQL protocol through an actual SSH tunnel and all three HTTPS readiness endpoints after the database container recreation.
