#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=identity_password="$IDENTITY_DB_PASSWORD" \
  --set=catalog_password="$CATALOG_DB_PASSWORD" \
  --set=admission_password="$ADMISSION_DB_PASSWORD" <<'SQL'
REVOKE ALL ON DATABASE sems FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE ROLE identity_app LOGIN PASSWORD :'identity_password';
CREATE ROLE catalog_app LOGIN PASSWORD :'catalog_password';
CREATE ROLE admission_app LOGIN PASSWORD :'admission_password';
GRANT CONNECT ON DATABASE sems TO identity_app, catalog_app, admission_app;
CREATE SCHEMA identity AUTHORIZATION identity_app;
CREATE SCHEMA catalog AUTHORIZATION catalog_app;
CREATE SCHEMA admission AUTHORIZATION admission_app;
ALTER ROLE identity_app SET search_path = identity;
ALTER ROLE catalog_app SET search_path = catalog;
ALTER ROLE admission_app SET search_path = admission;
SQL
