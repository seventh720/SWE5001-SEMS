#!/usr/bin/env python3
"""Render service-scoped Kubernetes Secrets to stdout; never evaluate .env code."""
import argparse
import base64
import json
from pathlib import Path
import re
import sys


def read_env(path):
    values = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key):
            raise ValueError(f'Invalid environment assignment at line {number}')
        if key in values:
            raise ValueError(f'Duplicate environment key: {key}')
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        values[key] = value
    return values


def render(env_path, key_directory, namespace, include_postgres=False):
    if len(namespace) > 63 or not re.fullmatch(r'[a-z0-9](?:[-a-z0-9]*[a-z0-9])?', namespace):
        raise ValueError('Expected a Kubernetes namespace name')
    values = read_env(env_path)
    required = (
        'IDENTITY_DB_PASSWORD', 'CATALOG_DB_PASSWORD', 'ADMISSION_DB_PASSWORD',
        'ORGANIZATION_ACCESS_TOKEN', 'CATALOG_TO_ADMISSION_TOKEN', 'ADMISSION_TO_CATALOG_TOKEN',
    ) + (('POSTGRES_PASSWORD',) if include_postgres else ())
    for key in required:
        if not values.get(key):
            raise ValueError(f'Missing nonempty environment key: {key}')
    email = values.get('SEMS_BOOTSTRAP_ADMIN_EMAIL', '')
    password = values.get('SEMS_BOOTSTRAP_ADMIN_PASSWORD', '')
    if bool(email) != bool(password):
        raise ValueError('Bootstrap admin email and password must both be set or both be empty')

    def secret(name, contents):
        return {
            'apiVersion': 'v1', 'kind': 'Secret',
            'metadata': {'name': name, 'namespace': namespace},
            'type': 'Opaque',
            'data': {key: base64.b64encode(value).decode('ascii') for key, value in contents.items()},
        }

    def text_secret(name, contents):
        return secret(name, {key: value.encode() for key, value in contents.items()})

    organization = {'ORGANIZATION_ACCESS_TOKEN': values['ORGANIZATION_ACCESS_TOKEN']}
    directions = {key: values[key] for key in ('CATALOG_TO_ADMISSION_TOKEN', 'ADMISSION_TO_CATALOG_TOKEN')}
    items = [
        text_secret('identity-secrets', {
            'DB_PASSWORD': values['IDENTITY_DB_PASSWORD'], **organization,
            'SEMS_BOOTSTRAP_ADMIN_EMAIL': email, 'SEMS_BOOTSTRAP_ADMIN_PASSWORD': password,
        }),
        text_secret('event-catalog-secrets', {
            'DB_PASSWORD': values['CATALOG_DB_PASSWORD'], **organization, **directions,
        }),
        text_secret('admission-secrets', {
            'DB_PASSWORD': values['ADMISSION_DB_PASSWORD'], **organization, **directions,
        }),
        secret('jwt-public', {'jwt-public.pem': (Path(key_directory) / 'jwt-public.pem').read_bytes()}),
        secret('jwt-private', {'jwt-private.pem': (Path(key_directory) / 'jwt-private.pem').read_bytes()}),
    ]
    if include_postgres:
        items.append(text_secret('postgres-secrets', {
            key: values[key] for key in (
                'POSTGRES_PASSWORD', 'IDENTITY_DB_PASSWORD', 'CATALOG_DB_PASSWORD', 'ADMISSION_DB_PASSWORD',
            )
        }))
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--key-directory', required=True)
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--include-postgres', action='store_true', help='Include self-managed PostgreSQL bootstrap credentials')
    args = parser.parse_args()
    try:
        result = render(args.env_file, args.key_directory, args.namespace, args.include_postgres)
    except (ValueError, OSError) as error:
        print(f'Cannot render Secrets: {error}', file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, indent=2)
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
