#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
sems_local_dir=${1:-.secrets/k8s-local}
sems_bootstrap_email=${2:-k8s-admin@example.invalid}
if [[ -s "$sems_local_dir/runtime.env" && -s "$sems_local_dir/jwt-private.pem" && -s "$sems_local_dir/jwt-public.pem" ]]; then
  echo 'Kept existing isolated Kubernetes credentials and keys.'
  exit 0
fi
if [[ -e "$sems_local_dir/runtime.env" || -e "$sems_local_dir/jwt-private.pem" || -e "$sems_local_dir/jwt-public.pem" ]]; then
  echo 'Incomplete Kubernetes credentials found; no existing file was overwritten.' >&2
  exit 1
fi
umask 077
mkdir -p "$sems_local_dir"
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$sems_local_dir/jwt-private.pem" 2>/dev/null
openssl pkey -in "$sems_local_dir/jwt-private.pem" -pubout -out "$sems_local_dir/jwt-public.pem" 2>/dev/null
{
  for key in ORGANIZATION_ACCESS_TOKEN CATALOG_TO_ADMISSION_TOKEN ADMISSION_TO_CATALOG_TOKEN; do
    printf '%s=%s\n' "$key" "$(openssl rand -hex 32)"
  done
  for key in POSTGRES_PASSWORD IDENTITY_DB_PASSWORD CATALOG_DB_PASSWORD ADMISSION_DB_PASSWORD; do
    printf '%s=%s\n' "$key" "$(openssl rand -hex 24)"
  done
  printf 'SEMS_BOOTSTRAP_ADMIN_EMAIL=%s\n' "$sems_bootstrap_email"
  printf 'SEMS_BOOTSTRAP_ADMIN_PASSWORD=%s\n' "$(openssl rand -hex 16)"
} > "$sems_local_dir/runtime.env"
echo "Created isolated Kubernetes credentials under $sems_local_dir/."
