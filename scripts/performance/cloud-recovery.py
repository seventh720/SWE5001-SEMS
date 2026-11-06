#!/usr/bin/env python3
"""Separate loaded Catalog/Admission Pod-failure trials during maintenance.

Reuses the private seeded snapshot from cloud-maintenance.py. Original business
data stays in its own database, and the maintenance runner restores service.
"""
import argparse
import concurrent.futures
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
import uuid
import urllib.error

spec = importlib.util.spec_from_file_location('maintenance', Path(__file__).with_name('cloud-maintenance.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def validate_seed_source(state, data, digest):
    if digest != state.get('baselineSha256'):
        raise ValueError('Seeded snapshot checksum mismatch')
    if data.get('baseUrl') != m.BASE or len(data.get('users', [])) < 1000 or len(data.get('events', [])) < 100:
        raise ValueError('Require the cloud dataset with 1000 accounts and 100 events')


def healthy_window(points, fault, end, operations):
    """Earliest post-fault 30-second business window meeting per-operation SLOs."""
    for offset in range(61):
        start = fault + offset
        if start + 30 > end:
            break
        selected = [p for p in points if start <= p['time'] < start + 30]
        errors = [p['error'] for p in selected if p['error'] is not None]
        if not errors or sum(errors) / len(errors) >= .01:
            continue
        ok = True
        for operation in operations:
            samples = sorted(p['durationMs'] for p in selected if p['operation'] == operation and p['durationMs'] is not None)
            operation_errors = [p['error'] for p in selected if p['operation'] == operation and p['error'] is not None]
            if not samples or not operation_errors or samples[min(len(samples) - 1, int(.95 * len(samples)))] >= 3000:
                ok = False
        if ok:
            return offset
    return None


def load_points(path):
    points = []
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('type') != 'Point' or row['data'].get('tags', {}).get('scenario') != 'measurement':
                continue
            data = row['data']
            point = {'time': dt.datetime.fromisoformat(data['time'].replace('Z', '+00:00')).timestamp(),
                     'operation': data['tags'].get('operation')}
            if row['metric'] == 'operation_duration':
                points.append({**point, 'durationMs': data['value'], 'error': None})
            elif row['metric'] == 'unexpected_error_rate':
                points.append({**point, 'durationMs': None, 'error': data['value']})
    return points


class Recovery(m.Maintenance):
    def seed(self):
        source = Path(self.args.dataset_source).resolve()
        source_state = json.loads((source / 'state.json').read_text())
        baseline = source / 'baseline.dump'
        if hashlib.sha256(baseline.read_bytes()).hexdigest() != source_state['baselineSha256']:
            raise ValueError('Seeded snapshot checksum mismatch')
        self.guard()
        self.scale(dict.fromkeys(m.BACKENDS, 0)); self.ready(dict.fromkeys(m.BACKENDS, 0))
        self.k('exec', '-i', 'postgres-0', '--', 'pg_restore', '-U', 'postgres', '-d', self.state['testDatabase'],
               '--clean', '--if-exists', '--exit-on-error', input=baseline.read_bytes(), timeout=300)
        shutil.copy2(baseline, self.out / 'baseline.dump')
        shutil.copy2(source / 'dataset.json', self.out / 'dataset.json')
        self.scale({s: 2 for s in m.BACKENDS}); self.ready({s: 2 for s in m.BACKENDS})
        self.state['baselineSha256'] = source_state['baselineSha256']
        self.state['phase'] = 'seeded'; self.state_save()

    def contention(self):
        """100 distinct accounts compete for 10 real API-created places."""
        target = self.out / 'contested-inventory'; target.mkdir()
        counts = {'identity': 1, 'event-catalog': 1, 'admission': 2}
        self.reset(counts); self.refresh(100); self.guard()
        data = json.loads((self.out / 'dataset.json').read_text())
        organizer = data['users'][0]['token']
        start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
        event = self.api('POST', '/api/v1/organizer/events', {
            'organizationId': data['organizationId'], 'visibility': 'PUBLIC',
            'title': 'Contention ' + self.state['runId'], 'description': 'Temporary maintenance validation',
            'location': 'Validation', 'startsAt': start.isoformat(),
            'endsAt': (start + dt.timedelta(hours=2)).isoformat(), 'capacity': 10}, organizer)
        path = '/api/v1/organizer/events/' + event['id']
        tickets = self.api('PUT', path + '/ticket-types', {'eventVersion': event['version'], 'version': 0,
            'ticketTypes': [{'name': 'Ten places', 'quota': 10,
             'opensAt': (start - dt.timedelta(days=8)).isoformat(), 'closesAt': start.isoformat()}]}, organizer)
        event = self.api('GET', path, token=organizer)
        published = self.api('POST', path + '/publish', {'version': event['version'], 'ticketVersion': tickets['version']}, organizer)
        if published['status'] != 'PUBLISHED': raise RuntimeError('Contention fixture was not published')
        hot = {'eventId': event['id'], 'ticketTypeId': tickets['ticketTypes'][0]['id'], 'quota': 10}
        pods = [p['metadata']['name'] for p in self.pods() if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == 'admission']
        for pod in pods:
            self.k('exec', pod, '--', 'sh', '-ec', 'for f in /tmp/sems-access/*; do : > "$f"; done')
        barrier = threading.Barrier(100)

        def book(index):
            key = str(uuid.uuid4()); barrier.wait(timeout=30)
            begin = time.monotonic()
            try:
                order = self.api('POST', '/api/v1/bookings', {**{k: hot[k] for k in ('eventId', 'ticketTypeId')},
                    'quantity': 1, 'requestKey': key}, data['users'][index]['token'])
                return {'status': 200, 'id': order['id'], 'key': key,
                        'valid': order.get('status') == 'CONFIRMED' and len(order.get('tickets', [])) == 1,
                        'durationMs': (time.monotonic() - begin) * 1000}
            except urllib.error.HTTPError as error:
                try:
                    value = json.load(error)
                except (ValueError, OSError):
                    value = {}
                return {'status': error.code, 'key': key, 'valid': error.code == 409 and
                        any(s in value.get('detail', '').lower() for s in ('quota', 'not enough', 'insufficient', 'sold out')),
                        'durationMs': (time.monotonic() - begin) * 1000}
            except Exception as error:
                return {'status': 0, 'key': key, 'valid': False, 'error': type(error).__name__}

        self.resources_ok(self.sample())
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            responses = list(executor.map(book, range(100)))
        m.save(target / 'responses.json', responses)
        inventory = json.loads(self.sql(m.shared.inventory_query({'events': [hot]}), self.state['testDatabase']))
        traffic = {pod: m.shared.traffic_counts(self.k('exec', pod, '--', 'sh', '-c', 'cat /tmp/sems-access/*').decode(), 'booking') for pod in pods}
        successes = sum(r['status'] == 200 for r in responses)
        rejected = sum(r['status'] == 409 for r in responses)
        result = {'requests': 100, 'availablePlaces': 10, 'successfulBookings': successes,
                  'soldOutResponses': rejected, 'validResponses': all(r['valid'] for r in responses),
                  'distinctAcknowledgedBookings': len({r.get('id') for r in responses if r['status'] == 200}),
                  'inventory': inventory, 'trafficByAdmissionPod': traffic}
        result['passed'] = (successes == 10 and rejected == 90 and result['validResponses'] and
                            result['distinctAcknowledgedBookings'] == 10 and m.shared.inventory_passed(inventory, 1) and
                            inventory[0]['reserved'] == 10 and len(traffic) == 2 and all(sum(v.values()) > 0 for v in traffic.values()))
        m.save(target / 'result.json', result); self.state['trials'].append(result); self.state_save()
        print(m.now(), 'Contested inventory', json.dumps(result), flush=True)
        if not result['passed']: raise RuntimeError('Contested inventory did not pass')

    def recovery(self, service):
        mode = 'catalog' if service == 'event-catalog' else 'booking'
        counts = dict.fromkeys(m.BACKENDS, 1); counts[service] = 2
        target = self.out / (service + '-failure'); target.mkdir()
        self.reset(counts); self.refresh(25); self.guard()
        initial = self.pods(); mapping = m.shared.Experiment.pod_map(self, initial)
        m.save(target / 'initial-pods.json', mapping)
        victim = next(p for p in initial if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == service)
        gateways = [p['metadata']['name'] for p in initial if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == 'gateway']
        for pod in gateways:
            self.k('exec', pod, '--', 'sh', '-ec', ': > /tmp/sems-maintenance/access.jsonl; : > /tmp/sems-maintenance/error.log')
        data = json.loads((self.out / 'dataset.json').read_text())
        stop, mutex = threading.Event(), threading.Lock()
        probes, attempts, committed, failures = [], {}, {}, []

        def call(method, path, body, user, operation):
            start = time.time(); result = None
            try:
                result = self.api(method, path, body, user['token'])
                if (not isinstance(result, dict) or not isinstance(result.get('id'), str)
                        or result.get('status') != 'CONFIRMED' or len(result.get('tickets', [])) != 1
                        or result['tickets'][0].get('state') != 'VALID'):
                    with mutex:
                        failures.append('unexpected successful booking response')
                    result = None
            except Exception:
                pass
            with mutex:
                probes.append({'time': time.time(), 'durationMs': (time.time() - start) * 1000,
                               'operation': operation, 'error': result is None})
            return result

        def probe(index):
            user, iteration = data['users'][index], 0
            while not stop.is_set():
                event = data['events'][(iteration * 3 + index) % len(data['events'])]
                key = str(uuid.uuid4())
                body = {'eventId': event['eventId'], 'ticketTypeId': event['ticketTypeId'], 'quantity': 1, 'requestKey': key}
                with mutex:
                    attempts[key] = user['id']
                order = None
                for _ in range(10):
                    order = call('POST', '/api/v1/bookings', body, user, 'book')
                    if order is not None or stop.is_set():
                        break
                    stop.wait(.3)
                if order and order.get('id'):
                    with mutex:
                        committed[order['id']] = key
                    replay = call('POST', '/api/v1/bookings', body, user, 'replay')
                    receipt = call('GET', '/api/v1/bookings/' + order['id'], None, user, 'receipt')
                    if replay and replay.get('id') != order['id']:
                        with mutex:
                            failures.append('same-key replay returned a different booking')
                    if receipt and (receipt.get('id') != order['id'] or receipt.get('status') != 'CONFIRMED'):
                        with mutex:
                            failures.append('committed booking receipt mismatch')
                iteration += 1; stop.wait(.2)

        run = self.state['runId'] + '-' + service + '-failure'
        values = {'DATASET': '/input/dataset.json', 'MODE': mode, 'VUS': '25', 'RUN_ID': run,
                  'WARMUP_SECONDS': '10', 'DURATION_SECONDS': '150', 'THINK_SECONDS': '.1',
                  'SUMMARY_FILE': '/out/summary.json', 'SEMS_MAINTENANCE_TOKEN': self.state['maintenanceToken'],
                  'COMMIT': '5e9081a9f5421fa5bdbd965d750641f3666dd5f3', 'REPLICAS': json.dumps(counts)}
        command = ['docker', 'run', '--rm', '--pull', 'never', '--name', self.load_name, '--cpus=2', '--memory=1g',
                   '-v', str(Path(__file__).parent) + ':/src:ro', '-v', str(self.out / 'dataset.json') + ':/input/dataset.json:ro',
                   '-v', str(target) + ':/out']
        for key, value in values.items():
            command += ['-e', key + '=' + value]
        command += ['grafana/k6:1.3.0', 'run', '--quiet', '--out', 'json=/out/raw.json', '/src/load.js']
        threads = [threading.Thread(target=probe, args=(i,)) for i in range(3)]
        fault_at, replacement_at, previous, invalid, exit_code = None, None, None, None, None
        traffic_before_fault = {}
        started = time.monotonic()
        print(m.now(), 'Running failure trial', service, flush=True)
        try:
            with (target / 'load.log').open('w') as log, (target / 'resources.jsonl').open('w') as samples:
                self.active = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                for thread in threads:
                    thread.start()
                while self.active.poll() is None:
                    sample = self.sample(); samples.write(json.dumps(sample) + '\n'); samples.flush()
                    m.shared.check_sample_continuity(previous, sample['time']); previous = sample['time']
                    self.resources_ok(sample)
                    current = m.shared.Experiment.pod_map(self, self.pods())
                    if any(current.get(pod) != details for pod, details in mapping.items() if pod != victim['metadata']['name']):
                        raise RuntimeError('A non-victim Pod changed during the recovery trial')
                    if fault_at is None and time.monotonic() - started >= 30:
                        self.guard()
                        for pod, info in mapping.items():
                            if info['service'] == service:
                                traffic_before_fault[pod] = m.shared.traffic_counts(
                                    self.k('exec', pod, '--', 'sh', '-c', 'cat /tmp/sems-access/*').decode(), mode)
                        m.save(target / 'traffic-before-fault.json', traffic_before_fault)
                        if len(traffic_before_fault) != 2 or not all(sum(v.values()) > 0 for v in traffic_before_fault.values()):
                            raise RuntimeError('Both replicas must serve business traffic before the fault')
                        fault_at = time.time()
                        self.k('delete', 'pod', victim['metadata']['name'], '--grace-period=0', '--force', '--wait=false')
                    elif fault_at is not None and replacement_at is None:
                        candidates = [p for p in self.pods() if p['metadata'].get('labels', {}).get('app.kubernetes.io/name') == service
                                      and p['metadata']['uid'] != victim['metadata']['uid'] and p['metadata']['name'] not in mapping]
                        if any(any(c['type'] == 'Ready' and c['status'] == 'True' for c in p.get('status', {}).get('conditions', [])) for p in candidates):
                            replacement_at = time.time()
                    if time.monotonic() - started > 270:
                        raise RuntimeError('Recovery load deadline exceeded')
                    time.sleep(5)
                exit_code = self.active.returncode
        except BaseException as error:
            invalid = str(error)
        finally:
            self.stop_load(); stop.set()
            for thread in threads:
                if thread.is_alive(): thread.join(timeout=60)
        finished = time.time()
        self.ready(counts); self.guard()
        if fault_at is not None and replacement_at is None:
            replacement_at = time.time()  # Upper bound after the final readiness wait.
        m.save(target / 'probe-operations.json', probes)
        m.save(target / 'probe-attempts.json', {'requestKeysAndUsers': attempts, 'acknowledgedIdsAndKeys': committed, 'failures': failures})
        keys = ','.join("'" + str(uuid.UUID(k)) + "'" for k in attempts)
        rows = json.loads(self.sql("SELECT coalesce(json_agg(row_to_json(x)),'[]'::json) FROM "
            "(SELECT id,user_id,request_key,status FROM admission.bookings WHERE request_key IN (" + keys + ')) x', self.state['testDatabase'])) if keys else []
        persisted = {r['id'] for r in rows}
        if any(r['status'] != 'CONFIRMED' for r in rows):
            failures.append('a recovery probe booking lost its confirmed state')
        lost = sorted(set(committed) - persisted)
        duplicates = len(rows) - len({(r['user_id'], r['request_key']) for r in rows})
        inventory = json.loads(self.sql(m.shared.inventory_query(data), self.state['testDatabase']))
        audit_ok = m.shared.inventory_passed(inventory, len(data['events']))
        m.save(target / 'inventory.json', {'passed': audit_ok, 'inventory': inventory})
        with (target / 'gateway.jsonl').open('wb') as stream:
            for pod in gateways: stream.write(self.k('exec', pod, '--', 'cat', '/tmp/sems-maintenance/access.jsonl', timeout=180))
        with (target / 'gateway-error.log').open('wb') as stream:
            for pod in gateways: stream.write(self.k('exec', pod, '--', 'cat', '/tmp/sems-maintenance/error.log'))
        summary = json.loads((target / 'summary.json').read_text()) if (target / 'summary.json').exists() else {}
        values = summary.get('metrics', {}).get('unexpected_error_rate{scenario:measurement}', {}).get('values', {})
        expected = values.get('passes', 0) + values.get('fails', 0)
        with (target / 'gateway.jsonl').open() as stream:
            evidence = m.shared.gateway_evidence(stream, run, expected)
        m.save(target / 'gateway-evidence.json', evidence)
        points = load_points(target / 'raw.json') if (target / 'raw.json').exists() else []
        errors = [p['error'] for p in points if p['error'] is not None]
        rejection = summary.get('metrics', {}).get('business_rejection_rate{scenario:measurement}', {}).get('values', {}).get('rate', 0)
        if rejection:
            invalid = 'Unexpected business rejection with ample fixture inventory'
        rto = healthy_window(points, fault_at, finished, ('list', 'detail') if mode == 'catalog' else ('book', 'receipt')) if fault_at else None
        probe_rto = healthy_window(probes, fault_at, finished, ('book', 'replay', 'receipt')) if fault_at else None
        result = {'service': service, 'loadVUs': 25, 'additionalBookingWorkers': 3, 'loadExitCode': exit_code,
                  'faultAtEpoch': fault_at, 'replacementReadySeconds': replacement_at - fault_at if replacement_at and fault_at else None,
                  'businessHealthyWindowStartSeconds': rto, 'probeHealthyWindowStartSeconds': probe_rto,
                  'healthyWindowSeconds': 30, 'acknowledgedProbeBookings': len(committed), 'lostAcknowledgedBookings': len(lost),
                  'duplicateProbeBookings': duplicates, 'probeConsistencyFailures': failures, 'inventoryPassed': audit_ok,
                  'gatewayMeasurementCoveragePassed': evidence['measurementCoveragePassed'],
                  'measurementUnexpectedErrors': sum(errors), 'measurementRequests': len(errors),
                  'probeUnexpectedErrors': sum(p['error'] for p in probes),
                  'bothReplicasServedBeforeFault': len(traffic_before_fault) == 2 and all(sum(v.values()) > 0 for v in traffic_before_fault.values()),
                  'invalidReason': invalid, 'note': 'Single controlled Pod-failure sample; transient errors and masked upstream retries are retained. Not host or database HA.'}
        result['passed'] = invalid is None and exit_code in (0, 99) and rto is not None and rto <= 60 and probe_rto is not None and probe_rto <= 60 and not lost and not duplicates and not failures and audit_ok and evidence['measurementCoveragePassed']
        m.save(target / 'result.json', result)
        self.state['trials'].append(result); self.state_save()
        print(m.now(), 'Completed failure trial', json.dumps(result), flush=True)
        if not result['passed']:
            raise RuntimeError('Recovery trial did not pass: ' + service)

    def execute(self):
        source = Path(self.args.dataset_source).resolve()
        source_state = json.loads((source / 'state.json').read_text())
        validate_seed_source(source_state, json.loads((source / 'dataset.json').read_text()),
                             hashlib.sha256((source / 'baseline.dump').read_bytes()).hexdigest())
        for name in m.SERVICES:
            old_image = source_state['deployments'][name]['spec']['template']['spec']['containers'][0]['image']
            if old_image != self.state['deployments'][name]['spec']['template']['spec']['containers'][0]['image']:
                raise ValueError('Application image changed since the seeded snapshot')
        self.acquire_lock()
        try:
            self.prepare(); self.seed()
            self.contention()
            for service in ('event-catalog', 'admission'):
                self.recovery(service)
            self.state['executionStatus'] = 'recovery-complete'; self.state_save()
        except BaseException as error:
            self.state['executionStatus'] = 'stopped'; self.state['executionError'] = str(error); self.state_save()
            raise
        finally:
            try:
                self.restore()
            finally:
                if self.lock: self.lock.stdin.close(); self.lock.wait(timeout=15)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True); p.add_argument('--dataset-source', required=True)
    p.add_argument('--maintenance-window', action='store_true')
    args = p.parse_args()
    if not args.maintenance_window: p.error('Explicit --maintenance-window authorization is required')
    m.os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit('Terminated; restore original service')))
    driver = Recovery(args)
    if not driver.state: driver.capture()
    if driver.state['phase'] != 'captured': p.error('Require a fresh original baseline')
    driver.execute()
