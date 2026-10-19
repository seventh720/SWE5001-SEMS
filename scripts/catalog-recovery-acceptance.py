#!/usr/bin/env python3
"""Disposable-stack regression: booking survives a Catalog replica cold restart.

Creates private test data, temporarily scales Catalog to two replicas and restores
its original count. Also verifies bounded failure when ALL Catalog replicas stop.
"""
import concurrent.futures
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('seed', ROOT / 'scripts/performance/seed.py')
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)
base = os.environ.get('SEMS_BASE_URL', 'http://localhost:18080').rstrip('/')
compose = ['docker', 'compose', '--env-file', os.environ.get('SEMS_ENV_FILE', '.env')]
for path in os.environ.get('SEMS_COMPOSE_FILE', 'deployment/compose.yaml').split(os.pathsep):
    compose += ['-f', path]


def command(*args):
    return subprocess.check_output(compose + list(args), text=True).strip()


def replicas():
    return command('ps', '-q', 'event-catalog').split()


def ready():
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        ok = True
        for cid in replicas():
            ip = subprocess.check_output(['docker', 'inspect', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', cid], text=True).strip()
            probe = subprocess.run(compose + ['exec', '-T', 'gateway', 'wget', '-qO-', '-T', '2', f'http://{ip}:8082/actuator/health/readiness'], capture_output=True, text=True)
            try:
                ok = ok and probe.returncode == 0 and json.loads(probe.stdout)['status'] == 'UP'
            except (ValueError, KeyError):
                ok = False
        if ok and replicas():
            time.sleep(6)
            return
        time.sleep(1)
    raise AssertionError('Catalog did not become ready')


def api(method, path, token=None, body=None):
    request = urllib.request.Request(base + path, method=method,
        headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, {}
    except OSError:
        return 0, {}


def main():
    original = len(replicas())
    assert original > 0, 'Start a disposable stack first'
    failures, completed, attempts = [], [], []
    stopped = []
    try:
        command('up', '-d', '--no-deps', '--no-recreate', '--scale', 'event-catalog=2', 'event-catalog')
        ready()
        with tempfile.TemporaryDirectory(prefix='sems-catalog-recovery-') as temp:
            dataset = str(Path(temp) / 'dataset.json')
            subprocess.run(['python3', str(ROOT / 'scripts/performance/seed.py'), '--base-url', base,
                '--users', '2', '--events', '2', '--output', dataset], check=True, stdout=subprocess.DEVNULL)
            data = json.loads(Path(dataset).read_text())
            event = data['events'][0]
            token = data['users'][0]['token']
            assert api('GET', f"/internal/v1/events/{event['eventId']}/published")[0] == 404, 'Internal API leaked through public entry'
            # The internal listener still requires the service token at the destination.
            unauth = subprocess.run(compose + ['exec', '-T', 'gateway', 'wget', '-S', '-O', '/dev/null',
                f"http://127.0.0.1:8080/internal/v1/events/{event['eventId']}/published"], capture_output=True, text=True)
            assert '401' in unauth.stderr or '403' in unauth.stderr, 'Internal service authentication missing'

            def body():
                return {'eventId': event['eventId'], 'ticketTypeId': event['ticketTypeId'], 'quantity': 1, 'requestKey': str(uuid.uuid4())}

            def worker():
                deadline = time.monotonic() + 75
                while time.monotonic() < deadline:
                    request = body()
                    attempts.append(request)
                    status, booking = api('POST', '/api/v1/bookings', token, request)
                    if status != 200:
                        failures.append({'operation': 'book', 'status': status})
                        time.sleep(.1)
                        continue
                    code, replay = api('POST', '/api/v1/bookings', token, request)
                    if code != 200 or replay.get('id') != booking['id']:
                        failures.append({'operation': 'replay', 'status': code})
                    # Receipt exercises the read-only internal POST /events/details too.
                    code, receipt = api('GET', '/api/v1/bookings/' + booking['id'], token)
                    if code != 200 or receipt.get('currentEvent') is None:
                        failures.append({'operation': 'receipt', 'status': code})
                    completed.append(booking['id'])
                    time.sleep(.1)

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(worker) for _ in range(3)]
                time.sleep(8)
                stopped = [replicas()[-1]]
                subprocess.run(['docker', 'stop', '--time', '0', *stopped], check=True, stdout=subprocess.DEVNULL)
                time.sleep(15)
                subprocess.run(['docker', 'start', *stopped], check=True, stdout=subprocess.DEVNULL)
                stopped = []
                for future in futures:
                    future.result()
            ready()
            assert completed and not failures, f'Cold restart requests failed: {failures[:10]}; successful bookings={len(completed)}'
            # A legitimate failure remains bounded when no healthy Catalog exists.
            stopped = replicas()
            subprocess.run(['docker', 'stop', '--time', '0', *stopped], check=True, stdout=subprocess.DEVNULL)
            request = body()
            started = time.monotonic()
            code, _ = api('POST', '/api/v1/bookings', token, request)
            assert code == 503 and time.monotonic() - started < 8, f'Expected bounded 503, got {code}'
            subprocess.run(['docker', 'start', *stopped], check=True, stdout=subprocess.DEVNULL)
            stopped = []
            ready()
            code, recovered = api('POST', '/api/v1/bookings', token, request)
            code2, replay = api('POST', '/api/v1/bookings', token, request)
            assert code == code2 == 200 and recovered['id'] == replay['id'], 'Same-key recovery duplicated or lost booking'
            subprocess.run(['python3', str(ROOT / 'scripts/performance/audit.py'), '--dataset', dataset,
                '--output', str(Path(temp) / 'audit.json')], check=True)
            print(f'PASS: {len(completed)} bookings plus same-key replays and live receipts survived Catalog stop/cold restart without failure')
            print('PASS: public internal paths denied; internal listener authenticated; all-replicas-down fails boundedly and same-key recovery succeeds')
    finally:
        if stopped:
            subprocess.run(['docker', 'start', *stopped], check=True, stdout=subprocess.DEVNULL)
        command('up', '-d', '--no-deps', '--no-recreate', '--scale', f'event-catalog={original}', 'event-catalog')
        ready()


if __name__ == '__main__':
    main()
