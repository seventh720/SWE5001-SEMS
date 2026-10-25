#!/usr/bin/env python3
"""SSM host entry point: backup, serial application rollout, verified release pointer.

Runs on the existing K3s server. Application rollback is explicit and never
reverses database migrations. No credentials are passed in the release bundle.
"""
import argparse
import base64
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

from k3s_release import APPLICATIONS, NAMESPACE, allowed, validate_release, validate_resources

ROOT = Path('/var/lib/sems-cd')
K = ['/usr/local/bin/kubectl', '--kubeconfig', '/etc/rancher/k3s/k3s.yaml',
     '--context', 'default', '--namespace', NAMESPACE]
BASE = 'https://swe5001.seventh720.com'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def command(*args, input=None, timeout=240):
    result = subprocess.run(K + list(args), input=input, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('kubectl ' + ' '.join(args[:3]) + ': ' + result.stderr.strip())
    return result.stdout


def clean(resource):
    resource = copy.deepcopy(resource)
    resource.pop('status', None)
    metadata = resource['metadata']
    for field in ('uid', 'resourceVersion', 'generation', 'creationTimestamp', 'managedFields'):
        metadata.pop(field, None)
    metadata.get('annotations', {}).pop('kubectl.kubernetes.io/last-applied-configuration', None)
    return resource


def snapshot():
    data = json.loads(command('get', 'deployments,services,configmaps,ingresses', '-o', 'json'))
    resources = [clean(r) for r in data['items'] if allowed(r)]
    validate_resources(resources)
    return resources


def postgres_identity():
    pod = json.loads(command('get', 'pod/postgres-0', '-o', 'json'))
    pvc = json.loads(command('get', 'pvc/data-postgres-0', '-o', 'json'))
    if pvc['status']['phase'] != 'Bound':
        raise RuntimeError('Database PVC is not bound')
    return {'podUid': pod['metadata']['uid'], 'pvcUid': pvc['metadata']['uid']}


def backup(directory, name):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    items = []
    for suffix, arguments in (
        ('.dump', ['pg_dump', '-U', 'postgres', '-d', 'sems', '-Fc']),
        ('.roles.sql', ['pg_dumpall', '-U', 'postgres', '--roles-only', '--no-role-passwords']),
    ):
        path = directory / (name + suffix)
        with path.open('xb') as output:
            result = subprocess.run(K + ['exec', 'postgres-0', '--'] + arguments, stdout=output,
                                    stderr=subprocess.PIPE, timeout=120)
        if result.returncode or not path.stat().st_size:
            raise RuntimeError('Pre-deployment database export failed')
        items.append({'file': path.name, 'bytes': path.stat().st_size,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    save(directory / (name + '.json'), {'createdAt': now(), 'files': items})
    return items


def apply(resources):
    common = [r for r in resources if r['kind'] != 'Deployment']
    if common:
        command('apply', '-f', '-', input=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': common}))
    # Small nodes: avoid starting all Java replacement replicas simultaneously.
    for name in APPLICATIONS:
        resource = next(r for r in resources if r['kind'] == 'Deployment' and r['metadata']['name'] == name)
        command('apply', '-f', '-', input=json.dumps(resource))
        # Two hard-separated replicas are replaced serially. Cold pulls and the
        # Java agent run before readiness on BOTH nodes; 180s can expire while
        # a healthy second replica is still starting. Keep the host subprocess
        # timeout outside kubectl's wait budget so its diagnostic is retained.
        command('rollout', 'status', 'deployment/' + name, '--timeout=600s', timeout=630)
        print('Ready: ' + name, flush=True)


def health_up(path, raw):
    if path == '/health/gateway':
        return raw.strip() == b'ok'
    try:
        return json.loads(raw).get('status') == 'UP'
    except (ValueError, AttributeError):
        return False


def rollback_target(root, release_id):
    # Live before-snapshots can contain a failed, partially applied candidate.
    # Always select the last verified release, not that diagnostic snapshot.
    pointer = json.loads((root / 'releases' / release_id / 'before-pointer.json').read_text())
    if not pointer or pointer.get('releaseId') == 'bootstrap':
        raise RuntimeError('No verified predecessor recorded; deploy a reviewed baseline explicitly')
    directory = root / 'releases' / pointer['releaseId']
    prior = validate_release(json.loads((directory / 'release.json').read_text()))
    result = json.loads((directory / 'result.json').read_text())
    if result['status'] != 'passed' or prior['operation'] != 'deploy':
        raise RuntimeError('Rollback target is not a verified application release')
    return prior['resources'], pointer


def verify(resources):
    expected = validate_resources(resources)
    actual = json.loads(command('get', 'deployments', '-o', 'json'))['items']
    for deployment in actual:
        name = deployment['metadata']['name']
        if name not in expected:
            continue
        status = deployment['status']
        if status.get('updatedReplicas') != 2 or status.get('readyReplicas') != 2 or status.get('availableReplicas') != 2:
            raise RuntimeError(name + ': incomplete rollout')
        if deployment['spec']['template']['spec']['containers'][0]['image'] != expected[name]:
            raise RuntimeError(name + ': unexpected image after rollout')
        pods = json.loads(command('get', 'pods', '-l', 'app.kubernetes.io/name=' + name, '-o', 'json'))['items']
        live = [p for p in pods if not p['metadata'].get('deletionTimestamp')]
        if len(live) != 2 or len({p['spec']['nodeName'] for p in live}) != 2:
            raise RuntimeError(name + ': replicas are not distributed across two nodes')
    checked = []
    for path in ('/', '/health/gateway', '/health/identity', '/health/event-catalog', '/health/admission'):
        with urllib.request.urlopen(BASE + path, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError('Public HTTPS check failed')
            if path.startswith('/health/') and not health_up(path, response.read()):
                raise RuntimeError('Public service readiness failed')
        checked.append(path)
    try:
        urllib.request.urlopen(BASE + '/internal/v1/events/details', timeout=15)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise RuntimeError('Internal API boundary check failed') from None
    else:
        raise RuntimeError('Internal API unexpectedly public')
    # Read credentials locally; never print them or pass them through SSM.
    secret = json.loads(command('get', 'secret/identity-secrets', '-o', 'json'))['data']
    credentials = {field: base64.b64decode(secret[key]).decode() for field, key in (
        ('email', 'SEMS_BOOTSTRAP_ADMIN_EMAIL'), ('password', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD'))}
    request = urllib.request.Request(BASE + '/api/v1/auth/login', data=json.dumps(credentials).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(request, timeout=15) as response:
        token = json.load(response)['accessToken']
    request = urllib.request.Request(BASE + '/api/v1/auth/me', headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(request, timeout=15) as response:
        if 'ADMIN' not in json.load(response)['roles']:
            raise RuntimeError('Authenticated administrator check failed')
    return {'verifiedHttpsPaths': checked, 'internalApiStatus': 404, 'adminLoginAndJwt': True,
            'images': expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', required=True, type=Path)
    args = parser.parse_args()
    release = validate_release(json.loads(args.release.read_text()))
    os.umask(0o077)
    ROOT.mkdir(mode=0o700, exist_ok=True)
    with (ROOT / 'deploy.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current_path = ROOT / 'current.json'
        previous = json.loads(current_path.read_text()) if current_path.exists() else None
        if release['operation'] == 'rollback':
            target = ROOT / 'releases' / release['releaseId']
            resources, before_pointer = rollback_target(ROOT, release['releaseId'])
            report = {'operation': 'rollback', 'releaseId': release['releaseId'], 'startedAt': now(),
                      'restoredReleaseId': before_pointer['releaseId'],
                      'sourceCommit': before_pointer['sourceCommit']}
            backup(ROOT / 'backups', 'pre-rollback-' + release['releaseId'] + '-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
            apply(resources)
            report['verification'] = verify(resources)
            save(current_path, before_pointer)
            report.update(status='passed', completedAt=now(), databaseRestored=False)
            save(target / 'rollback.json', report)
            print(json.dumps(report), flush=True)
            return
        directory = ROOT / 'releases' / release['releaseId']
        directory.mkdir(parents=True, mode=0o700)  # A retry uses a new Actions attempt ID.
        save(directory / 'release.json', release)
        save(directory / 'before.json', snapshot())
        save(directory / 'before-pointer.json', previous)
        report = {'operation': 'deploy', 'releaseId': release['releaseId'],
                  'sourceCommit': release['sourceCommit'], 'startedAt': now(), 'status': 'running'}
        try:
            # Admission/defaulting and immutable-field checks before any update.
            command('apply', '--dry-run=server', '-f', '-', input=json.dumps(
                {'apiVersion': 'v1', 'kind': 'List', 'items': release['resources']}))
            postgres = postgres_identity()
            report['backup'] = backup(ROOT / 'backups', release['releaseId'])
            print('Pre-deployment backup complete', flush=True)
            apply(release['resources'])
            report['verification'] = verify(release['resources'])
            if postgres_identity() != postgres:
                raise RuntimeError('Application release changed the database Pod or PVC')
            report['databasePodAndPvcUnchanged'] = True
            report.update(status='passed', completedAt=now())
            save(directory / 'result.json', report)
            if previous:
                save(ROOT / 'previous.json', previous)
            save(current_path, {'releaseId': release['releaseId'], 'sourceCommit': release['sourceCommit'],
                                'verifiedAt': now()})
            print(json.dumps(report), flush=True)
        except Exception as error:
            report.update(status='failed', completedAt=now(), error=str(error))
            save(directory / 'result.json', report)
            print('Release failed; verified pointer unchanged. Backup and previous application snapshot retained.', flush=True)
            raise


if __name__ == '__main__':
    main()
