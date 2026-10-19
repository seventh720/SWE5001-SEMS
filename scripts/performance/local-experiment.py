#!/usr/bin/env python3
"""Run reproducible experiments on a dedicated local Docker Compose JSON stack.

Restores its database before EACH run. Never use a demo/production stack.
Private input files and database snapshots must remain outside committed evidence.
"""
import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def recovery(raw, stopped):
    """First observed 30-second window with traffic, <1% errors and p95<3s."""
    samples, durations = [], []
    with open(raw) as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('type') != 'Point':
                continue
            data = row['data']
            t = dt.datetime.fromisoformat(data['time'].replace('Z', '+00:00')).timestamp()
            if row['metric'] == 'unexpected_error_rate':
                samples.append((t, data['value']))
            elif row['metric'] == 'operation_duration':
                durations.append((t, data['value'], data.get('tags', {}).get('operation')))
    samples.sort()
    failed = [t for t, error in samples if error and t >= stopped]
    result = {'failedRequestsAfterStop': len(failed), 'recoverySeconds': None,
              'firstFailureAfterStopSeconds': failed[0] - stopped if failed else None,
              'lastFailureAfterStopSeconds': failed[-1] - stopped if failed else None,
              'definition': 'First 30s window, sampled at 1s offsets from stop request, with traffic in every second, error rate <1% and each operation p95 <3000ms. Completion timestamps; local experiment only.'}
    if not samples:
        return result
    for offset in range(max(0, math.floor(samples[-1][0] - stopped - 30)) + 1):
        start = stopped + offset
        window = [(t, v) for t, v in samples if start <= t < start + 30]
        if len({int(t - start) for t, _ in window}) != 30:
            continue
        ops = {}
        for t, value, operation in durations:
            if start <= t < start + 30:
                ops.setdefault(operation, []).append(value)
        if not ops or sum(v for _, v in window) / len(window) >= .01:
            continue
        if all(sorted(v)[math.ceil(len(v) * .95) - 1] < 3000 for v in ops.values()):
            result['recoverySeconds'] = offset
            result['stableWindowRequests'] = len(window)
            break
    return result


class Experiment:
    def __init__(self, args):
        self.args = args
        self.compose_file = Path(args.compose).resolve()
        self.dataset_file = Path(args.dataset).resolve()
        self.out = Path(args.output).resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.config = json.loads(self.compose_file.read_text())
        self.data = json.loads(self.dataset_file.read_text())
        self.base = self.data['baseUrl'].rstrip('/')
        # This runner performs database restores; enforce the dedicated local scope.
        if self.config.get('name') != 'sems-architecture' or self.base != 'http://127.0.0.1:18087':
            raise ValueError('Requires dedicated sems-architecture stack on loopback port 18087')
        for service in ('event-catalog', 'admission'):
            if not self.config['services'][service].get('cpus') or not self.config['services'][service].get('mem_limit'):
                raise ValueError('Set explicit per-replica CPU/memory limits')
        self.compose = ['docker', 'compose', '-f', str(self.compose_file)]
        self.env = dict(os.environ, SEMS_COMPOSE_FILE=str(self.compose_file))
        self.snapshot = Path(args.baseline).resolve() if args.baseline else self.dataset_file.parent / ('baseline-' + self.out.name + '.dump')
        self.results = []
        self.commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()

    def command(self, args, **kwargs):
        return subprocess.run(args, cwd=ROOT, check=True, **kwargs)

    def status(self, phase, **extra):
        write(self.out / 'progress.json', {'updatedAt': utc(), 'phase': phase, 'completedRuns': len(self.results), **extra})
        print(utc(), phase, extra, flush=True)

    def ids(self, service):
        return subprocess.check_output(self.compose + ['ps', '-q', service], text=True).split()

    def ready(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            ready = True
            for service, port in [('identity', 8081), ('event-catalog', 8082), ('admission', 8083)]:
                ids = self.ids(service)
                if not ids:
                    ready = False
                for cid in ids:
                    ip = subprocess.check_output(['docker', 'inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', cid], text=True).strip()
                    probe = subprocess.run(self.compose + ['exec', '-T', 'gateway', 'wget', '-qO-', '-T', '2', f'http://{ip}:{port}/actuator/health/readiness'], capture_output=True, text=True)
                    try:
                        ready = ready and probe.returncode == 0 and json.loads(probe.stdout).get('status') == 'UP'
                    except ValueError:
                        ready = False
            if ready:
                time.sleep(7)  # Allow gateway Docker DNS refresh, unchanged between runs.
                return
            time.sleep(2)
        raise RuntimeError('All-replica readiness timed out')

    def reset(self, catalog, admission):
        self.command(self.compose + ['stop', 'identity', 'event-catalog', 'admission'], stdout=subprocess.DEVNULL)
        with self.snapshot.open('rb') as src:
            self.command(self.compose + ['exec', '-T', 'postgres', 'pg_restore', '-U', 'postgres', '-d', 'sems', '--clean', '--if-exists', '--exit-on-error'], stdin=src, stdout=subprocess.DEVNULL)
        self.command(self.compose + ['up', '-d', '--no-build', '--pull', 'never', '--scale', f'event-catalog={catalog}', '--scale', f'admission={admission}'], stdout=subprocess.DEVNULL)
        self.ready()
        self.command(['python3', 'scripts/performance/seed.py', '--base-url', self.base, '--output', str(self.dataset_file), '--refresh'], stdout=subprocess.DEVNULL)
        self.data = json.loads(self.dataset_file.read_text())

    def observe(self, target, stop):
        with target.open('w') as out:
            while not stop.is_set():
                try:
                    result = subprocess.run(['python3', 'scripts/observe-platform.py', '5s'], cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=40)
                    row = json.loads(result.stdout) if result.returncode == 0 else {'collectionError': result.returncode, 'observedAt': utc()}
                except (ValueError, subprocess.TimeoutExpired):
                    row = {'collectionError': True, 'observedAt': utc()}
                out.write(json.dumps(row) + '\n')
                out.flush()
                stop.wait(5)

    def api(self, method, path, user, body=None):
        request = urllib.request.Request(self.base + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + user['token']})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, {}
        except (OSError, ValueError):
            return 0, {}

    def replay_probe(self, stop, target, attempts):
        # An independent low-rate business probe retains original keys across failures.
        user = self.data['users'][0]
        with target.open('w') as out:
            while not stop.is_set():
                event = self.data['events'][len(attempts) % len(self.data['events'])]
                body = {'eventId': event['eventId'], 'ticketTypeId': event['ticketTypeId'], 'quantity': 1, 'requestKey': str(uuid.uuid4())}
                observed = []
                codes = []
                for _ in range(2):
                    code, result = self.api('POST', '/api/v1/bookings', user, body)
                    codes.append(code)
                    if code == 200:
                        observed.append(result['id'])
                row = {'time': utc(), 'request': body, 'statuses': codes, 'bookingIds': observed}
                attempts.append(row)
                out.write(json.dumps(row) + '\n')
                out.flush()
                stop.wait(1)

    def run(self, mode, replicas, vus, repeat, fault=False):
        name = f'{mode}-r{replicas}-vu{vus}-repeat{repeat}' + ('-fault' if fault else '')
        target = self.out / name
        target.mkdir()
        self.status('preparing', run=name)
        cat, adm = (replicas, 1) if mode == 'catalog' else (1, replicas)
        self.reset(cat, adm)
        start = utc()
        ids = {service: self.ids(service) for service in ('event-catalog', 'admission')}
        mapping = []
        for service, containers in ids.items():
            for cid in containers:
                info = json.loads(subprocess.check_output(['docker', 'inspect', cid], text=True))[0]
                mapping.append({'service': service, 'container': cid, 'imageId': info['Image'],
                    'cpuNano': info['HostConfig']['NanoCpus'], 'memoryBytes': info['HostConfig']['Memory'],
                    'addresses': [v['IPAddress'] for v in info['NetworkSettings']['Networks'].values()]})
        write(target / 'replicas.json', mapping)
        duration = 180 if fault else self.args.duration
        warmup = 10 if fault else self.args.warmup
        args = ['docker', 'run', '--rm', '--name', 'sems-architecture-load',
                '-v', f'{ROOT}/scripts/performance:/src:ro', '-v', f'{self.dataset_file}:/input/dataset.json:ro', '-v', f'{target}:/out']
        values = dict(DATASET='/input/dataset.json', BASE_URL='http://host.docker.internal:18087', MODE=mode,
                      VUS=str(vus), WARMUP_SECONDS=str(warmup), DURATION_SECONDS=str(duration),
                      RUN_ID=name + '-' + self.out.name, COMMIT=self.commit,
                      REPLICAS=f'catalog{cat}-admission{adm}', SUMMARY_FILE='/out/summary.json')
        for key, value in values.items():
            args += ['-e', key + '=' + value]
        args += ['grafana/k6:1.3.0', 'run', '--out', 'json=/out/raw.json', '/src/load.js']
        stop = threading.Event()
        observer = threading.Thread(target=self.observe, args=(target / 'resources.jsonl', stop))
        observer.start()
        attempts = []
        probe = None
        if fault:
            probe = threading.Thread(target=self.replay_probe, args=(stop, target / 'replay-attempts.jsonl', attempts))
            probe.start()
        self.status('running', run=name, durationSeconds=duration, warmupSeconds=warmup)
        failure = None
        try:
            with (target / 'k6.log').open('w') as log:
                process = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                try:
                    if fault:
                        # Check setup/load is actually active before injecting the fault.
                        time.sleep(40)
                        if process.poll() is not None:
                            raise RuntimeError('Load ended before fault injection')
                        service = 'event-catalog' if mode == 'catalog' else 'admission'
                        self.command(['python3', 'scripts/performance/fault.py', '--service', service, '--seconds', '45', '--output', str(target / 'fault.jsonl')], env=self.env)
                    exit_code = process.wait(timeout=duration + warmup + 150)
                finally:
                    if process.poll() is None:
                        subprocess.run(['docker', 'stop', 'sems-architecture-load'], capture_output=True)
                        process.wait(timeout=30)
        finally:
            stop.set()
            observer.join(timeout=50)
            if probe:
                probe.join(timeout=35)
        write(target / 'completion.json', {'loadCompletedAt': utc(), 'exitCode': exit_code})
        self.ready()
        if fault:
            events = [json.loads(line) for line in (target / 'fault.jsonl').read_text().splitlines()]
            stopped = dt.datetime.fromisoformat(events[0]['time']).timestamp()
            failure = recovery(target / 'raw.json', stopped)
            user = self.data['users'][0]
            reconciled = []
            for attempt in attempts:
                code, result = self.api('POST', '/api/v1/bookings', user, attempt['request'])
                ok = code == 200 and all(b == result.get('id') for b in attempt['bookingIds'])
                reconciled.append({'requestKey': attempt['request']['requestKey'], 'bookingId': result.get('id'), 'passed': ok})
            keys = ','.join("'" + str(uuid.UUID(r['requestKey'])) + "'" for r in reconciled)
            count = int(subprocess.check_output(self.compose + ['exec', '-T', 'postgres', 'psql', '-U', 'postgres', '-d', 'sems', '-Atq', '-c', f'SELECT count(*) FROM admission.bookings WHERE request_key IN ({keys})'], text=True)) if keys else 0
            failure['replayedKeys'] = len(reconciled)
            failure['persistedBookingsForKeys'] = count
            failure['idempotencyPassed'] = bool(reconciled) and all(r['passed'] for r in reconciled) and count == len(reconciled)
            write(target / 'reconciliation.json', reconciled)
            write(target / 'recovery.json', failure)
        audit = subprocess.run(['python3', 'scripts/performance/audit.py', '--dataset', str(self.dataset_file), '--output', str(target / 'inventory.json')], cwd=ROOT, env=self.env, capture_output=True, text=True)
        with (target / 'gateway.jsonl').open('w') as log:
            subprocess.run(self.compose + ['logs', '--no-log-prefix', '--since', start, 'gateway'], stdout=log, stderr=subprocess.DEVNULL, check=True)
        with (target / 'raw.json').open('rb') as src, gzip.open(target / 'raw.json.gz', 'wb') as dest:
            shutil.copyfileobj(src, dest)
        (target / 'raw.json').unlink()
        result = {'run': name, 'mode': mode, 'replicas': replicas, 'vus': vus, 'repeat': repeat,
                  'fault': fault, 'loadExitCode': exit_code, 'auditPassed': audit.returncode == 0, 'recovery': failure}
        self.results.append(result)
        write(self.out / 'runs.json', self.results)
        self.status('run-complete', run=name, loadExitCode=exit_code, auditPassed=result['auditPassed'])
        if audit.returncode != 0 or (fault and not failure['idempotencyPassed']):
            raise RuntimeError('Business consistency failed; stopped to retain evidence')
        if exit_code not in (0, 99):
            raise RuntimeError('Load infrastructure failed; inspect k6.log')

    def execute(self):
        self.status('initializing')
        self.ready()
        if not self.args.baseline:
            with self.snapshot.open('xb') as out:
                os.chmod(self.snapshot, 0o600)
                self.command(self.compose + ['exec', '-T', 'postgres', 'pg_dump', '-U', 'postgres', '-d', 'sems', '-Fc'], stdout=out)
        images = {}
        for name, service in self.config['services'].items():
            info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', service['image']], text=True))[0]
            images[name] = {'id': info['Id'], 'repoDigests': info.get('RepoDigests', [])}
        info = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .}}'], text=True))
        write(self.out / 'environment.json', {'startedAt': utc(), 'commit': self.commit,
              'dataset': self.data['runId'], 'users': len(self.data['users']), 'events': len(self.data['events']),
              'snapshotSha256': hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
              'dockerCpus': info['NCPU'], 'dockerMemoryBytes': info['MemTotal'], 'architecture': info['Architecture'],
              'images': images, 'limits': {s: {k: self.config['services'][s].get(k) for k in ('cpus', 'mem_limit')} for s in self.config['services']},
              'warmupSeconds': self.args.warmup, 'measurementSeconds': self.args.duration,
              'repetitions': self.args.repeats, 'vus': [25, 50, 100],
              'limitations': ['Local Docker Desktop, not cloud or host-level HA', 'Load generator shares Docker VM with services',
                  'Other local containers remain running; contention is not eliminated',
                  'Images built before this experiment; recorded image IDs define tested artifacts, not an assumed HEAD rebuild',
                  'No extra paid resources; resource cost is CPU/memory allocation, not measured cloud billing']} )
        try:
            if self.args.only_runs:
                for name in self.args.only_runs:
                    match = re.fullmatch(r'(catalog|booking)-r([12])-vu(25|50|100)-repeat([123])', name)
                    if not match:
                        raise ValueError('Invalid repeat identifier')
                    mode, replicas, vus, repeat = match.groups()
                    self.run(mode, int(replicas), int(vus), int(repeat))
            else:
                for mode in ('catalog', 'booking'):
                    self.run(mode, 2, 25, 1, fault=True)
            if not self.args.fault_only and not self.args.only_runs:
                for mode in ('catalog', 'booking'):
                    for vus in (25, 50, 100):
                        for repeat in range(1, self.args.repeats + 1):
                            for replicas in ((1, 2) if repeat % 2 else (2, 1)):
                                self.run(mode, replicas, vus, repeat)
            self.status('complete')
        except BaseException as error:
            self.status('failed', error=type(error).__name__, detail=str(error))
            raise
        finally:
            self.command(self.compose + ['stop'], stdout=subprocess.DEVNULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compose', required=True)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--duration', type=int, default=600)
    parser.add_argument('--warmup', type=int, default=60)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--fault-only', action='store_true')
    parser.add_argument('--baseline', help='Reuse the ORIGINAL private snapshot for selected replacement runs')
    parser.add_argument('--only-runs', nargs='+', help='Explicit failed/invalid run IDs to repeat, retaining original evidence')
    args = parser.parse_args()
    if min(args.duration, args.warmup, args.repeats) < 1:
        parser.error('Durations and repetitions must be positive')
    if bool(args.baseline) != bool(args.only_runs):
        parser.error('Use --baseline and --only-runs together for controlled replacement runs')
    os.umask(0o077)
    Experiment(args).execute()


if __name__ == '__main__':
    main()
