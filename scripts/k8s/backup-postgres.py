#!/usr/bin/env python3
"""Export a PostgreSQL custom-format dump and password-free role definitions off-node."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess


def backup(kubeconfig, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    kubectl = ['kubectl', '--kubeconfig', str(kubeconfig), '--context', 'sems-k3s',
               '--cache-dir', '.secrets/k3s-cloud/cache', '-n', 'sems-prod']
    result = {'recordedAt': timestamp, 'context': 'sems-k3s', 'namespace': 'sems-prod',
              'database': 'sems', 'files': {},
              'rolePasswords': 'Not included; retain runtime.env separately for credential recovery'}
    commands = {
        'database': ('.dump', ['pg_dump', '-U', 'postgres', '-d', 'sems', '--format=custom']),
        'roles': ('.roles.sql', ['pg_dumpall', '-U', 'postgres', '--globals-only', '--no-role-passwords']),
    }
    for kind, (suffix, command) in commands.items():
        path = directory / ('sems-' + timestamp + suffix)
        temporary = path.with_name(path.name + '.partial')
        try:
            with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
                process = subprocess.run(kubectl + ['exec', 'postgres-0', '--'] + command,
                                         stdout=handle, stderr=subprocess.PIPE, timeout=300)
            if process.returncode:
                raise RuntimeError('PostgreSQL ' + kind + ' backup failed: ' + process.stderr.decode())
            temporary.rename(path)
        finally:
            temporary.unlink(missing_ok=True)
        with path.open('rb') as handle:
            digest = hashlib.file_digest(handle, 'sha256').hexdigest()
        result['files'][kind] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}
    path = directory / ('sems-' + timestamp + '.metadata.json')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--output-directory', required=True)
    args = parser.parse_args()
    print(json.dumps(backup(args.kubeconfig, args.output_directory), indent=2))
