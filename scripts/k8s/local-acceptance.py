#!/usr/bin/env python3
"""Verify two Admission Pods in an explicitly selected local or K3s test environment."""
import argparse
from collections import Counter
import concurrent.futures
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--kubeconfig', required=True)
parser.add_argument('--env-file', required=True)
parser.add_argument('--report', required=True)
parser.add_argument('--environment', choices=('local', 'k3s'), default='local')
args = parser.parse_args()
os.chdir(ROOT)
context, namespace, cache = (
    ('kind-sems-local', 'sems-local', '.secrets/k8s-local/cache') if args.environment == 'local'
    else ('sems-k3s', 'sems-test', '.secrets/k3s-cloud/cache'))
kubectl = ['kubectl', '--kubeconfig', str(Path(args.kubeconfig).resolve()),
           '--context', context, '--cache-dir', str(ROOT / cache), '-n', namespace]
report = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'environment': context + '/' + namespace, 'tests': [], 'status': 'running'}
forwarders = []
step = 'cluster and credentials'


def output(*arguments):
    return subprocess.check_output(kubectl + list(arguments), text=True, timeout=60).strip()


def sql(query):
    return output('exec', 'postgres-0', '--', 'psql', '-v', 'ON_ERROR_STOP=1',
                  '-U', 'postgres', '-d', 'sems', '-Atq', '-c', query)


def passed(name, **details):
    report['tests'].append({'name': name, 'status': 'passed', **details})
    print('PASS:', name, flush=True)


def forward(target, port):
    log = tempfile.TemporaryFile(mode='w+')
    process = subprocess.Popen(kubectl + ['port-forward', '--address', '127.0.0.1', target, ':' + str(port)],
                               stdout=log, stderr=subprocess.STDOUT, text=True)
    forwarders.append((process, log))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        log.seek(0)
        match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+)', log.read())
        if match:
            return 'http://127.0.0.1:' + match[1]
        if process.poll() is not None:
            raise RuntimeError('Port-forward failed for ' + target)
        time.sleep(.1)
    raise RuntimeError('Port-forward timed out for ' + target)


def request(base, method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read()
    try:
        value = json.loads(raw) if raw else None
    except json.JSONDecodeError:
        value = None
    return status, value


try:
    pods = json.loads(output('get', 'pods', '-l', 'app.kubernetes.io/name=admission', '-o', 'json'))['items']
    assert len(pods) == 2 and all(any(c['type'] == 'Ready' and c['status'] == 'True'
                                    for c in p['status']['conditions']) for p in pods), 'Need two ready Admission Pods'
    report['admissionPods'] = [p['metadata']['name'] for p in pods]
    report['admissionNodes'] = [p['spec']['nodeName'] for p in pods]
    if args.environment == 'k3s':
        assert len(set(report['admissionNodes'])) == 2, 'Cloud Admission replicas must run on different EC2 nodes'
    report['sourceCommit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    report['worktreeDirty'] = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True))
    rendered = subprocess.check_output(['kubectl', 'kustomize', 'deployment/k8s/overlays/' + args.environment])
    report['manifestSha256'] = hashlib.sha256(rendered).hexdigest()
    report['kubernetesVersion'] = json.loads(output('version', '-o', 'json'))['serverVersion']['gitVersion']
    all_pods = json.loads(output('get', 'pods', '-o', 'json'))['items']
    report['runtimeImages'] = {p['metadata']['name']: [c['imageID'] for c in p['status'].get('containerStatuses', [])]
                               for p in all_pods}
    spec = importlib.util.spec_from_file_location('k8s_secret_renderer', ROOT / 'scripts/k8s/secrets.py')
    secrets = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(secrets)
    env = secrets.read_env(args.env_file)
    for key in ('SEMS_BOOTSTRAP_ADMIN_EMAIL', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD'):
        os.environ[key] = env[key]
    gateway = forward('service/gateway', 80)
    admission_urls = [forward('pod/' + p['metadata']['name'], 8083) for p in pods]
    os.environ['SEMS_BASE_URL'] = gateway
    step = 'gateway and service readiness'
    assert request(gateway, 'GET', '/')[0] == 200
    for name in ('gateway', 'identity', 'event-catalog', 'admission'):
        assert request(gateway, 'GET', '/health/' + name)[0] == 200
    assert request(gateway, 'GET', '/internal/v1/events/details')[0] == 404
    passed(step)

    step = 'registration, login, organization permissions and draft concurrency'
    fixture = runpy.run_path('scripts/acceptance.py')
    call, owner, outsider, attendee = (fixture[key] for key in ('call', 'a', 'b', 'attendee'))
    passed(step)

    def offering(title, quota):
        now = datetime.datetime.now(datetime.timezone.utc)
        starts = now + datetime.timedelta(minutes=10)
        event = call('POST', '/api/v1/organizer/events', {
            **fixture['body'], 'title': title + ' ' + fixture['suffix'], 'capacity': quota,
            'startsAt': starts.isoformat(), 'endsAt': (starts + datetime.timedelta(hours=1)).isoformat(),
        }, owner, 201)
        path = '/api/v1/organizer/events/' + event['id']
        inventory = call('PUT', path + '/ticket-types', {
            'eventVersion': event['version'], 'version': 0,
            'ticketTypes': [{'name': 'General', 'quota': quota, 'opensAt': (now - datetime.timedelta(hours=1)).isoformat(),
                             'closesAt': starts.isoformat()}],
        }, owner)
        event = call('GET', path, token=owner)
        status, _ = request(gateway, 'POST', path + '/publish',
                            {'version': event['version'], 'ticketVersion': inventory['version']}, owner)
        assert status in (200, 202), 'Unexpected publication status: ' + str(status)
        for _ in range(30):
            event = call('GET', path, token=owner)
            if event['status'] == 'PUBLISHED':
                break
            time.sleep(1)
        assert event['status'] == 'PUBLISHED', 'Publication did not complete'
        assert call('GET', '/api/v1/events/' + event['id'])['id'] == event['id']
        return event, path, inventory['ticketTypes'][0]

    def booking_request(event, ticket, quantity=1):
        return {'eventId': event['id'], 'ticketTypeId': ticket['id'], 'quantity': quantity, 'requestKey': str(uuid.uuid4())}

    def compete(job):
        number, payload = job
        return request(admission_urls[number % 2], 'POST', '/api/v1/bookings', payload, attendee)

    step = 'publication, booking, private ownership and retry payload validation'
    replay_event, replay_path, replay_ticket = offering('Kubernetes retry', 4)
    initial_request = booking_request(replay_event, replay_ticket, 2)
    initial = call('POST', '/api/v1/bookings', initial_request, attendee)
    assert len(initial['tickets']) == 2
    assert call('POST', '/api/v1/bookings', initial_request, attendee)['id'] == initial['id']
    call('POST', '/api/v1/bookings', {**initial_request, 'quantity': 1}, attendee, 409)
    call('GET', '/api/v1/bookings/' + initial['id'], token=outsider, expected=404)
    passed(step)

    step = 'same request key across both Admission Pods'
    same_request = booking_request(replay_event, replay_ticket)
    with concurrent.futures.ThreadPoolExecutor(10) as pool:
        same = list(pool.map(compete, enumerate([same_request] * 20)))
    assert all(status == 200 for status, _ in same), str(Counter(status for status, _ in same))
    assert len({value['id'] for _, value in same}) == 1
    assert sql(f"SELECT reserved FROM admission.ticket_types WHERE id='{replay_ticket['id']}'") == '3'
    passed(step, requests=20, requestsPerPod=10, distinctBookings=1, reservedTotal=3)

    step = '100 distinct requests for ten places across both Admission Pods'
    race_event, race_path, race_ticket = offering('Kubernetes final ten places', 10)
    jobs = [booking_request(race_event, race_ticket) for _ in range(100)]
    with concurrent.futures.ThreadPoolExecutor(20) as pool:
        results = list(pool.map(compete, enumerate(jobs)))
    counts = Counter(status for status, _ in results)
    assert counts == {200: 10, 409: 90}, str(counts)
    winners = [value for status, value in results if status == 200]
    assert len({value['tickets'][0]['credential'] for value in winners}) == 10
    audit = sql(f"SELECT t.reserved,(SELECT sum(b.quantity) FROM admission.bookings b WHERE b.ticket_type_id=t.id AND b.status='CONFIRMED'),(SELECT count(*) FROM admission.tickets k JOIN admission.bookings b ON b.id=k.booking_id WHERE b.ticket_type_id=t.id AND k.state='VALID') FROM admission.ticket_types t WHERE t.id='{race_ticket['id']}'")
    assert audit == '10|10|10', audit
    passed(step, requests=100, requestsPerPod=50, statusCounts=dict(counts), inventoryAudit=audit)

    step = 'staff authorization and concurrent exactly-once check-in'
    credential = winners[0]['tickets'][0]['credential']
    check_path = '/api/v1/events/' + race_event['id'] + '/check-ins'
    call('POST', check_path, {'credential': credential}, owner, 403)
    call('PUT', race_path + '/staff', {'userId': fixture['users'][0]['id'], 'active': True}, owner, 204)
    with concurrent.futures.ThreadPoolExecutor(5) as pool:
        checked = list(pool.map(lambda n: request(admission_urls[n % 2], 'POST', check_path,
                                                 {'credential': credential}, owner), range(10)))
    assert all(status == 200 for status, _ in checked)
    assert sum(not value['alreadyCheckedIn'] for _, value in checked) == 1
    assert len({value['checkedInAt'] for _, value in checked}) == 1
    call('POST', '/api/v1/bookings/' + winners[0]['id'] + '/cancel', token=attendee, expected=409)
    passed(step, attempts=10, firstCheckIns=1)

    step = 'repeated personal cancellation releases inventory once'
    cancel_path = '/api/v1/bookings/' + initial['id'] + '/cancel'
    for _ in range(2):
        assert call('POST', cancel_path, token=attendee)['status'] == 'CANCELLED'
    assert sql(f"SELECT reserved FROM admission.ticket_types WHERE id='{replay_ticket['id']}'") == '1'
    passed(step, reservedAfterCancellation=1)

    step = 'whole-event cancellation preserves check-in history and closes inventory'
    current = call('GET', race_path, token=owner)
    cancellation = {'version': current['version'], 'reason': 'Kubernetes acceptance'}
    status, _ = request(gateway, 'POST', race_path + '/cancel', cancellation, owner)
    assert status in (200, 202)
    for _ in range(30):
        if call('GET', race_path, token=owner)['status'] == 'CANCELLED':
            break
        time.sleep(1)
    assert call('GET', race_path, token=owner)['status'] == 'CANCELLED'
    assert call('POST', race_path + '/cancel', cancellation, owner)['status'] == 'CANCELLED'
    event_id = race_event['id']
    audit = sql(f"SELECT (SELECT COALESCE(sum(reserved),0) FROM admission.ticket_types WHERE event_id='{event_id}'),(SELECT count(*) FROM admission.bookings WHERE event_id='{event_id}' AND status='CONFIRMED'),(SELECT count(*) FROM admission.tickets t JOIN admission.bookings b ON b.id=t.booking_id WHERE b.event_id='{event_id}' AND t.state='VALID'),(SELECT count(*) FROM admission.tickets t JOIN admission.bookings b ON b.id=t.booking_id WHERE b.event_id='{event_id}' AND t.state='CHECKED_IN'),(SELECT count(*) FROM admission.event_cancellation_receipts WHERE event_id='{event_id}')")
    assert audit == '0|0|0|1|1', audit
    call('GET', '/api/v1/events/' + event_id, expected=404)
    passed(step, inventoryConfirmedValidCheckedReceipts=audit)

    step = 'database schema isolation'
    for service in ('identity', 'catalog', 'admission'):
        for other in ('identity', 'catalog', 'admission'):
            if service != other:
                assert sql(f"SELECT has_schema_privilege('{service}_app','{other}','USAGE')") == 'f'
        assert sql(f"SELECT has_schema_privilege('{service}_app','public','CREATE')") == 'f'
    denied = subprocess.run(kubectl + ['exec', 'postgres-0', '--', 'psql', '-v', 'ON_ERROR_STOP=1',
                                     '-U', 'postgres', '-d', 'sems', '-c',
                                     'SET ROLE catalog_app; SELECT * FROM identity.users'], capture_output=True, text=True, timeout=30)
    assert denied.returncode != 0 and 'permission denied for schema identity' in denied.stderr
    passed(step, deniedCrossSchemaChecks=6, deniedPublicCreateChecks=3, actualCrossSchemaQuery='denied')
    report['status'] = 'passed'
except Exception as error:
    report['status'] = 'failed'
    report['tests'].append({'name': step, 'status': 'failed', 'error': type(error).__name__ + ': ' + str(error)})
    raise
finally:
    for process, log in forwarders:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        log.close()
    report['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = Path(args.report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
