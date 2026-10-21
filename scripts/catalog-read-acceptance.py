#!/usr/bin/env python3
"""Catalog projections, live access checks and protected timing diagnostics. Disposable stack only."""
from acceptance import *
import re
import shlex
import subprocess
from urllib.parse import urlencode

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

# Full pages must count only matching, currently active organizations. These
# offerings also exercise the public DTO's JSON field, category and card theme.
directory_keyword = 'Directory read ' + suffix
requirements = {'realName': True, 'email': True, 'phone': False, 'studentId': True,
                'passport': False, 'customFieldLabel': 'Meal preference'}


def directory_event(token, organization, index, visibility='PUBLIC', category='TECH'):
    begins = start + datetime.timedelta(minutes=index + 1)
    payload = {'organizationId': organization['id'], 'visibility': visibility,
        'title': directory_keyword + (r' \literal_' if index == 0 else ' ') + str(index), 'description': 'Projected public description',
        'location': 'Projection venue', 'startsAt': begins.isoformat(),
        'endsAt': (begins + datetime.timedelta(hours=2)).isoformat(), 'capacity': 30,
        'category': category, 'cardTheme': 'SKY', 'registrationRequirements': requirements}
    event = call('POST', '/api/v1/organizer/events', payload, token, 201)
    route = '/api/v1/organizer/events/' + event['id']
    tickets = call('PUT', route + '/ticket-types', {'eventVersion': event['version'], 'version': 0,
        'ticketTypes': [{'name': 'General', 'quota': 30,
                        'opensAt': (start - datetime.timedelta(days=8)).isoformat(),
                        'closesAt': begins.isoformat()}]}, token)
    event = call('GET', route, token=token)
    event = call('POST', route + '/publish', {'version': event['version'],
                 'ticketVersion': tickets['version']}, token)
    assert event['status'] == 'PUBLISHED'
    public = call('GET', '/api/v1/events/' + event['id'], token=token)
    assert set(public) == {'id', 'title', 'description', 'location', 'startsAt', 'endsAt',
        'capacity', 'category', 'cardTheme', 'registrationRequirements', 'organizationId',
        'visibility', 'organizationName'}
    for key in ['title', 'description', 'location', 'capacity', 'category', 'cardTheme',
                'registrationRequirements', 'organizationId', 'visibility']:
        assert public[key] == payload[key], key
    assert public['organizationName'] == organization['name']
    for key in ['startsAt', 'endsAt']:
        assert datetime.datetime.fromisoformat(public[key].replace('Z', '+00:00')) == datetime.datetime.fromisoformat(payload[key])
    return event


directory_a = directory_event(a, org_a, 0)
directory_a2 = directory_event(a, org_a, 1, category='EDUCATION')
directory_b = directory_event(b, org_b, 2)
directory_private = directory_event(a, org_a, 3, visibility='ORGANIZATION_ONLY')


def directory(page=0, size=2, token=None, **filters):
    return call('GET', '/api/v1/events?' + urlencode({'keyword': directory_keyword,
                'page': page, 'size': size, **filters}), token=token)


first = directory()
assert first['totalElements'] == 3 and first['totalPages'] == 2
backslash = directory(keyword=directory_keyword + r' \literal_0')
assert backslash['totalElements'] == 1 and backslash['items'][0]['id'] == directory_a['id']
assert [x['id'] for x in first['items']] == [directory_a['id'], directory_a2['id']]
assert all(x['registrationRequirements'] == requirements and x['cardTheme'] == 'SKY' for x in first['items'])
assert [x['id'] for x in directory(page=1)['items']] == [directory_b['id']]
last = directory(page=2)
assert last['items'] == [] and last['totalElements'] == 3 and last['totalPages'] == 2
filtered = directory(category='TECH')
assert filtered['totalElements'] == 2 and {x['id'] for x in filtered['items']} == {directory_a['id'], directory_b['id']}
scoped = directory(token=a, organizationId=org_a['id'])
assert scoped['totalElements'] == 3 and scoped['totalPages'] == 2
assert [x['id'] for x in directory(page=1, token=a, organizationId=org_a['id'])['items']] == [directory_private['id']]
call('GET', '/api/v1/events/' + directory_private['id'], expected=404)
call('GET', '/api/v1/events/' + directory_private['id'], token=b, expected=404)
call('PATCH', '/api/v1/admin/organizations/' + org_a['id'], {'status': 'SUSPENDED'}, admin, 204)
try:
    internal(published, expected=404)
    call('GET', '/api/v1/events/' + draft['id'], expected=404)
    assert call('GET', '/api/v1/events?keyword=' + suffix)['totalElements'] == 1
    # Admission has already authorized the receipt; historical details remain readable.
    assert internal('/internal/v1/events/details', {'ids': [draft['id']]})[0]['title'] == title
    remaining = directory(size=1)
    assert remaining['totalElements'] == 1 and remaining['totalPages'] == 1
    assert [x['id'] for x in remaining['items']] == [directory_b['id']]
    assert directory(page=1, size=1)['items'] == []
    call('GET', '/api/v1/events/' + directory_a['id'], token=a, expected=404)
    assert internal('/internal/v1/events/details', {'ids': [directory_a['id']]})[0]['title'] == directory_a['title']
finally:
    call('PATCH', '/api/v1/admin/organizations/' + org_a['id'], {'status': 'ACTIVE'}, admin, 204)
assert internal(published)['id'] == draft['id']
assert directory()['totalElements'] == 3
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
print('PASS: public/internal projections, grouped active totals and pagination, private visibility, live suspension, historical details and protected read/pool/Identity timings')
