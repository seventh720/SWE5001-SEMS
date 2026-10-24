#!/usr/bin/env python3
"""Deploy the release to the existing EC2 K3s server via AWS SSM Run Command."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time

from k3s_release import validate_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--instance-id', required=True)
    parser.add_argument('--region', default='ap-southeast-1')
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--release', type=Path)
    choice.add_argument('--rollback', help='Release ID whose verified predecessor is to be restored')
    parser.add_argument('--database-compatible', action='store_true')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    release = json.loads(args.release.read_text()) if args.release else {
        'operation': 'rollback', 'releaseId': args.rollback,
        'databaseCompatibilityConfirmed': args.database_compatible}
    validate_release(release)
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as archive:
        for name in ('deploy-k3s.py', 'k3s_release.py'):
            archive.add(Path(__file__).with_name(name), arcname=name)
        raw = json.dumps(release, separators=(',', ':')).encode()
        info = tarfile.TarInfo('release.json'); info.size = len(raw); info.mode = 0o600
        archive.addfile(info, io.BytesIO(raw))
    packed = data.getvalue()
    encoded = base64.b64encode(packed).decode()
    if len(encoded) > 50000:
        raise ValueError('Release exceeds the bounded SSM inline bundle size')
    checksum = hashlib.sha256(packed).hexdigest()
    script = '\n'.join([
        'set -eu', 'umask 077', 'install -d -m 700 /var/lib/sems-cd',
        'work=$(mktemp -d /var/lib/sems-cd/incoming.XXXXXX)',
        'trap \'rm -rf "$work"\' EXIT',
        'base64 --decode > "$work/bundle.tar.gz" <<\'SEMS_RELEASE_BUNDLE\'', encoded,
        'SEMS_RELEASE_BUNDLE',
        f'printf "%s  %s\\n" "{checksum}" "$work/bundle.tar.gz" | sha256sum --check --status',
        'tar --no-same-owner -xzf "$work/bundle.tar.gz" -C "$work"',
        'python3 "$work/deploy-k3s.py" --release "$work/release.json"',
    ])
    request = {'DocumentName': 'AWS-RunShellScript', 'InstanceIds': [args.instance_id],
               'Comment': 'SEMS K3s ' + release['operation'] + ' ' + release['releaseId'],
               'TimeoutSeconds': 120, 'Parameters': {'commands': [script], 'executionTimeout': ['1200']}}
    aws = ['aws', '--region', args.region, '--output', 'json']

    def call(arguments):
        result = subprocess.run(aws + arguments, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout)

    with tempfile.TemporaryDirectory(prefix='sems-ssm-') as temp:
        path = Path(temp) / 'request.json'
        path.write_text(json.dumps(request))
        os.chmod(path, 0o600)
        command = call(['ssm', 'send-command', '--cli-input-json', 'file://' + str(path)])['Command']
    command_id = command['CommandId']
    print('SSM command: ' + command_id, flush=True)
    deadline = time.monotonic() + 1300
    while time.monotonic() < deadline:
        try:
            result = call(['ssm', 'get-command-invocation', '--command-id', command_id, '--instance-id', args.instance_id])
        except RuntimeError as error:
            if 'InvocationDoesNotExist' not in str(error):
                raise
            time.sleep(3)
            continue
        if result['Status'] in ('Pending', 'InProgress', 'Delayed'):
            time.sleep(5)
            continue
        report = {key: result.get(key) for key in (
            'CommandId', 'InstanceId', 'Status', 'ResponseCode', 'ExecutionStartDateTime',
            'ExecutionEndDateTime', 'StandardOutputContent', 'StandardErrorContent')}
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
        print(result.get('StandardOutputContent', ''), flush=True)
        if result['Status'] != 'Success' or result['ResponseCode'] != 0:
            raise RuntimeError('SSM deployment failed: ' + result['Status'] + '; see report')
        return
    raise TimeoutError('SSM deployment exceeded its execution window; inspect command before retrying')


if __name__ == '__main__':
    main()
