#!/usr/bin/env python3
"""Catalog projections, live access checks and protected timing diagnostics. Disposable stack only."""
from acceptance import *
import re
import shlex
import subprocess

compose = ['docker', 'compose', '--env-file', os.environ.get('SEMS_ENV_FILE', '.env')]
for filename in os.environ.get('SEMS_COMPOSE_FILE', 'deployment/compose.yaml').split(os.pathsep):
    compose += ['-f', filename]
service_token = os.environ['ADMISSION_TO_CATALOG_TOKEN']


def internal(route, payload=None, secret=service_token, expected=200):
    # Send the credential on stdin; it is absent from argv and assertion messages.
    command = 'IFS= read -r service_token; wget -S -O - -T 8 --header "X-Service-Token: $service_token"'
    if payload is not None:
        command += ' --header "Content-Type: application/json" --post-data ' + shlex.quote(json.dumps(payload))
    command += ' ' + shlex.quote('http://event-catalog:8082' + route)
    result = subprocess.run(compose + ['exec', '-T', 'gateway', 'sh', '-c', command],
                            input=secret + '\n', capture_output=True, text=True)
    statuses = re.findall(r'HTTP/\S+\s+(\d+)', result.stderr)
    assert statuses and int(statuses[-1]) == expected, f'Internal {route}: unexpected status'
    return json.loads(result.stdout) if expected == 200 else None


diagnostics = '/internal/v1/diagnostics/catalog'
internal(diagnostics, secret='', expected=401)
internal(diagnostics, secret='invalid-service-token', expected=401)
call('GET', diagnostics, token=admin, expected=404)
before = internal(diagnostics)
current = call('GET', path, token=a)
inventory = call('PUT', path + '/ticket-types', {'eventVersion': current['version'], 'version': 0,
    'ticketTypes': [{'name': 'General', 'quota': 30,
                    'opensAt': (start - datetime.timedelta(days=8)).isoformat(),
                    'closesAt': start.isoformat()}]}, a)
current = call('GET', path, token=a)
current = call('POST', path + '/publish', {'version': current['version'],
               'ticketVersion': inventory['version']}, a)
title = 'Catalog read ' + suffix
current = call('PATCH', path + '/presentation', {**current, 'title': title}, a)
rows = internal('/internal/v1/events/details', {'ids': [draft['id'], draft['id'], str(uuid.uuid4())]})
assert len(rows) == 1 and rows[0]['id'] == draft['id']
assert set(rows[0]) == {'id', 'title', 'location', 'startsAt', 'endsAt', 'status'}
assert rows[0]['title'] == title and rows[0]['status'] == 'PUBLISHED'
assert internal('/internal/v1/events/details', {'ids': []}) == []
internal('/internal/v1/events/details', {'ids': [draft['id']] * 51}, expected=400)
internal('/internal/v1/events/details', {'ids': [None]}, expected=400)
published = '/internal/v1/events/' + draft['id'] + '/published'
snapshot = internal(published)
assert snapshot['registrationRequirements'] == current['registrationRequirements']
assert snapshot['organizationId'] == org_a['id'] and snapshot['title'] == title
assert call('GET', '/api/v1/events?keyword=' + suffix)['totalElements'] == 1
call('PATCH', '/api/v1/admin/organizations/' + org_a['id'], {'status': 'SUSPENDED'}, admin, 204)
try:
    internal(published, expected=404)
    call('GET', '/api/v1/events/' + draft['id'], expected=404)
    assert call('GET', '/api/v1/events?keyword=' + suffix)['totalElements'] == 0
    # Admission has already authorized the receipt; historical details remain readable.
    assert internal('/internal/v1/events/details', {'ids': [draft['id']]})[0]['title'] == title
finally:
    call('PATCH', '/api/v1/admin/organizations/' + org_a['id'], {'status': 'ACTIVE'}, admin, 204)
assert internal(published)['id'] == draft['id']
after = internal(diagnostics)
counts = {(t['name'], t['operation']): t['count'] for t in after['timers']}
old = {(t['name'], t['operation']): t['count'] for t in before['timers']}
for key in [('catalog.read', 'internal-details'), ('catalog.read', 'publication-snapshot'),
            ('catalog.read', 'public-list'), ('catalog.identity', 'active-organizations')]:
    assert counts[key] > old.get(key, 0), key
for name in ['hikaricp.connections.acquire', 'hikaricp.connections.usage']:
    assert any(t['name'] == name and t['count'] > 0 for t in after['timers']), name
maximum = next(g['value'] for g in after['pool'] if g['name'] == 'hikaricp.connections.max')
assert maximum == int(os.environ.get('CATALOG_DB_POOL_SIZE', '10'))
print('PASS: six-field projection, duplicates/missing IDs, limits, live suspension, historical details and protected read/pool/Identity timings')
