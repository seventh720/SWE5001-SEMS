#!/usr/bin/env python3
"""Real HTTPS booking/replay/receipt traffic during Catalog Pod loss on K3s.

No Docker daemon or container topology assumptions. Do not run concurrently with
other fault-injection suites. Only sems-k3s/sems-test is supported.
"""
import argparse
from collections import Counter
import concurrent.futures
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://sems-test.seventh720.com'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    try:
        import certifi
    except ImportError:
        pass
    else:
        os.environ['SSL_CERT_FILE'] = certifi.where()
    secrets = load('sems_secrets', ROOT / 'scripts/k8s/secrets.py')
    env = secrets.read_env(args.env_file)
    for key in ('SEMS_BOOTSTRAP_ADMIN_EMAIL', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD'):
        os.environ[key] = env[key]
    os.environ['SEMS_BASE_URL'] = BASE
    adapter = load('k3s_runtime', ROOT / 'scripts/k8s/business-regression.py')
    runtime = adapter.KubernetesRuntime(args.kubeconfig)
    report = {'startedAt': adapter.now(), 'environment': 'sems-k3s/sems-test', 'baseUrl': BASE,
              'status': 'running', 'tests': []}
    stage = 'fixture and initial readiness'

    def api(method, path, token=None, body=None):
        request = urllib.request.Request(BASE + path, method=method,
            headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})},
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, {}
        except OSError:
            return 0, {}

    def pods(service):
        return json.loads(runtime.command('get', 'pods', '-l', 'app.kubernetes.io/name=' + service, '-o', 'json'))['items']

    def wait_two(excluded=None):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            items = pods('event-catalog')
            if len(items) == 2 and all(not p['metadata'].get('deletionTimestamp') and
                p['metadata']['uid'] != excluded and any(c['type'] == 'Ready' and c['status'] == 'True'
                for c in p['status'].get('conditions', [])) for p in items):
                return items
            time.sleep(1)
        raise RuntimeError('Two Catalog Pods did not recover')

    def sql(query):
        return runtime.command('exec', 'postgres-0', '--', 'psql', '-v', 'ON_ERROR_STOP=1',
                               '-U', 'postgres', '-d', 'sems', '-Atq', '-c', query)

    def passed(name, **details):
        report['tests'].append({'name': name, 'status': 'passed', **details})
        print('PASS: ' + name, flush=True)

    try:
        runtime.snapshot()
        initial = wait_two()
        baseline = {name: sorted(p['metadata']['uid'] for p in pods(name)) for name in ('identity', 'admission', 'gateway')}
        sys.path.insert(0, str(ROOT / 'scripts'))
        fixture = runpy.run_path(str(ROOT / 'scripts/acceptance.py'))
        call, owner, attendee = (fixture[key] for key in ('call', 'a', 'attendee'))
        starts = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
        event = call('POST', '/api/v1/organizer/events', {**fixture['body'],
            'title': 'K3s cold restart ' + fixture['suffix'], 'capacity': 10000,
            'startsAt': starts.isoformat(), 'endsAt': (starts + dt.timedelta(hours=2)).isoformat()}, owner, 201)
        path = '/api/v1/organizer/events/' + event['id']
        inventory = call('PUT', path + '/ticket-types', {'eventVersion': event['version'], 'version': 0,
            'ticketTypes': [{'name': 'General', 'quota': 10000,
                'opensAt': (starts - dt.timedelta(days=8)).isoformat(), 'closesAt': starts.isoformat()}]}, owner)
        event = call('GET', path, token=owner)
        assert call('POST', path + '/publish', {'version': event['version'], 'ticketVersion': inventory['version']}, owner)['status'] == 'PUBLISHED'
        ticket = inventory['ticketTypes'][0]
        report['fixtures'] = {'organizationId': fixture['org_a']['id'], 'eventId': event['id'],
                              'ticketTypeId': ticket['id'], 'title': event['title']}

        def payload():
            return {'eventId': event['id'], 'ticketTypeId': ticket['id'], 'quantity': 1, 'requestKey': str(uuid.uuid4())}

        stage = 'internal API boundaries'
        assert api('GET', '/internal/v1/events/' + event['id'] + '/published')[0] == 404
        unauth = subprocess.run(runtime.k + ['exec', 'deployment/gateway', '--', 'wget', '-S', '-O', '/dev/null',
            'http://127.0.0.1:8080/internal/v1/events/' + event['id'] + '/published'], capture_output=True, text=True, timeout=15)
        assert '401' in unauth.stderr or '403' in unauth.stderr
        passed(stage, publicStatus=404, internalUnauthenticatedDenied=True)

        stage = 'booking, same-key replay and live receipt during one Catalog Pod deletion'
        failures, completed, statuses = [], [], Counter()
        victim = initial[-1]
        report['deletedPod'] = {'name': victim['metadata']['name'], 'uid': victim['metadata']['uid'], 'node': victim['spec']['nodeName']}

        def worker():
            deadline = time.monotonic() + 75
            while time.monotonic() < deadline:
                request = payload()
                code, booking = api('POST', '/api/v1/bookings', attendee, request)
                statuses[code] += 1
                if code != 200:
                    failures.append({'operation': 'booking', 'status': code})
                    time.sleep(.1)
                    continue
                code, replay = api('POST', '/api/v1/bookings', attendee, request)
                if code != 200 or replay.get('id') != booking['id']:
                    failures.append({'operation': 'same-key replay', 'status': code})
                code, receipt = api('GET', '/api/v1/bookings/' + booking['id'], attendee)
                if code != 200 or receipt.get('currentEvent') is None:
                    failures.append({'operation': 'live receipt', 'status': code})
                completed.append(booking['id'])
                time.sleep(.1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(worker) for _ in range(3)]
            time.sleep(8)
            deleted_at = time.monotonic()
            # Forceful Pod loss models the abrupt process failure from the old test.
            runtime.command('delete', 'pod', victim['metadata']['name'], '--grace-period=0', '--force', '--wait=false')
            replacement = wait_two(victim['metadata']['uid'])
            recovery_seconds = round(time.monotonic() - deleted_at, 3)
            for future in futures:
                future.result()
        report['traffic'] = {'durationSeconds': 75, 'workers': 3, 'completedBookings': len(completed),
            'statusCounts': dict(statuses), 'failedOperations': failures,
            'replacementReadySeconds': recovery_seconds}
        assert completed and not failures, 'Request failures=' + str(failures[:10])
        assert all(sorted(p['metadata']['uid'] for p in pods(name)) == before for name, before in baseline.items()), 'Other services unexpectedly restarted'
        passed(stage, **report['traffic'], otherServicesUnchanged=True,
               replacementPodUids=[p['metadata']['uid'] for p in replacement])

        stage = 'all Catalog replicas down: bounded failure and same-key recovery'
        try:
            runtime.scale('event-catalog', 0)
            # Allow the headless DNS cache (valid=5s) to expire after endpoint removal.
            time.sleep(6)
            request = payload()
            began = time.monotonic()
            code, _ = api('POST', '/api/v1/bookings', attendee, request)
            seconds = round(time.monotonic() - began, 3)
            assert code == 503 and seconds < 8, 'Expected bounded 503; got ' + str(code) + ' in ' + str(seconds)
        finally:
            runtime.scale('event-catalog', 2)
        wait_two()
        # Check autonomous DNS/client recovery without a Gateway restart.
        time.sleep(6)
        code, booking = api('POST', '/api/v1/bookings', attendee, request)
        again, replay = api('POST', '/api/v1/bookings', attendee, request)
        assert code == again == 200 and booking['id'] == replay['id'], 'Same-key recovery failed'
        passed(stage, unavailableStatus=503, unavailableSeconds=seconds, recoveryStatus=200,
               distinctRecoveredBookings=1, gatewayRestarted=False)

        stage = 'persisted inventory and idempotency audit'
        audit = sql(f"SELECT t.reserved,(SELECT coalesce(sum(b.quantity),0) FROM admission.bookings b WHERE b.ticket_type_id=t.id AND b.status='CONFIRMED'),(SELECT count(*) FROM admission.tickets k JOIN admission.bookings b ON b.id=k.booking_id WHERE b.ticket_type_id=t.id AND k.state='VALID'),(SELECT count(*)-count(DISTINCT request_key) FROM admission.bookings b WHERE b.ticket_type_id=t.id) FROM admission.ticket_types t WHERE t.id='{ticket['id']}'")
        values = list(map(int, audit.split('|')))
        assert values[:3] == [len(completed) + 1] * 3 and values[3] == 0, audit
        passed(stage, reserved=values[0], confirmedQuantity=values[1], validTickets=values[2], duplicateRequestKeys=0)
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['tests'].append({'name': stage, 'status': 'failed', 'error': str(error)})
        print('FAIL: ' + stage + ': ' + str(error), flush=True)
    finally:
        try:
            runtime.restore()
            report['replicasRestored'] = True
        except Exception as error:
            report['status'] = 'failed'
            report['cleanupError'] = str(error)
        report['completedAt'] = adapter.now()
        adapter.save(args.report, report)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
