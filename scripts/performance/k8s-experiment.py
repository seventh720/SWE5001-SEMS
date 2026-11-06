#!/usr/bin/env python3
"""Run short 1/2 replica comparisons in kind-sems-local/sems-benchmark only.

Restores a PRIVATE database snapshot before every run. Creates its own gateway
port-forward; no public/cloud target or production namespace option is accepted.
"""
import argparse
from collections import Counter
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
CONTEXT = 'kind-sems-local'
NAMESPACE = 'sems-benchmark'
BASE = 'http://127.0.0.1:18087'
BACKENDS = ('identity', 'event-catalog', 'admission')
SERVICES = (*BACKENDS, 'web', 'gateway')
CPU_ROUND_ANNOTATION = 'sems.seventh720.com/cpu-experiment-round'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


secret_renderer = load_module('benchmark_secrets', ROOT / 'scripts/k8s/secrets.py')
comparison = load_module('benchmark_comparison', Path(__file__).with_name('compare.py'))


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def check_sample_continuity(previous, current):
    if previous is not None:
        gap = (dt.datetime.fromisoformat(current) - dt.datetime.fromisoformat(previous)).total_seconds()
        if gap < 0 or gap > 15:
            raise RuntimeError(f'Stopped: resource sampling clock gap {gap:.3f}s; continuous load invalid')


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def validate_target(config, namespace):
    contexts = [x for x in config.get('contexts', []) if x['name'] == CONTEXT]
    if len(contexts) != 1:
        raise ValueError('Requires explicit kind-sems-local context')
    cluster = contexts[0]['context']['cluster']
    if cluster != CONTEXT:
        raise ValueError('Requires the kind-sems-local cluster reference')
    servers = [x['cluster']['server'] for x in config['clusters'] if x['name'] == cluster]
    if len(servers) != 1 or urlparse(servers[0]).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Benchmark requires a loopback Kubernetes API')
    metadata = namespace['metadata']
    if metadata['name'] != NAMESPACE or metadata.get('annotations', {}).get(
            'sems.seventh720.com/environment') != 'benchmark':
        raise ValueError('Requires explicitly marked disposable sems-benchmark namespace')


def inventory_query(data):
    import uuid
    ids = ','.join("'" + str(uuid.UUID(e['eventId'])) + "'" for e in data['events'])
    if not ids or len({e['eventId'] for e in data['events']}) != len(data['events']):
        raise ValueError('Dataset needs distinct events')
    return f"""SELECT coalesce(json_agg(row_to_json(x)), '[]'::json) FROM (
        SELECT t.id, t.quota, t.reserved,
          (SELECT coalesce(sum(b.quantity),0) FROM admission.bookings b
           WHERE b.ticket_type_id=t.id AND b.status='CONFIRMED') AS confirmed,
          (SELECT count(*) FROM admission.tickets k JOIN admission.bookings b ON b.id=k.booking_id
           WHERE b.ticket_type_id=t.id AND k.state IN ('VALID','CHECKED_IN')) AS tickets
        FROM admission.ticket_types t WHERE t.event_id IN ({ids}) ORDER BY t.id) x"""


def inventory_passed(rows, events):
    return len(rows) == events and all(0 <= r['reserved'] <= r['quota'] and
                                      r['reserved'] == r['confirmed'] == r['tickets'] for r in rows)


def traffic_counts(text, mode):
    counts = Counter()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4 or not fields[2].isdigit():
            continue
        method, path, status, _ = fields
        if mode == 'catalog' and method == 'GET' and re.fullmatch(r'/api/v1/events(?:/[^/]+)?', path):
            counts[status] += 1
        elif mode == 'booking' and ((method == 'POST' and path == '/api/v1/bookings') or
                                   (method == 'GET' and re.fullmatch(r'/api/v1/bookings/[^/]+', path))):
            counts[status] += 1
    return dict(counts)


def gateway_evidence(lines, run_id, expected_measurement):
    entry, internal, upstream_errors = Counter(), Counter(), Counter()
    malformed, measurement, retries = 0, 0, 0
    for line in lines:
        try:
            row = json.loads(line)
            status, port = int(row['status']), int(row['server_port'])
        except (ValueError, KeyError, TypeError):
            malformed += 1
            continue
        if port == 80 and row.get('benchmark_run') == run_id:
            phase = row.get('benchmark_phase', 'missing')
            entry[f'{phase}:{status}'] += 1
            measurement += phase == 'measurement'
        if port == 8080 and row.get('path', '').startswith('/internal/'):
            internal[str(status)] += 1
        statuses = re.findall(r'\b\d{3}\b', str(row.get('upstream_status', '')))
        for code in statuses:
            if int(code) >= 500:
                upstream_errors[code] += 1
        retries += len(statuses) > 1
    coverage = expected_measurement > 0 and measurement == expected_measurement and malformed == 0
    return {'entryByPhaseAndStatus': dict(entry), 'internalByStatus': dict(internal),
            'upstreamErrorsByStatus': dict(upstream_errors), 'requestsWithMultipleUpstreams': retries,
            'malformedLines': malformed, 'expectedMeasurementRequests': expected_measurement,
            'recordedMeasurementRequests': measurement, 'measurementCoveragePassed': coverage,
            'serverGatePassed': coverage and not upstream_errors and retries == 0 and
                not any(int(k) >= 500 for k in internal) and
                not any(int(k.rsplit(':', 1)[1]) >= 500 for k in entry)}


class Experiment:
    def __init__(self, args):
        self.args = args
        self.kube = ['kubectl', '--kubeconfig', str(Path(args.kubeconfig).resolve()),
                     '--context', CONTEXT, '-n', NAMESPACE]
        self.out = Path(args.output).resolve()
        private = ROOT / '.performance'
        if not self.out.is_relative_to(private) or self.out == private:
            raise ValueError('Output must be a new directory under ignored .performance/')
        self.env_file = Path(args.env_file).resolve()
        self.env = secret_renderer.read_env(self.env_file)
        self.runs = []
        self.forwarder = None
        self.original = {}
        self.active_load = None
        self.load_name = 'sems-benchmark-load-' + str(os.getpid())

    def command(self, arguments, **kwargs):
        kwargs.setdefault('timeout', 120)
        return subprocess.run(arguments, cwd=ROOT, check=True, **kwargs)

    def kube_json(self, *arguments):
        return json.loads(subprocess.check_output(self.kube + list(arguments), text=True, timeout=30))

    def guard(self):
        config = self.kube_json('config', 'view', '-o', 'json')
        namespace = self.kube_json('get', 'namespace', NAMESPACE, '-o', 'json')
        validate_target(config, namespace)
        nodes = self.kube_json('get', 'nodes', '-o', 'json')['items']
        if not nodes or any(not re.fullmatch(r'sems-local-(control-plane|worker\d*)', n['metadata']['name']) for n in nodes):
            raise ValueError('Refusing nodes outside the sems-local kind cluster')
        self.nodes = [n['metadata']['name'] for n in nodes]
        database = self.kube_json('get', 'configmap', 'sems-database', '-o', 'json')['data']
        for service in ('IDENTITY', 'CATALOG', 'ADMISSION'):
            schema = service.lower()
            if database.get(service + '_DB_URL') != f'jdbc:postgresql://postgres:5432/sems?currentSchema={schema}':
                raise ValueError('Refusing database outside the benchmark namespace')
        postgres = self.kube_json('get', 'pod', 'postgres-0', '-o', 'json')
        for entry in postgres['spec']['containers']:
            if any(e['name'] == 'PGHOST' for e in entry.get('env', [])):
                raise ValueError('Unexpected remote PGHOST')
        pvc_uid = self.kube_json('get', 'pvc', 'data-postgres-0', '-o', 'json')['metadata']['uid']
        if hasattr(self, 'pvc_uid') and pvc_uid != self.pvc_uid:
            raise ValueError('Benchmark PVC changed; refusing restore')
        self.pvc_uid = pvc_uid

    def scale(self, values):
        for name, count in values.items():
            self.command(self.kube + ['scale', 'deployment/' + name, '--replicas=' + str(count)],
                         stdout=subprocess.DEVNULL)

    def pods(self):
        return self.kube_json('get', 'pods', '-o', 'json')['items']

    def ready(self, expected):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            pods = self.pods()
            ok = True
            for service, count in expected.items():
                selected = [p for p in pods if p['metadata'].get('labels', {}).get(
                    'app.kubernetes.io/name') == service]
                ok = ok and len(selected) == count and all(
                    not p['metadata'].get('deletionTimestamp') and any(
                        c['type'] == 'Ready' and c['status'] == 'True'
                        for c in p.get('status', {}).get('conditions', [])) for p in selected)
            if ok:
                return pods
            time.sleep(2)
        raise RuntimeError('Expected replica readiness timed out')

    def forward(self):
        log = (self.out / 'port-forward.log').open('w+')
        self.forward_log = log
        self.forwarder = subprocess.Popen(self.kube + ['port-forward', '--address', '127.0.0.1',
                                                       'service/gateway', '18087:80'],
                                          stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            log.seek(0)
            if 'Forwarding from 127.0.0.1:18087' in log.read():
                return
            if self.forwarder.poll() is not None:
                raise RuntimeError('Own port-forward failed; port 18087 must be free')
            time.sleep(.1)
        raise RuntimeError('Port-forward timed out')

    def seed(self, refresh=False):
        command = [sys.executable, str(ROOT / 'scripts/performance/seed.py'), '--base-url', BASE,
                   '--output', str(self.out / 'dataset.json')]
        if refresh:
            command += ['--refresh']
        else:
            command += ['--users', str(self.args.users), '--events', str(self.args.events), '--quota', str(self.args.quota)]
        self.command(command, env={**os.environ, **{key: self.env[key] for key in (
            'SEMS_BOOTSTRAP_ADMIN_EMAIL', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD')}}, stdout=subprocess.DEVNULL,
            timeout=max(120, self.args.users * 2 + self.args.events * 10))
        self.data = json.loads((self.out / 'dataset.json').read_text())

    def reset(self, mode, replicas):
        self.guard()
        self.scale(dict.fromkeys(BACKENDS, 0))
        self.ready(dict.fromkeys(BACKENDS, 0))
        if getattr(self.args, 'postgres_cpu_limits', None):
            patch = {'spec': {'template': {'metadata': {'annotations': {
                CPU_ROUND_ANNOTATION: self.out.name + '-' + str(time.monotonic_ns())}},
                'spec': {'containers': [{'name': 'postgres', 'resources': {
                    'limits': {'cpu': str(self.postgres_cpu)}}}]}}}}
            self.command(self.kube + ['patch', 'statefulset/postgres', '--type=strategic',
                                     '-p', json.dumps(patch)], stdout=subprocess.DEVNULL)
            self.postgres_ready()
            self.guard()
            actual = self.kube_json('get', 'pod', 'postgres-0', '-o', 'json')['spec']['containers'][0]
            if actual['resources']['limits']['cpu'] != str(self.postgres_cpu):
                raise RuntimeError('PostgreSQL CPU limit does not match requested control')
        with (self.out / 'baseline.dump').open('rb') as stream:
            self.command(self.kube + ['exec', '-i', 'postgres-0', '--', 'pg_restore', '-U', 'postgres',
                                     '-d', 'sems', '--clean', '--if-exists', '--exit-on-error'],
                         stdin=stream, stdout=subprocess.DEVNULL)
        expected = dict.fromkeys(SERVICES, 1)
        expected['event-catalog' if mode == 'catalog' else 'admission'] = replicas
        self.scale({s: expected[s] for s in BACKENDS})
        pods = self.ready(expected)
        time.sleep(7)  # Shared, fixed allowance for the gateway's 5-second DNS cache.
        self.seed(refresh=True)
        return pods

    def postgres_ready(self):
        self.command(self.kube + ['rollout', 'status', 'statefulset/postgres', '--timeout=180s'],
                     stdout=subprocess.DEVNULL, timeout=200)
        self.command(self.kube + ['wait', '--for=condition=Ready', 'pod/postgres-0', '--timeout=120s'],
                     stdout=subprocess.DEVNULL, timeout=140)

    def restore_postgres_template(self):
        current = self.kube_json('get', 'statefulset', 'postgres', '-o', 'json')['spec']['template']
        patch = []
        original_resources = self.original_postgres['spec']['containers'][0]['resources']
        if current['spec']['containers'][0]['resources'] != original_resources:
            patch.append({'op': 'replace', 'path': '/spec/template/spec/containers/0/resources',
                          'value': original_resources})
        annotations = self.original_postgres['metadata'].get('annotations')
        if current['metadata'].get('annotations') != annotations:
            patch.append({'op': 'add' if annotations is not None else 'remove',
                          'path': '/spec/template/metadata/annotations',
                          **({'value': annotations} if annotations is not None else {})})
        if patch:
            self.command(self.kube + ['patch', 'statefulset/postgres', '--type=json', '-p', json.dumps(patch)],
                         stdout=subprocess.DEVNULL)
            self.postgres_ready()

    def sample(self):
        result = {'time': utc(), 'nodes': [], 'pods': []}
        for node in self.nodes:
            stats = self.kube_json('get', '--raw', '/api/v1/nodes/' + node + '/proxy/stats/summary')
            result['nodes'].append({k: stats['node'].get(k) for k in ('nodeName', 'cpu', 'memory', 'fs')})
            result['pods'] += [p for p in stats['pods'] if p['podRef']['namespace'] == NAMESPACE]
        return result

    def database_sample(self):
        # No SQL text, tokens or attendee data are captured. Sample only this isolated DB.
        query = """SELECT json_build_object(
          'time',clock_timestamp(),
          'settings',(SELECT json_object_agg(name,setting) FROM pg_settings
            WHERE name IN ('max_connections','shared_buffers','work_mem','track_io_timing')),
          'activity',(SELECT coalesce(json_agg(json_build_object(
            'pid',pid,'role',usename,'state',state,'waitType',wait_event_type,'waitEvent',wait_event,
            'transactionAgeSeconds',extract(epoch FROM clock_timestamp()-xact_start),
            'blockers',pg_blocking_pids(pid))),'[]'::json)
            FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),
          'database',(SELECT row_to_json(d) FROM (SELECT xact_commit,xact_rollback,blks_read,
            blks_hit,tup_returned,tup_fetched,tup_inserted,tup_updated,tup_deleted,
            conflicts,temp_files,temp_bytes,deadlocks,blk_read_time,blk_write_time,stats_reset
            FROM pg_stat_database WHERE datname=current_database()) d))"""
        return json.loads(subprocess.check_output(self.kube + ['exec', 'postgres-0', '--', 'psql',
            '-U', 'postgres', '-d', 'sems', '-v', 'ON_ERROR_STOP=1', '-Atq', '-c', query],
            text=True, timeout=30))

    def pod_map(self, pods):
        return {p['metadata']['name']: {
            'uid': p['metadata']['uid'], 'service': p['metadata'].get('labels', {}).get('app.kubernetes.io/name'),
            'node': p['spec']['nodeName'], 'ip': p['status']['podIP'],
            'containers': [{'name': c['name'], 'image': c['image'], 'imageID': c.get('imageID'),
                            'restartCount': c.get('restartCount', 0)}
                           for c in p['status'].get('containerStatuses', [])],
            'resources': [c.get('resources', {}) for c in p['spec']['containers']],
            'poolSizes': [e for c in p['spec']['containers'] for e in c.get('env', [])
                          if e['name'] == 'CATALOG_DB_POOL_SIZE'],
        } for p in pods}

    def check_sample(self, sample, mapping):
        for node in sample['nodes']:
            if node['memory'].get('availableBytes', 0) < 512 * 1024**2:
                raise RuntimeError('Stopped: node available memory below 512MiB')
            fs = node.get('fs') or {}
            if fs.get('capacityBytes', 0) and fs['availableBytes'] / fs['capacityBytes'] < .1:
                raise RuntimeError('Stopped: node disk available below 10%')
        current = self.pod_map(self.pods())
        if current != mapping:
            raise RuntimeError('Stopped: Pod identity, image, resource or restart count changed during load')

    def stop_load(self):
        if self.active_load is None:
            return
        if self.active_load.poll() is None:
            subprocess.run(['docker', 'stop', '-t', '5', self.load_name], capture_output=True, timeout=20)
            try:
                self.active_load.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.active_load.kill()
        self.active_load = None

    def run(self, mode, replicas, vus, repetition, distribution='spread'):
        name = f'{mode}-r{replicas}-vu{vus}-repeat{repetition}' + ('-hot' if distribution == 'hot' else '')
        if getattr(self.args, 'postgres_cpu_limits', None):
            name += f'-db{self.postgres_cpu}cpu'
        target = self.out / name
        target.mkdir()
        print(utc(), 'Preparing', name, flush=True)
        pods = self.reset(mode, replicas)
        mapping = self.pod_map(pods)
        for service, images in self.images.items():
            actual = {c['imageID'] for p in mapping.values() if p['service'] == service for c in p['containers']}
            if actual != images:
                raise RuntimeError('Image changed between runs: ' + service)
        write(target / 'pods.json', mapping)
        self.check_sample(self.sample(), mapping)
        tested_service = 'event-catalog' if mode == 'catalog' else 'admission'
        postgres_cpu = next(p for p in mapping.values() if p['service'] == 'postgres')['resources'][0]['limits']['cpu']
        values = dict(DATASET='/input/dataset.json', BASE_URL='http://host.docker.internal:18087',
                      POSTGRES_CPU_LIMIT=postgres_cpu,
                      MODE=mode, VUS=str(vus), WARMUP_SECONDS=str(self.args.warmup),
                      EVENT_DISTRIBUTION=distribution, THINK_SECONDS=str(self.args.think_seconds),
                      DURATION_SECONDS=str(self.args.duration), RUN_ID=self.out.name + '-' + name,
                      COMMIT=self.commit, REPLICAS=f'catalog{replicas if mode == "catalog" else 1}'
                      f'-admission{replicas if mode == "booking" else 1}', SUMMARY_FILE='/out/summary.json')
        command = ['docker', 'run', '--rm', '--name', self.load_name, '--cpus=1', '--memory=256m',
                   '--user', str(os.getuid()) + ':' + str(os.getgid()),
                   '-v', f'{ROOT}/scripts/performance:/src:ro',
                   '-v', f'{self.out}/dataset.json:/input/dataset.json:ro', '-v', f'{target}:/out']
        for key, value in values.items():
            command += ['-e', key + '=' + value]
        command += ['grafana/k6:1.3.0', 'run', '--out', 'json=/out/raw.json', '/src/load.js']
        exit_code, failure = None, None
        start = utc()
        print(utc(), 'Running', name, flush=True)
        self.command(self.kube + ['exec', 'deployment/gateway', '--', 'sh', '-ec',
            'grep -q /tmp/sems-gateway/access.jsonl /etc/nginx/nginx.conf; '
            ': > /tmp/sems-gateway/access.jsonl; : > /tmp/sems-gateway/error.log'], stdout=subprocess.DEVNULL)
        try:
            with (target / 'k6.log').open('w') as log, (target / 'resources.jsonl').open('w') as samples, \
                    (target / 'database.jsonl').open('w') as database:
                database.write(json.dumps(self.database_sample()) + '\n')
                database.flush()
                self.active_load = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + self.args.warmup + self.args.duration + 120
                previous_sample = None
                while self.active_load.poll() is None:
                    sample = self.sample()
                    samples.write(json.dumps(sample) + '\n')
                    samples.flush()
                    check_sample_continuity(previous_sample, sample['time'])
                    previous_sample = sample['time']
                    self.check_sample(sample, mapping)
                    database.write(json.dumps(self.database_sample()) + '\n')
                    database.flush()
                    if self.forwarder.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Port-forward lost or load deadline exceeded')
                    time.sleep(5)
                exit_code = self.active_load.returncode
                database.write(json.dumps(self.database_sample()) + '\n')
        except Exception as error:
            failure = str(error)
        finally:
            self.stop_load()
        # Keep audit, logs and failed load results before aborting any comparison.
        with (target / 'gateway.jsonl').open('w') as log:
            self.command(self.kube + ['exec', 'deployment/gateway', '--', 'cat',
                                     '/tmp/sems-gateway/access.jsonl'], stdout=log, timeout=180)
        with (target / 'gateway-error.log').open('w') as log:
            self.command(self.kube + ['exec', 'deployment/gateway', '--', 'cat',
                                     '/tmp/sems-gateway/error.log'], stdout=log)
        summary_path = target / 'summary.json'
        rate_values = json.loads(summary_path.read_text())['metrics'][
            'unexpected_error_rate{scenario:measurement}']['values'] if summary_path.exists() else {}
        with (target / 'gateway.jsonl').open() as stream:
            gateway = gateway_evidence(stream, values['RUN_ID'],
                                       rate_values.get('passes', 0) + rate_values.get('fails', 0))
        gateway['bytes'] = (target / 'gateway.jsonl').stat().st_size
        write(target / 'gateway-evidence.json', gateway)
        counts = {}
        for pod, details in mapping.items():
            if details['service'] == tested_service:
                raw = subprocess.check_output(self.kube + ['exec', pod, '--', 'sh', '-c',
                    'cat /tmp/sems-access/* 2>/dev/null'], text=True, timeout=30)
                counts[pod] = traffic_counts(raw, mode)
        write(target / 'traffic.json', {'includesWarmup': True, 'requestsByPodAndStatus': counts})
        rows = json.loads(subprocess.check_output(self.kube + ['exec', 'postgres-0', '--', 'psql',
            '-U', 'postgres', '-d', 'sems', '-v', 'ON_ERROR_STOP=1', '-Atq', '-c', inventory_query(self.data)],
            text=True, timeout=30))
        audit = {'passed': inventory_passed(rows, len(self.data['events'])), 'inventory': rows}
        write(target / 'inventory.json', audit)
        result = {'run': name, 'mode': mode, 'replicas': replicas, 'vus': vus, 'repeat': repetition,
                  'distribution': distribution, 'thinkSeconds': self.args.think_seconds,
                  'postgresCpuLimit': postgres_cpu,
                  'runnerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'loadExitCode': exit_code, 'auditPassed': audit['passed'], 'failure': failure,
                  'gatewayCoveragePassed': gateway['measurementCoveragePassed'],
                  'serverGatePassed': gateway['serverGatePassed'],
                  'eachReplicaServed': len(counts) == replicas and all(sum(x.values()) > 0 for x in counts.values())}
        self.runs.append(result)
        write(self.out / 'runs.json', self.runs)
        print(utc(), 'Completed', name, result, flush=True)
        if failure or exit_code not in (0, 99) or not audit['passed'] or not result['eachReplicaServed'] or not gateway['measurementCoveragePassed']:
            raise RuntimeError('Run invalid; retained evidence in ' + str(target))
        return target

    def execute(self):
        self.guard()  # Complete target checks before ANY namespace mutation or seeding.
        self.original = {s: self.kube_json('get', 'deployment', s, '-o', 'json')['spec']['replicas'] for s in SERVICES}
        if any(n != 1 for n in self.original.values()):
            raise ValueError('Start with all five benchmark deployments at one replica')
        cpu_controls = getattr(self.args, 'postgres_cpu_limits', None)
        if cpu_controls:
            if self.args.modes != ['booking'] or self.args.replica_counts != [2] or any(c not in (1, 2) for c in cpu_controls):
                raise ValueError('PostgreSQL CPU comparison requires booking-only and fixed Admission two replicas')
            self.original_postgres = self.kube_json('get', 'statefulset', 'postgres', '-o', 'json')['spec']['template']
        self.out.mkdir(parents=True, exist_ok=False)
        self.commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        try:
            self.ready(self.original)
            self.images = {s: {c['imageID'] for p in self.pod_map(self.pods()).values()
                              if p['service'] == s for c in p['containers']} for s in SERVICES}
            if any(len(images) != 1 for images in self.images.values()):
                raise ValueError('Need one fixed running image ID per service')
            self.forward()
            self.seed()
            with (self.out / 'baseline.dump').open('xb') as stream:
                self.command(self.kube + ['exec', 'postgres-0', '--', 'pg_dump', '-U', 'postgres',
                                         '-d', 'sems', '-Fc'], stdout=stream)
            environment = {
                'startedAt': utc(), 'commit': self.commit, 'context': CONTEXT, 'namespace': NAMESPACE,
                'runnerSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'manifestSha256': hashlib.sha256(subprocess.check_output(
                    ['kubectl', 'kustomize', str(ROOT / 'deployment/k8s/overlays/benchmark')])).hexdigest(),
                'kubernetesVersion': self.kube_json('version', '-o', 'json')['serverVersion']['gitVersion'],
                'javaOptions': self.kube_json('get', 'configmap', 'sems-runtime', '-o', 'json')['data'].get('JAVA_TOOL_OPTIONS'),
                'dataset': self.data['runId'], 'users': len(self.data['users']), 'events': len(self.data['events']),
                'baselineSha256': hashlib.sha256((self.out / 'baseline.dump').read_bytes()).hexdigest(),
                'initialPods': self.pod_map(self.pods()), 'vus': self.args.vus, 'modes': self.args.modes,
                'warmupSeconds': self.args.warmup, 'measurementSeconds': self.args.duration,
                'repeats': self.args.repeats, 'pvcUid': self.pvc_uid,
                'replicaCounts': self.args.replica_counts, 'distributions': self.args.distributions,
                'controlledVariable': 'postgresCpuLimit' if cpu_controls else 'replicas',
                'postgresCpuLimits': cpu_controls,
                'originalPostgresTemplate': self.original_postgres if cpu_controls else None,
                'thinkSeconds': self.args.think_seconds, 'quotaPerEvent': self.args.quota,
                'loadScriptSha256': hashlib.sha256((ROOT / 'scripts/performance/load.js').read_bytes()).hexdigest(),
                'loadImage': json.loads(subprocess.check_output(['docker', 'image', 'inspect', 'grafana/k6:1.3.0'], text=True))[0]['Id'],
                'limitations': ['Local kind single node; no EC2 capacity or cross-node HA claim',
                                'Load generator, existing local containers and services share Docker VM',
                                'Port-forward and gateway are possible bottlenecks',
                                'Record initialPods imageIDs as tested artifacts; HEAD alone is not image provenance',
                                '10 VU / 60 second defaults are a tool preflight, not a capacity result'],
            }
            write(self.out / 'environment.json', environment)
            for mode in self.args.modes:
                for vus in self.args.vus:
                    for repetition in range(1, self.args.repeats + 1):
                        for distribution in self.args.distributions:
                            pair = {}
                            controls = cpu_controls or self.args.replica_counts
                            order = controls if repetition % 2 else controls[::-1]
                            for control in order:
                                if cpu_controls:
                                    self.postgres_cpu = control
                                replicas = 2 if cpu_controls else control
                                pair[control] = self.run(mode, replicas, vus, repetition, distribution)
                            if set(pair) == {1, 2}:
                                a, b = [json.loads((pair[n] / 'summary.json').read_text()) for n in (1, 2)]
                                report = comparison.compare(a, b, 'postgresCpuLimit' if cpu_controls else 'replicas')
                                report['eligibleForPerformanceClaim'] = False
                                report['note'] = 'Local Kubernetes comparison; inspect DB audit, resource contention and Pod traffic. No cloud capacity conclusion.'
                                suffix = ('-hot' if distribution == 'hot' else '') + ('-db-cpu' if cpu_controls else '')
                                write(self.out / f'{mode}-vu{vus}-repeat{repetition}{suffix}-comparison.json', report)
            write(self.out / 'completion.json', {'completedAt': utc(), 'status': 'complete', 'runs': len(self.runs)})
        except BaseException as error:
            write(self.out / 'completion.json', {'completedAt': utc(), 'status': 'failed', 'error': str(error)})
            raise
        finally:
            self.stop_load()
            if self.forwarder:
                self.forwarder.terminate()
                self.forwarder.wait(timeout=15)
                self.forward_log.close()
            # Restore replica counts only; never delete this namespace or its PVC.
            # If this fails, raise and require a manual inspection before another run.
            try:
                if cpu_controls:
                    self.scale(dict.fromkeys(BACKENDS, 0))
                    self.ready(dict.fromkeys(BACKENDS, 0))
                    self.restore_postgres_template()
                self.scale(self.original)
                self.ready(self.original)
                if self.kube_json('get', 'pvc', 'data-postgres-0', '-o', 'json')['metadata']['uid'] != self.pvc_uid:
                    raise RuntimeError('Benchmark PVC changed during experiment')
            except BaseException as error:
                write(self.out / 'completion.json', {'completedAt': utc(), 'status': 'cleanup-failed', 'error': str(error)})
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--vus', type=int, nargs='+', default=[10])
    parser.add_argument('--modes', choices=('catalog', 'booking'), nargs='+', default=['catalog', 'booking'])
    parser.add_argument('--users', type=int, default=20)
    parser.add_argument('--events', type=int, default=10)
    parser.add_argument('--quota', type=int, default=100000)
    parser.add_argument('--replica-counts', type=int, choices=(1, 2), nargs='+', default=[1, 2])
    parser.add_argument('--postgres-cpu-limits', type=int, choices=(1, 2), nargs='+')
    parser.add_argument('--distributions', choices=('spread', 'hot'), nargs='+', default=['spread'])
    parser.add_argument('--think-seconds', type=float, default=.1)
    parser.add_argument('--warmup', type=int, default=30)
    parser.add_argument('--duration', type=int, default=60)
    parser.add_argument('--repeats', type=int, default=1)
    args = parser.parse_args()
    if min(*args.vus, args.users, args.events, args.warmup, args.duration, args.repeats) < 1 or max(args.vus) > args.users:
        parser.error('Positive values and at least one user per VU are required')
    if args.quota < 1 or not math.isfinite(args.think_seconds) or args.think_seconds < 0:
        parser.error('Positive quota and finite, non-negative think time required')
    if len(set(args.replica_counts)) != len(args.replica_counts) or len(set(args.distributions)) != len(args.distributions):
        parser.error('Duplicate replica counts or distributions')
    if 'hot' in args.distributions and args.modes != ['booking']:
        parser.error('Hot-event distribution is for booking-only experiments')
    if args.postgres_cpu_limits and (args.modes != ['booking'] or args.replica_counts != [2] or
            len(set(args.postgres_cpu_limits)) != len(args.postgres_cpu_limits)):
        parser.error('Database CPU comparison requires booking-only, Admission fixed at 2 and distinct CPU limits')
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit('Terminated; restoring benchmark replicas'))
    Experiment(args).execute()


if __name__ == '__main__':
    main()
