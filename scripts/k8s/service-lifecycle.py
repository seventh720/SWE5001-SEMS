#!/usr/bin/env python3
"""Exercise Admission-only scaling and Pod replacement in the sems-k3s test cluster."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import threading
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig', required=True)
parser.add_argument('--report', required=True)
args = parser.parse_args()
k = ['kubectl', '--kubeconfig', args.kubeconfig, '--context', 'sems-k3s',
     '--cache-dir', '.secrets/k3s-cloud/cache', '-n', 'sems-test']
report = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'environment': 'sems-k3s/sems-test', 'status': 'running', 'tests': []}
stop = threading.Event()
samples = []


def command(*args):
    return subprocess.check_output(k + list(args), text=True, timeout=60).strip()


def pods(service):
    return json.loads(command('get', 'pods', '-l', 'app.kubernetes.io/name=' + service, '-o', 'json'))['items']


def ready(items):
    return all(not p['metadata'].get('deletionTimestamp') and any(
        c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', [])) for p in items)


def wait_for(count, exclude_uid=None):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        items = pods('admission')
        if len(items) == count and ready(items) and all(p['metadata']['uid'] != exclude_uid for p in items):
            return items
        time.sleep(1)
    raise RuntimeError('Admission did not reach ' + str(count) + ' ready replicas within 180 seconds')


def identities(service):
    return sorted(p['metadata']['uid'] for p in pods(service))


def audit():
    return command('exec', 'postgres-0', '--', 'psql', '-U', 'postgres', '-d', 'sems', '-Atq', '-c',
                   'SELECT (SELECT count(*) FROM admission.bookings),(SELECT count(*) FROM admission.tickets)')


def monitor():
    paths = ('/', '/health/identity', '/health/event-catalog', '/health/admission', '/api/v1/events?size=5')
    while not stop.is_set():
        for path in paths:
            process = subprocess.run(['curl', '--silent', '--show-error', '--max-time', '5',
                                      '--output', '/dev/null', '--write-out', '%{http_code}',
                                      'https://sems-test.seventh720.com' + path],
                                     capture_output=True, text=True, timeout=10)
            samples.append({'at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            'path': path, 'status': process.stdout.strip(), 'exit': process.returncode})
        stop.wait(1)


thread = threading.Thread(target=monitor, daemon=True)
stage = 'initial state'
try:
    initial = wait_for(2)
    baseline = {name: identities(name) for name in ('identity', 'event-catalog')}
    before = audit()
    report['baselineOtherServicePodUids'] = baseline
    report['baselineAdmissionPodUids'] = [p['metadata']['uid'] for p in initial]
    thread.start()

    stage = 'Admission independently scales from two to one'
    command('scale', 'deployment/admission', '--replicas=1')
    wait_for(1)
    assert all(identities(name) == baseline[name] for name in baseline)
    report['tests'].append({'name': stage, 'status': 'passed'})
    print('PASS ' + stage, flush=True)

    stage = 'Admission independently scales from one to two'
    command('scale', 'deployment/admission', '--replicas=2')
    expanded = wait_for(2)
    assert len({p['spec']['nodeName'] for p in expanded}) == 2
    assert all(identities(name) == baseline[name] for name in baseline)
    report['tests'].append({'name': stage, 'status': 'passed',
                            'nodes': [p['spec']['nodeName'] for p in expanded]})
    print('PASS ' + stage, flush=True)

    stage = 'one Admission Pod is recreated without restarting other services'
    victim = expanded[0]
    started = time.monotonic()
    command('delete', 'pod', victim['metadata']['name'], '--wait=false')
    restored = wait_for(2, victim['metadata']['uid'])
    duration = round(time.monotonic() - started, 3)
    assert all(identities(name) == baseline[name] for name in baseline)
    assert audit() == before
    report['tests'].append({'name': stage, 'status': 'passed', 'observedReplacementReadySeconds': duration,
                            'deletedPodUid': victim['metadata']['uid'],
                            'finalAdmissionPodUids': [p['metadata']['uid'] for p in restored],
                            'bookingAndTicketCountsPreserved': True})
    print('PASS ' + stage, flush=True)
    report['status'] = 'passed'
except Exception as error:
    report['status'] = 'failed'
    report['tests'].append({'name': stage, 'status': 'failed', 'error': str(error)})
    print('FAIL ' + stage + ': ' + str(error), flush=True)
finally:
    stop.set()
    if thread.is_alive():
        thread.join(timeout=60)
    try:
        command('scale', 'deployment/admission', '--replicas=2')
        wait_for(2)
    except Exception as error:
        report['cleanupError'] = str(error)
    report['httpSamples'] = samples
    report['httpFailures'] = [s for s in samples if s['exit'] != 0 or s['status'] != '200']
    if report['httpFailures']:
        report['status'] = 'failed'
    report['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')

if report['status'] != 'passed' or report.get('cleanupError'):
    raise SystemExit(1)
