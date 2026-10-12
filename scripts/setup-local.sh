#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -e .env || -e .secrets ]]; then
  echo 'Existing .env or .secrets found; keeping configuration unchanged.' >&2
  exit 1
fi
umask 077
mkdir .secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out .secrets/jwt-private.pem 2>/dev/null
openssl pkey -in .secrets/jwt-private.pem -pubout -out .secrets/jwt-public.pem 2>/dev/null
# Containers run as a non-root UID. Only the Identity container mounts the private key.
chmod 644 .secrets/*.pem
{
  printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'IDENTITY_DB_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'CATALOG_DB_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'ADMISSION_DB_PASSWORD=%s\n' "$(openssl rand -hex 24)"
  printf 'SEMS_BOOTSTRAP_ADMIN_EMAIL=admin@example.com\n'
  printf 'SEMS_BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 16)"
} > .env
echo 'Created .env and RSA keys. Read the generated admin password from .env; do not commit it.'
