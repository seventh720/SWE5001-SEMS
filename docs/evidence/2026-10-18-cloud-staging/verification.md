# First cloud staging deployment — 2026-10-18

Application source: e8dc453. Deployment overlay and Caddy configuration are additional working-tree changes in this rollout. Backend package and frontend production build completed locally; this deployment did not rerun the full regression suite or claim a new remote CI result.

Deployed to the user-created Singapore Lightsail Ubuntu instance (2 vCPU / 4 GB), with independent generated credentials and a fresh database. Public address: https://swe5001.seventh720.com. Only Caddy exposes public application ports 80/443; gateway port 18080 is loopback-only. Java services have no host port mappings. PostgreSQL was initially unpublished; the subsequent Navicat setup binds it only to 127.0.0.1:5432.

Verified from the development machine with TLS certificate verification enabled: homepage and referenced JS/CSS assets return 200; all three readiness endpoints report UP; event listing returns 200; initial administrator login succeeds; unauthenticated admin access returns 401; internal API routing returns 404. Initial Python verification lacked a local CA bundle, so the successful run explicitly used the macOS system CA bundle; TLS validation was never disabled.

Database migrations: Identity V9, Catalog V11, Admission V10. Seven containers running; PostgreSQL healthy. Observed idle memory usage is recorded in deployment-checks.txt and is not a load-test result. Created a PostgreSQL custom-format backup on the server and downloaded it to the ignored local .secrets/cloud-staging directory. Administrator credentials are in that same private directory and are excluded from evidence.

Caddy persists certificate state for automatic renewal. All services have restart policies and bounded logs. Backup automation, image registry/CD, security gates, actual phone camera tests, cloud load/scale/fault recovery experiments and browser end-to-end verification remain outstanding. This is a single-host staging environment, not production high availability.

## Database access follow-up

A backup preceded the administrator credential update and another preceded the Navicat configuration. The administrator ID and roles were preserved, the bootstrap environment was synchronized, and login with the updated credentials passed. No credentials are recorded here.

The `sems_viewer` login has CONNECT, schema USAGE, and table SELECT in the three service schemas, including default SELECT grants for future tables created by their respective service roles. Password authentication and SELECT succeeded; `has_table_privilege(..., 'UPDATE')` returned false. Compose reported `127.0.0.1:5432`. An actual temporary SSH tunnel from the development machine reached the PostgreSQL protocol endpoint, then closed. All three HTTPS readiness checks remained UP after the database container recreation. The initial `https-checks.txt` container listing predates this loopback mapping.
