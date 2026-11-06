#!/usr/bin/env python3
"""Maintenance-window validation on existing K3s Pods, using a temporary database.

Requires explicit maintenance authorization. Existing fixture runners keep their
production guards. This runner never restores or seeds the original business DB.
Private snapshots, credentials and raw evidence stay under .performance/.
"""
import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import signal
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ('identity', 'event-catalog', 'admission', 'web', 'gateway')
BACKENDS = SERVICES[:3]
ANNOTATION = 'sems.seventh720.com/maintenance-run'
BASE = 'https://swe5001.seventh720.com'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


shared = module('local_evidence', Path(__file__).with_name('k8s-experiment.py'))


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def require_test_database(database):
    if not re.fullmatch(r'sems_validation_[a-f0-9]{12}', database):
        raise ValueError('Only a run-owned sems_validation database is allowed')


def database_urls(database):
    require_test_database(database)
    return {s.upper() + '_DB_URL': f'jdbc:postgresql://postgres:5432/{database}?currentSchema={s}'
            for s in ('identity', 'catalog', 'admission')}


def validate_active(state, namespace, config, postgres, pvc):
    require_test_database(state['testDatabase'])
    if namespace['metadata']['name'] != 'sems-prod' or namespace['metadata']['uid'] != state['namespaceUid']:
        raise ValueError('Namespace identity changed')
    if config['metadata'].get('annotations', {}).get(ANNOTATION) != state['runId']:
        raise ValueError('Maintenance run ownership is missing')
    if config['data'] != database_urls(state['testDatabase']):
        raise ValueError('Refusing tests against an original or unexpected database')
    if postgres['metadata']['uid'] != state['postgresUid'] or pvc['metadata']['uid'] != state['pvcUid']:
        raise ValueError('Original PostgreSQL Pod/PVC identity changed')


def gateway_config(original, token):
    if not re.fullmatch('[a-f0-9]{48}', token):
        raise ValueError('Invalid maintenance token')
    text = original.replace('access_log /var/log/nginx/access.log',
                            'access_log /tmp/sems-maintenance/access.jsonl')
    text = text.replace('"request_id":"$request_id"',
                        '"request_id":"$request_id","server_port":$server_port,'
                        '"upstream_status":"$upstream_status","benchmark_run":"$http_x_benchmark_run",'
                        '"benchmark_phase":"$http_x_benchmark_phase"')
    text = text.replace('http {', 'http {\n'
        '    map "$request_method:$http_x_sems_maintenance_token" $sems_maintenance_allowed {\n'
        '        default 0;\n        ~^(GET|HEAD|OPTIONS): 1;\n'
        f'        ~^[A-Z]+:{token}$ 1;\n    }}', 1)
    return text.replace('listen 80;', 'listen 80;\n'
                        '        if ($sems_maintenance_allowed = 0) { return 503; }', 1)


def business_traffic_counts(text, service):
    if service != 'identity':
        return shared.traffic_counts(text, 'catalog' if service == 'event-catalog' else 'booking')
    counts = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[:2] == ['GET', '/api/v1/auth/me'] and fields[2].isdigit():
            counts[fields[2]] = counts.get(fields[2], 0) + 1
    return counts


class Maintenance:
    def __init__(self, args):
        self.args = args
        self.out = Path(args.output).resolve()
        if not self.out.is_relative_to(ROOT / '.performance') or not self.out.is_dir():
            raise ValueError('Use a private .performance directory with an original-backup/')
        self.kube = ['kubectl', '--kubeconfig', str(self.out / 'kubeconfig'), '--context', 'sems-k3s',
                     '--cache-dir', '/private/tmp/sems-cloud-kube-cache', '-n', 'sems-prod']
        self.ssh = ['ssh', '-T', '-i', str(ROOT / '.secrets/k3s-cloud/ssh.pem'),
                    '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'UserKnownHostsFile="' + str(ROOT / '.secrets/k3s-cloud/known_hosts') + '"',
                    '-o', 'ConnectTimeout=10', '-o', 'ServerAliveInterval=10', 'ubuntu@18.141.228.205']
        self.state = json.loads((self.out / 'state.json').read_text()) if (self.out / 'state.json').exists() else None
        self.active = None
        self.load_name = 'sems-cloud-validation-' + str(os.getpid())
        self.lock = None
        self.started = time.monotonic()
        self.ssl = ssl.create_default_context()

    def command(self, args, timeout=120, **kwargs):
        result = subprocess.run(args, cwd=ROOT, timeout=timeout, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, **kwargs)
        if result.returncode:
            message = result.stderr.decode(errors='replace')
            if self.state:
                message = message.replace(self.state.get('maintenanceToken', '__none__'), '[redacted]')
            raise RuntimeError(args[0] + ' failed: ' + message[-1500:])
        return result.stdout

    def k(self, *args, **kwargs):
        return self.command(self.kube + list(args), **kwargs)

    def j(self, *args):
        return json.loads(self.k(*args, '-o', 'json'))

    def sql(self, query, database='postgres'):
        return self.k('exec', '-i', 'postgres-0', '--', 'psql', '-U', 'postgres', '-d', database,
                      '-v', 'ON_ERROR_STOP=1', '-Atq', input=query.encode(), timeout=120)

    def patch(self, kind, name, operations):
        self.k('patch', kind, name, '--type=json', '-p', json.dumps(operations))

    def state_save(self):
        save(self.out / 'state.json', self.state)

    def fingerprint(self):
        tables = self.sql("SELECT table_schema||'.'||table_name FROM information_schema.tables "
                          "WHERE table_schema IN ('identity','catalog','admission') "
                          "AND table_type='BASE TABLE' ORDER BY 1", 'sems').decode().splitlines()
        result = {}
        for table in tables:
            if not re.fullmatch(r'(identity|catalog|admission)\.[a-z_0-9]+', table):
                raise ValueError('Unexpected original table name')
            data = self.sql('COPY ' + table + ' TO STDOUT', 'sems').splitlines()
            result[table] = {'rows': len(data), 'sha256': hashlib.sha256(b'\n'.join(sorted(data))).hexdigest()}
        return result

    def capture(self):
        if self.state:
            raise ValueError('Snapshot exists; do not overwrite an original state')
        deployments = {s: self.j('get', 'deployment', s) for s in SERVICES}
        gateway_name = next(v['configMap']['name'] for v in deployments['gateway']['spec']['template']['spec']['volumes']
                            if v['name'] == 'config')
        configs = {name: self.j('get', 'configmap', name) for name in ('sems-database', gateway_name)}
        expected = {s.upper() + '_DB_URL': f'jdbc:postgresql://postgres:5432/sems?currentSchema={s}'
                    for s in ('identity', 'catalog', 'admission')}
        if configs['sems-database']['data'] != expected:
            raise ValueError('Original DB configuration is not the expected production baseline')
        run = secrets.token_hex(6)
        self.state = {'runId': run, 'capturedAt': now(), 'testDatabase': 'sems_validation_' + run,
                      'maintenanceToken': secrets.token_hex(24), 'deployments': deployments,
                      'configmaps': configs, 'gatewayConfigName': gateway_name,
                      'namespaceUid': self.j('get', 'namespace', 'sems-prod')['metadata']['uid'],
                      'postgresUid': self.j('get', 'pod', 'postgres-0')['metadata']['uid'],
                      'pvcUid': self.j('get', 'pvc', 'data-postgres-0')['metadata']['uid'],
                      'originalReplicas': {s: d['spec']['replicas'] for s, d in deployments.items()},
                      'originalPods': self.j('get', 'pods')['items'],
                      'nodes': [n['metadata']['name'] for n in self.j('get', 'nodes')['items']],
                      'originalFingerprint': self.fingerprint(), 'trials': [], 'phase': 'captured'}
        if sorted(self.state['nodes']) != ['sems-k3s-server', 'sems-k3s-worker']:
            raise ValueError('Unexpected cluster nodes')
        backup = next((self.out / 'original-backup').glob('*.dump'))
        listing = self.k('exec', '-i', 'postgres-0', '--', 'pg_restore', '--list', input=backup.read_bytes())
        if b' TABLE ' not in listing:
            raise ValueError('Original backup cannot be listed')
        self.state['originalBackupVerified'] = {'bytes': backup.stat().st_size,
                                               'sha256': hashlib.sha256(backup.read_bytes()).hexdigest()}
        self.state_save()
        print(now(), 'Captured original deployment and', len(self.state['originalFingerprint']), 'table fingerprints', flush=True)

    def guard(self):
        validate_active(self.state, self.j('get', 'namespace', 'sems-prod'),
                        self.j('get', 'configmap', 'sems-database'),
                        self.j('get', 'pod', 'postgres-0'), self.j('get', 'pvc', 'data-postgres-0'))

    def runtime_guard(self, expected=None):
        expected = expected or database_urls(self.state['testDatabase'])
        seen = set()
        for pod in self.pods():
            service = pod['metadata'].get('labels', {}).get('app.kubernetes.io/name')
            if service not in BACKENDS or pod['metadata'].get('deletionTimestamp'):
                continue
            schema = 'catalog' if service == 'event-catalog' else service
            value = self.k('exec', pod['metadata']['name'], '-c', service, '--', 'printenv', 'DB_URL').decode().strip()
            if value != expected[schema.upper() + '_DB_URL']:
                raise ValueError('Running backend database URL differs: ' + pod['metadata']['name'])
            seen.add(service)
        if seen != set(BACKENDS):
            raise ValueError('All three running backend services must be verified')

    def scale(self, counts):
        for service, count in counts.items():
            self.k('scale', 'deployment/' + service, '--replicas=' + str(count))

    def pods(self):
        return self.j('get', 'pods')['items']

    def ready(self, counts):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            pods = self.pods()
            valid = True
            for service, count in counts.items():
                selected = [p for p in pods if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == service]
                valid = valid and len(selected) == count and all(not p['metadata'].get('deletionTimestamp') and
                    any(c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', []))
                    for p in selected)
            if valid:
                return pods
            time.sleep(2)
        raise RuntimeError('Replica readiness timed out')

    def acquire_lock(self):
        self.lock = subprocess.Popen(self.ssh + ['sudo -n flock -n /var/lib/sems-cd/deploy.lock '
                                    "sh -c 'echo LOCKED; cat >/dev/null'"],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=ROOT)
        if self.lock.stdout.readline().strip() != b'LOCKED':
            raise RuntimeError('Could not acquire the existing deployment lock: '
                               + self.lock.stderr.read().decode(errors='replace')[-1000:])

    def watchdog(self):
        directory = '/var/lib/sems-maintenance/' + self.state['runId']
        recovery = {'deployments': self.state['deployments'], 'configmaps': self.state['configmaps'],
                    'gatewayConfigName': self.state['gatewayConfigName']}
        program = '''import json,subprocess,time
from pathlib import Path
p=Path(__file__).parent
s=json.loads((p/'original.json').read_text())
k=['k3s','kubectl','-n','sems-prod']
def call(args): subprocess.run(k+args,check=True,timeout=630)
for name in ('identity','event-catalog','admission'):call(['scale','deployment/'+name,'--replicas=0'])
time.sleep(25)
for name,cm in s['configmaps'].items():
 if name==s['gatewayConfigName']:continue
 call(['patch','configmap',name,'--type=json','-p',json.dumps([{'op':'replace','path':'/data','value':cm['data']},{'op':'add','path':'/metadata/annotations','value':cm['metadata'].get('annotations',{})}])])
for name,d in s['deployments'].items():
 if name=='gateway':continue
 call(['patch','deployment',name,'--type=json','-p',json.dumps([{'op':'replace','path':'/spec','value':d['spec']}])])
for name in ('identity','event-catalog','admission','web'):call(['rollout','status','deployment/'+name,'--timeout=600s'])
name=s['gatewayConfigName'];cm=s['configmaps'][name]
call(['patch','configmap',name,'--type=json','-p',json.dumps([{'op':'replace','path':'/data','value':cm['data']}])])
call(['patch','deployment','gateway','--type=json','-p',json.dumps([{'op':'replace','path':'/spec','value':s['deployments']['gateway']['spec']}])])
call(['rollout','status','deployment/gateway','--timeout=600s'])
(p/'restored.json').write_text(json.dumps({'status':'restored','at':time.time()}))
'''
        self.command(self.ssh + ['sudo -n mkdir -p ' + directory + '; sudo -n chmod 700 ' + directory])
        for name, data in [('original.json', json.dumps(recovery).encode()), ('restore.py', program.encode())]:
            self.command(self.ssh + ['sudo -n tee ' + directory + '/' + name + ' >/dev/null; sudo -n chmod 600 '
                                     + directory + '/' + name], input=data)
        self.command(self.ssh + ['sudo -n systemd-run --unit=sems-maintenance-' + self.state['runId']
                     + ' --on-active=6h /usr/bin/python3 ' + directory + '/restore.py'])
        self.state['watchdogDirectory'] = directory
        self.state['watchdogMaximumHours'] = 6
        self.state_save()

    def prepare(self):
        self.watchdog()
        self.state['phase'] = 'maintenance-starting'
        self.state_save()
        gateway_name = self.state['gatewayConfigName']
        data = copy.deepcopy(self.state['configmaps'][gateway_name]['data'])
        data['nginx.conf'] = gateway_config(data['nginx.conf'], self.state['maintenanceToken'])
        self.patch('configmap', gateway_name, [{'op': 'replace', 'path': '/data', 'value': data}])
        spec = copy.deepcopy(self.state['deployments']['gateway']['spec'])
        container = spec['template']['spec']['containers'][0]
        container['command'] = ['/bin/sh', '-ec', 'mkdir -p /tmp/sems-maintenance; exec /bin/sh '
                                '/config/kubernetes-entrypoint.sh -e /tmp/sems-maintenance/error.log -g "daemon off;"']
        container['args'] = []
        spec['template']['metadata'].setdefault('annotations', {})[ANNOTATION] = self.state['runId']
        self.patch('deployment', 'gateway', [{'op': 'replace', 'path': '/spec', 'value': spec}])
        self.k('rollout', 'status', 'deployment/gateway', '--timeout=600s', timeout=630)
        self.scale(dict.fromkeys(BACKENDS, 0))
        self.ready(dict.fromkeys(BACKENDS, 0))
        if self.fingerprint() != self.state['originalFingerprint']:
            raise RuntimeError('Original data changed after capture; retain backups and restore service')
        database = self.state['testDatabase']
        require_test_database(database)
        self.sql('CREATE DATABASE ' + database)
        self.sql('REVOKE ALL ON DATABASE ' + database + ' FROM PUBLIC; '
                 'REVOKE ALL ON SCHEMA public FROM PUBLIC; '
                 'GRANT CONNECT ON DATABASE ' + database + ' TO identity_app,catalog_app,admission_app; '
                 'CREATE SCHEMA identity AUTHORIZATION identity_app; '
                 'CREATE SCHEMA catalog AUTHORIZATION catalog_app; '
                 'CREATE SCHEMA admission AUTHORIZATION admission_app;', database)
        cm = self.state['configmaps']['sems-database']
        annotations = {**cm['metadata'].get('annotations', {}), ANNOTATION: self.state['runId']}
        self.patch('configmap', 'sems-database', [{'op': 'replace', 'path': '/data', 'value': database_urls(database)},
                   {'op': 'add', 'path': '/metadata/annotations', 'value': annotations}])
        for name in BACKENDS:
            spec = copy.deepcopy(self.state['deployments'][name]['spec'])
            spec['template']['metadata'].setdefault('annotations', {})[ANNOTATION] = self.state['runId']
            env = spec['template']['spec']['containers'][0].setdefault('env', [])
            values = {'SERVER_TOMCAT_ACCESSLOG_ENABLED': 'true', 'SERVER_TOMCAT_ACCESSLOG_DIRECTORY': '/tmp/sems-access',
                      'SERVER_TOMCAT_ACCESSLOG_BUFFERED': 'false', 'SERVER_TOMCAT_ACCESSLOG_PATTERN': '%m %U %s %D'}
            env[:] = [e for e in env if e['name'] not in values] + [{'name': k, 'value': v} for k, v in values.items()]
            self.patch('deployment', name, [{'op': 'replace', 'path': '/spec', 'value': spec}])
        self.ready(self.state['originalReplicas'])
        self.guard()
        self.runtime_guard()
        self.state['phase'] = 'test-database-ready'
        self.state_save()
        print(now(), 'Temporary test database ready; original database retained', flush=True)

    def seed(self):
        renderer = shared.secret_renderer
        env = renderer.read_env(ROOT / '.secrets/k3s-cloud/runtime.env')
        values = {k: env[k] for k in ('SEMS_BOOTSTRAP_ADMIN_EMAIL', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD')}
        self.state['phase'] = 'seeding'; self.state_save()
        with (self.out / 'seed.log').open('w') as log, (self.out / 'seed-resources.jsonl').open('w') as samples:
            process = subprocess.Popen([sys.executable, str(Path(__file__).with_name('seed.py')), '--base-url', BASE,
                      '--output', str(self.out / 'dataset.json'), '--users', '1000', '--events', '100', '--quota', '1000000'],
                     env={**os.environ, **values, 'SEMS_MAINTENANCE_TOKEN': self.state['maintenanceToken']},
                     stdout=log, stderr=subprocess.STDOUT)
            deadline, previous = time.monotonic() + 3600, None
            try:
                while process.poll() is None:
                    sample = self.sample(); samples.write(json.dumps(sample) + '\n'); samples.flush()
                    shared.check_sample_continuity(previous, sample['time']); previous = sample['time']
                    self.resources_ok(sample)
                    if time.monotonic() > deadline:
                        raise RuntimeError('Fixture preparation exceeded one hour')
                    time.sleep(5)
                if process.returncode:
                    raise RuntimeError('Fixture preparation failed; see private seed.log')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=10)
        with (self.out / 'baseline.dump').open('wb') as stream:
            stream.write(self.k('exec', 'postgres-0', '--', 'pg_dump', '-U', 'postgres', '-d', self.state['testDatabase'], '-Fc'))
        self.state['baselineSha256'] = hashlib.sha256((self.out / 'baseline.dump').read_bytes()).hexdigest()
        self.state['phase'] = 'seeded'
        self.state_save()
        print(now(), 'Seeded 1000 accounts and 100 events; baseline snapshot saved', flush=True)

    def api(self, method, path, body=None, token=None):
        headers = {'Content-Type': 'application/json', 'X-SEMS-Maintenance-Token': self.state['maintenanceToken']}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(BASE + path, method=method, headers=headers,
                    data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(request, context=self.ssl, timeout=15) as response:
            return json.load(response)

    def refresh(self, vus):
        data = json.loads((self.out / 'dataset.json').read_text())
        for user in data['users'][:vus]:
            for attempt in range(6):
                try:
                    user['token'] = self.api('POST', '/api/v1/auth/login',
                        {'email': user['email'], 'password': data['password']})['accessToken']
                    break
                except urllib.error.HTTPError as error:
                    if error.code != 429 or attempt == 5:
                        raise
                    time.sleep(5)
            time.sleep(.3)
        data['tokensRefreshedAt'] = now()
        save(self.out / 'dataset.json', data)

    def sample(self):
        result = {'time': now(), 'nodes': [], 'pods': []}
        for node in self.state['nodes']:
            stats = json.loads(self.k('get', '--raw', '/api/v1/nodes/' + node + '/proxy/stats/summary'))
            result['nodes'].append({k: stats['node'].get(k) for k in ('nodeName', 'cpu', 'memory', 'fs')})
            result['pods'] += [p for p in stats['pods'] if p['podRef']['namespace'] == 'sems-prod']
        return result

    def database_sample(self):
        query = """SELECT json_build_object('time',clock_timestamp(),
          'activity',(SELECT coalesce(json_agg(json_build_object('role',usename,'state',state,
            'waitType',wait_event_type,'waitEvent',wait_event,'blockers',pg_blocking_pids(pid))),'[]'::json)
            FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),
          'database',(SELECT row_to_json(x) FROM (SELECT xact_commit,xact_rollback,blks_read,blks_hit,
            tup_inserted,tup_updated,tup_deleted,temp_bytes,deadlocks,stats_reset
            FROM pg_stat_database WHERE datname=current_database()) x))"""
        return json.loads(self.sql(query, self.state['testDatabase']))

    def resources_ok(self, sample):
        if time.monotonic() - self.started > 5 * 3600:
            raise RuntimeError('Five-hour local deadline reached; restore before the remote watchdog')
        for node in sample['nodes']:
            if node['memory'].get('availableBytes', 0) < 512 * 1024**2:
                raise RuntimeError('Resource stop: node available memory below 512MiB')
            fs = node.get('fs') or {}
            if fs.get('capacityBytes') and (fs['availableBytes'] < 2 * 1024**3 or fs['availableBytes'] / fs['capacityBytes'] < .1):
                raise RuntimeError('Resource stop: node disk below 2GiB or 10%')

    def reset(self, counts):
        self.guard()
        self.scale(dict.fromkeys(BACKENDS, 0))
        self.ready(dict.fromkeys(BACKENDS, 0))
        self.k('exec', '-i', 'postgres-0', '--', 'pg_restore', '-U', 'postgres', '-d', self.state['testDatabase'],
               '--clean', '--if-exists', '--exit-on-error', input=(self.out / 'baseline.dump').read_bytes(), timeout=300)
        self.scale(counts)
        self.ready(counts)
        time.sleep(7)
        self.runtime_guard()

    def stop_load(self):
        if self.active and self.active.poll() is None:
            subprocess.run(['docker', 'stop', '-t', '3', self.load_name], capture_output=True, timeout=20)
            self.active.wait(timeout=15)
        self.active = None

    def trial(self, name, mode, vus, replicas=None, duration=600, warmup=60):
        target = self.out / name
        target.mkdir()
        counts = {s: 2 if mode == 'mixed' else 1 for s in BACKENDS}
        tested = 'event-catalog' if mode == 'catalog' else 'admission'
        if replicas is not None:
            counts[tested] = replicas
        print(now(), 'Preparing', name, flush=True)
        self.reset(counts)
        self.refresh(vus)
        self.guard()
        pods = self.pods()
        mapping = shared.Experiment.pod_map(self, pods)
        save(target / 'pods.json', mapping)
        gateways = [p['metadata']['name'] for p in pods if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == 'gateway']
        for pod in gateways:
            self.k('exec', pod, '--', 'sh', '-ec', ': > /tmp/sems-maintenance/access.jsonl; : > /tmp/sems-maintenance/error.log')
        run = self.state['runId'] + '-' + name
        values = {'DATASET': '/input/dataset.json', 'BASE_URL': BASE, 'MODE': mode, 'VUS': str(vus),
                  'RUN_ID': run, 'SEMS_MAINTENANCE_TOKEN': self.state['maintenanceToken'],
                  'WARMUP_SECONDS': str(warmup), 'DURATION_SECONDS': str(duration), 'THINK_SECONDS': '.1',
                  'HOLD': str(duration) + 's', 'RAMP_SECONDS': str(warmup), 'MAX_WRITES_PER_VU': '0',
                  'SUMMARY_FILE': '/out/summary.json', 'COMMIT': '5e9081a9f5421fa5bdbd965d750641f3666dd5f3',
                  'POSTGRES_CPU_LIMIT': '1', 'REPLICAS': '-'.join(s + str(counts[s]) for s in BACKENDS)}
        script = 'cloud-capacity.js' if mode == 'mixed' else 'load.js'
        command = ['docker', 'run', '--rm', '--pull', 'never', '--name', self.load_name, '--cpus=2', '--memory=1g',
                   '-v', str(Path(__file__).parent) + ':/src:ro', '-v', str(self.out / 'dataset.json') + ':/input/dataset.json:ro',
                   '-v', str(target) + ':/out']
        for key, value in values.items():
            command += ['-e', key + '=' + value]
        command += ['grafana/k6:1.3.0', 'run', '--quiet', '--out', 'json=/out/raw.json']
        if mode == 'mixed':
            command += ['--summary-export', '/out/summary.json']
        command += ['/src/' + script]
        self.resources_ok(self.sample())
        error, code, previous = None, None, None
        print(now(), 'Running', name, flush=True)
        try:
            with (target / 'load.log').open('w') as log, (target / 'resources.jsonl').open('w') as samples, \
                    (target / 'database.jsonl').open('w') as database, (target / 'generator.jsonl').open('w') as generator:
                self.active = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + warmup + duration + 120
                while self.active.poll() is None:
                    sample = self.sample()
                    samples.write(json.dumps(sample) + '\n'); samples.flush()
                    shared.check_sample_continuity(previous, sample['time']); previous = sample['time']
                    self.resources_ok(sample)
                    database.write(json.dumps(self.database_sample()) + '\n'); database.flush()
                    stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', self.load_name],
                                           capture_output=True, text=True, timeout=15)
                    if stats.returncode == 0 and stats.stdout.strip():
                        generator.write(json.dumps({'time': now(), 'stats': json.loads(stats.stdout)}) + '\n'); generator.flush()
                    if shared.Experiment.pod_map(self, self.pods()) != mapping:
                        raise RuntimeError('Unexpected Pod identity, restart, image or resource change')
                    if time.monotonic() > deadline:
                        raise RuntimeError('Load deadline exceeded')
                    time.sleep(5)
                code = self.active.returncode
        except BaseException as failure:
            error = str(failure)
        finally:
            self.stop_load()
        with (target / 'gateway.jsonl').open('wb') as stream:
            for pod in gateways:
                stream.write(self.k('exec', pod, '--', 'cat', '/tmp/sems-maintenance/access.jsonl', timeout=180))
        with (target / 'gateway-error.log').open('wb') as stream:
            for pod in gateways:
                stream.write(self.k('exec', pod, '--', 'cat', '/tmp/sems-maintenance/error.log'))
        summary = json.loads((target / 'summary.json').read_text()) if (target / 'summary.json').exists() else None
        metrics = summary['metrics'] if summary else {}
        count_key = 'http_reqs{phase:hold}' if mode == 'mixed' else 'unexpected_error_rate{scenario:measurement}'
        counter = metrics.get(count_key, {})
        expected = counter.get('count', 0) if mode == 'mixed' else sum(counter.get('values', {}).get(k, 0) for k in ('passes', 'fails'))
        with (target / 'gateway.jsonl').open() as stream:
            evidence = shared.gateway_evidence(stream, run, expected)
        save(target / 'gateway-evidence.json', evidence)
        data = json.loads((self.out / 'dataset.json').read_text())
        rows = json.loads(self.sql(shared.inventory_query(data), self.state['testDatabase']))
        audit = {'passed': shared.inventory_passed(rows, len(data['events'])), 'inventory': rows}
        save(target / 'inventory.json', audit)
        traffic = {}
        for pod, info in mapping.items():
            if info['service'] in (BACKENDS if mode == 'mixed' else (tested,)):
                raw = self.k('exec', pod, '--', 'sh', '-c', 'cat /tmp/sems-access/* 2>/dev/null').decode()
                traffic[pod] = business_traffic_counts(raw, info['service'])
        save(target / 'traffic.json', traffic)
        result = {'name': name, 'mode': mode, 'vus': vus, 'counts': counts, 'duration': duration, 'warmup': warmup,
                  'loadExitCode': code, 'error': error, 'inventoryPassed': audit['passed'],
                  'gatewayCoveragePassed': evidence['measurementCoveragePassed'], 'serverGatePassed': evidence['serverGatePassed'],
                  'eachReplicaServed': len(traffic) == (sum(counts.values()) if mode == 'mixed' else replicas) and all(sum(x.values()) > 0 for x in traffic.values())}
        result['passed'] = code == 0 and error is None and all(result[k] for k in
            ('inventoryPassed', 'gatewayCoveragePassed', 'serverGatePassed', 'eachReplicaServed'))
        save(target / 'result.json', result)
        self.state['trials'].append(result); self.state_save()
        print(now(), 'Completed', json.dumps(result), flush=True)
        if not result['passed']:
            raise RuntimeError('Trial did not pass; no higher load scheduled: ' + name)

    def restore(self):
        print(now(), 'Restoring original database connections and deployments', flush=True)
        self.stop_load()
        if self.state.get('phase') in ('captured', 'restored'):
            return
        self.command(self.ssh + ['sudo -n /usr/bin/python3 ' + self.state['watchdogDirectory'] + '/restore.py'], timeout=2400)
        self.ready(self.state['originalReplicas'])
        self.runtime_guard(self.state['configmaps']['sems-database']['data'])
        fingerprint = self.fingerprint()
        same = fingerprint == self.state['originalFingerprint']
        self.state['restoration'] = {'at': now(), 'originalTableFingerprintsMatch': same,
                                    'tables': len(fingerprint), 'originalReplicasReady': True,
                                    'databaseConnectionConfigRestored': self.j('get', 'configmap', 'sems-database')['data'] == self.state['configmaps']['sems-database']['data'],
                                    'databasePodAndPvcUnchanged': self.j('get', 'pod', 'postgres-0')['metadata']['uid'] == self.state['postgresUid'] and self.j('get', 'pvc', 'data-postgres-0')['metadata']['uid'] == self.state['pvcUid']}
        self.state['phase'] = 'restored'; self.state_save()
        if not same:
            raise RuntimeError('Original data fingerprint differs; original backups retained for investigation')
        self.command(self.ssh + ['sudo -n systemctl stop sems-maintenance-' + self.state['runId'] + '.timer'])
        require_test_database(self.state['testDatabase'])
        exists = self.sql("SELECT 1 FROM pg_database WHERE datname='" + self.state['testDatabase'] + "'").strip() == b'1'
        if exists:
            with (self.out / 'final-test-database.dump').open('wb') as stream:
                stream.write(self.k('exec', 'postgres-0', '--', 'pg_dump', '-U', 'postgres', '-d', self.state['testDatabase'], '-Fc', timeout=300))
            self.sql('DROP DATABASE ' + self.state['testDatabase'] + ' WITH (FORCE)')
        self.state['restoration']['temporaryDatabaseRemoved'] = True
        self.state_save()
        print(now(), 'Original service restored; original data fingerprints match', flush=True)

    def execute(self):
        self.acquire_lock()
        try:
            self.prepare()
            self.seed()
            for vus in (1, 5, 10):
                self.trial('preflight-mixed-' + str(vus), 'mixed', vus, duration=30, warmup=10)
            self.trial('mixed-100vu-600s', 'mixed', 100)
            for mode in ('catalog', 'booking'):
                for vus in (25, 50, 100):
                    for replicas in (1, 2):
                        self.trial(f'{mode}-r{replicas}-vu{vus}-600s', mode, vus, replicas)
            self.state['executionStatus'] = 'performance-complete'
            self.state_save()
        except BaseException as error:
            self.state['executionStatus'] = 'stopped'; self.state['executionError'] = str(error); self.state_save()
            raise
        finally:
            try:
                self.restore()
            finally:
                if self.lock:
                    self.lock.stdin.close(); self.lock.wait(timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--action', choices=('capture', 'execute', 'restore'), required=True)
    parser.add_argument('--maintenance-window', action='store_true')
    args = parser.parse_args()
    if args.action != 'capture' and not args.maintenance_window:
        parser.error('Explicit --maintenance-window authorization is required')
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit('Terminated; restore original deployment'))
    driver = Maintenance(args)
    if args.action == 'capture':
        driver.capture()
    elif args.action == 'restore':
        driver.restore()
    else:
        if not driver.state or driver.state['phase'] != 'captured':
            parser.error('Capture an original baseline first')
        driver.execute()


if __name__ == '__main__':
    main()
