#!/usr/bin/env python3
"""Verify the dedicated sems-k3s PostgreSQL database without changing application data."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from environment_guard import require_disposable_namespace

from importlib.util import module_from_spec, spec_from_file_location

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig', required=True)
parser.add_argument('--report', required=True)
args = parser.parse_args()
k = ['kubectl', '--kubeconfig', args.kubeconfig, '--context', 'sems-k3s',
     '--cache-dir', '.secrets/k3s-cloud/cache', '-n', 'sems-test']
require_disposable_namespace(k)
report = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'environment': 'sems-k3s/sems-test', 'status': 'running', 'tests': []}
suffix = uuid.uuid4().hex[:12]
table = 'sems_probe_' + suffix
restore_db = 'sems_restore_' + suffix
clients = ['pg-allowed-' + suffix, 'pg-blocked-' + suffix]
log = []
step = 'database state and volume'


def run(command, timeout=60, check=True, input=None):
    result = subprocess.run(command, input=input, capture_output=True, text=True, timeout=timeout)
    log.append('$ ' + ' '.join(command) + '\n' + result.stdout + result.stderr)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def out(*command):
    return run(k + list(command)).stdout.strip()


def sql(query, database='sems'):
    return out('exec', 'postgres-0', '--', 'psql', '-v', 'ON_ERROR_STOP=1',
               '-U', 'postgres', '-d', database, '-Atq', '-c', query)


def passed(name, **details):
    report['tests'].append({'name': name, 'status': 'passed', **details})
    print('PASS ' + name, flush=True)


try:
    pod = json.loads(out('get', 'pod', 'postgres-0', '-o', 'json'))
    claim = json.loads(out('get', 'pvc', 'data-postgres-0', '-o', 'json'))
    volume = json.loads(out('get', 'pv', claim['spec']['volumeName'], '-o', 'json'))
    assert pod['spec']['nodeName'] == 'sems-k3s-worker'
    assert claim['status']['phase'] == 'Bound' and volume['spec']['persistentVolumeReclaimPolicy'] == 'Retain'
    report['databaseManifestSha256'] = hashlib.sha256(subprocess.check_output(
        ['kubectl', 'kustomize', 'deployment/k8s/overlays/k3s/postgres'])).hexdigest()
    report['imageID'] = pod['status']['containerStatuses'][0]['imageID']
    report['version'] = sql('SHOW server_version')
    assert report['version'].startswith('17.')
    report['volume'] = {'name': volume['metadata']['name'], 'claimUid': claim['metadata']['uid'],
                        'node': pod['spec']['nodeName'], 'reclaimPolicy': 'Retain',
                        'path': volume['spec'].get('hostPath', {}).get('path')}
    passed(step)

    step = 'schema ownership and authenticated application roles'
    owners = sql("SELECT nspname||':'||pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname IN ('identity','catalog','admission') ORDER BY nspname")
    assert owners.splitlines() == ['admission:admission_app', 'catalog:catalog_app', 'identity:identity_app']
    for service in ('identity', 'catalog', 'admission'):
        shell = ('PGPASSWORD="$' + service.upper() + '_DB_PASSWORD" psql -h 127.0.0.1 -U ' + service +
                 '_app -d sems -Atq -c "SELECT current_user,current_schema()"')
        assert out('exec', 'postgres-0', '--', 'sh', '-ec', shell) == service + '_app|' + service
        for other in ('identity', 'catalog', 'admission'):
            if other != service:
                assert sql(f"SELECT has_schema_privilege('{service}_app','{other}','USAGE')") == 'f'
        assert sql(f"SELECT has_schema_privilege('{service}_app','public','CREATE')") == 'f'
    rejected = run(k + ['exec', 'postgres-0', '--', 'sh', '-ec',
                       'PGPASSWORD=incorrect-test-password psql -h 127.0.0.1 -U identity_app -d sems -c "SELECT 1"'], check=False)
    assert rejected.returncode != 0 and 'password authentication failed' in rejected.stderr, 'Incorrect password was not rejected over TCP'
    passed(step, schemaOwners=owners.splitlines(), crossSchemaDenials=6, publicCreateDenials=3,
           invalidPassword='rejected')

    step = 'database network policy from another node'
    items = []
    for name, label in zip(clients, ('postgres-backup', 'postgres-untrusted-client')):
        items.append({'apiVersion': 'v1', 'kind': 'Pod',
                      'metadata': {'name': name, 'namespace': 'sems-test',
                                   'labels': {'app.kubernetes.io/name': label}},
                      'spec': {'nodeName': 'sems-k3s-server', 'automountServiceAccountToken': False,
                               'terminationGracePeriodSeconds': 1,
                               'securityContext': {'runAsNonRoot': True, 'runAsUser': 70, 'runAsGroup': 70},
                               'containers': [{'name': 'client', 'image': pod['spec']['containers'][0]['image'],
                                               'command': ['sleep', '600'],
                                               'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'},
                                                             'limits': {'cpu': '100m', 'memory': '128Mi'}},
                                               'env': [{'name': 'PGHOST', 'value': 'postgres.sems-test.svc.cluster.local'},
                                                       {'name': 'PGDATABASE', 'value': 'sems'},
                                                       {'name': 'PGUSER', 'value': 'admission_app'},
                                                       {'name': 'PGCONNECT_TIMEOUT', 'value': '3'},
                                                       {'name': 'PGPASSWORD', 'valueFrom': {'secretKeyRef':
                                                        {'name': 'admission-secrets', 'key': 'DB_PASSWORD'}}}]}]}})
    run(k + ['apply', '-f', '-'], input=json.dumps({'apiVersion': 'v1', 'kind': 'List', 'items': items}))
    for name in clients:
        run(k + ['wait', '--for=condition=Ready', 'pod/' + name, '--timeout=120s'], timeout=135)
    assert out('exec', clients[0], '--', 'psql', '-Atq', '-c', 'SELECT current_user') == 'admission_app'
    denied = run(k + ['exec', clients[1], '--', 'psql', '-Atq', '-c', 'SELECT 1'], check=False)
    assert denied.returncode != 0 and any(message in denied.stderr for message in
                                          ('timeout expired', 'Connection refused', 'No route to host')), denied.stderr
    passed(step, allowedClientNode='sems-k3s-server', databaseNode='sems-k3s-worker',
           allowedRole='admission_app', untrustedClient='connection blocked',
           denialMode='connection refused' if 'Connection refused' in denied.stderr else 'timeout or unreachable')

    step = 'data survives PostgreSQL Pod replacement'
    sql(f"SET ROLE admission_app; CREATE TABLE admission.{table}(value text NOT NULL); INSERT INTO admission.{table} VALUES ('{suffix}')")
    old_uid = pod['metadata']['uid']
    run(k + ['delete', 'pod', 'postgres-0', '--wait=true', '--timeout=90s'], timeout=105)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        result = run(k + ['get', 'pod', 'postgres-0', '-o', 'json'], check=False)
        if result.returncode == 0:
            replacement = json.loads(result.stdout)
            if replacement['metadata']['uid'] != old_uid and any(
                    c['type'] == 'Ready' and c['status'] == 'True' for c in replacement['status'].get('conditions', [])):
                break
        time.sleep(1)
    else:
        raise RuntimeError('Replacement database Pod was not ready within 180 seconds')
    assert sql(f'SELECT value FROM admission.{table}') == suffix
    after = json.loads(out('get', 'pvc', 'data-postgres-0', '-o', 'json'))
    assert after['metadata']['uid'] == claim['metadata']['uid'] and after['spec']['volumeName'] == claim['spec']['volumeName']
    assert replacement['spec']['nodeName'] == 'sems-k3s-worker'
    passed(step, oldPodUid=old_uid, newPodUid=replacement['metadata']['uid'], claimUnchanged=True,
           probeRowPreserved=True)

    step = 'off-node dump and isolated data restore'
    spec = spec_from_file_location('pg_backup', Path(__file__).with_name('backup-postgres.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    backup = module.backup(args.kubeconfig, '.secrets/k3s-cloud/backups')
    out('exec', 'postgres-0', '--', 'createdb', '-U', 'postgres', restore_db)
    with open(backup['files']['database']['path'], 'rb') as handle:
        restored = subprocess.run(k + ['exec', '-i', 'postgres-0', '--', 'pg_restore', '-U', 'postgres',
                                      '-d', restore_db, '--no-owner', '--no-privileges', '--exit-on-error'],
                                  stdin=handle, capture_output=True, timeout=120)
    assert restored.returncode == 0, restored.stderr.decode()
    assert sql(f'SELECT value FROM admission.{table}', restore_db) == suffix
    passed(step, dumpSha256=backup['files']['database']['sha256'], probeRowRestored=True,
           restoreScope='Isolated temporary database; data restore without owner/ACL replay')
    report['status'] = 'passed'
except Exception as error:
    report['status'] = 'failed'
    report['tests'].append({'name': step, 'status': 'failed', 'error': str(error)})
    print('FAIL ' + step + ': ' + str(error), flush=True)
finally:
    cleanup = []
    for command in (['exec', 'postgres-0', '--', 'dropdb', '-U', 'postgres', '--if-exists', restore_db],
                    ['exec', 'postgres-0', '--', 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'sems',
                     '-c', f'DROP TABLE IF EXISTS admission.{table}'],
                    ['delete', 'pod', *clients, '--ignore-not-found=true', '--wait=true', '--timeout=30s']):
        try:
            result = run(k + command, timeout=45, check=False)
            if result.returncode:
                cleanup.append(result.stderr.strip())
        except Exception as error:
            cleanup.append(str(error))
    report['cleanupErrors'] = cleanup
    report['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
    path.with_suffix('.txt').write_text('\n\n'.join(log) + '\n')

if report['status'] != 'passed' or report['cleanupErrors']:
    raise SystemExit(1)
