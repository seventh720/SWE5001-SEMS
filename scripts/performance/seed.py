#!/usr/bin/env python3
"""Create an isolated benchmark dataset through public APIs, never direct DB writes."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.request
import uuid


def call(base, method, path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(base + path, method=method, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code != 429 or attempt == 5:
                raise RuntimeError(f'{method} {path}: HTTP {error.code}') from None
            time.sleep(5)
    raise RuntimeError('Authentication rate limit did not clear')


def save(path, data):
    # Tokens/passwords stay outside evidence and are created private from the outset.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as out:
        os.chmod(path, 0o600)
        json.dump(data, out, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--users', type=int, default=1000)
    parser.add_argument('--events', type=int, default=100)
    parser.add_argument('--quota', type=int, default=100000)
    parser.add_argument('--refresh', action='store_true', help='Refresh tokens in an existing dataset')
    args = parser.parse_args()
    if min(args.users, args.events, args.quota) < 1:
        parser.error('Counts must be positive')
    base = args.base_url.rstrip('/')
    path = Path(args.output)
    if args.refresh:
        data = json.loads(path.read_text())
        if data['baseUrl'] != base:
            parser.error('Dataset belongs to a different target')
        for user in data['users']:
            user['token'] = call(base, 'POST', '/api/v1/auth/login',
                {'email': user['email'], 'password': data['password']})['accessToken']
            time.sleep(.25)
        data['tokensRefreshedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save(path, data)
        print('Refreshed tokens; no dataset changes')
        return
    if path.exists():
        parser.error('Output exists; choose a new dataset file or use --refresh')
    admin = call(base, 'POST', '/api/v1/auth/login', {
        'email': os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],
        'password': os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD']})['accessToken']
    run = uuid.uuid4().hex[:12]
    password = secrets.token_urlsafe(24)
    data = {'schemaVersion': 1, 'runId': run, 'baseUrl': base, 'password': password,
            'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'users': [], 'events': []}
    save(path, data)
    # Register at <=4 requests/s; keep the real gateway authentication limiter enabled.
    for index in range(args.users):
        email = f'load-{run}-{index}@example.com'
        user = call(base, 'POST', '/api/v1/auth/register',
            {'email': email, 'username': f'load{run}{index}', 'password': password})
        data['users'].append({'id': user['id'], 'email': email})
        save(path, data)
        time.sleep(.25)
    organizer = data['users'][0]
    call(base, 'PUT', f"/api/v1/admin/users/{organizer['id']}/roles",
         {'roles': ['ATTENDEE', 'ORGANIZER']}, admin)
    org = call(base, 'POST', '/api/v1/admin/organizations',
        {'name': f'Benchmark {run}', 'slug': f'benchmark-{run}', 'adminEmail': organizer['email']}, admin)
    data['organizationId'] = org['id']
    token = call(base, 'POST', '/api/v1/auth/login',
        {'email': organizer['email'], 'password': password})['accessToken']
    start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
    for index in range(args.events):
        event = call(base, 'POST', '/api/v1/organizer/events', {
            'organizationId': org['id'], 'visibility': 'PUBLIC', 'title': f'Benchmark {run} {index:03}',
            'description': 'Disposable benchmark dataset', 'location': 'Benchmark venue',
            'startsAt': start.isoformat(), 'endsAt': (start + dt.timedelta(hours=2)).isoformat(),
            'capacity': args.quota}, token)
        ep = '/api/v1/organizer/events/' + event['id']
        tickets = call(base, 'PUT', ep + '/ticket-types', {'eventVersion': event['version'],
            'version': 0, 'ticketTypes': [{'name': 'General', 'quota': args.quota,
                'opensAt': (start - dt.timedelta(days=8)).isoformat(), 'closesAt': start.isoformat()}]}, token)
        event = call(base, 'GET', ep, token=token)
        published = call(base, 'POST', ep + '/publish',
            {'version': event['version'], 'ticketVersion': tickets['version']}, token)
        if published['status'] != 'PUBLISHED':
            raise RuntimeError('Publication pending; restore service health before benchmarking')
        data['events'].append({'eventId': event['id'], 'ticketTypeId': tickets['ticketTypes'][0]['id'], 'quota': args.quota})
        save(path, data)
    # Log in after dataset creation so the full one-hour JWT window is available.
    for user in data['users']:
        user['token'] = call(base, 'POST', '/api/v1/auth/login',
            {'email': user['email'], 'password': password})['accessToken']
        time.sleep(.25)
    data['tokensRefreshedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    save(path, data)
    print(f"Created dataset {run}: {len(data['events'])} events, {len(data['users'])} users. Credentials saved privately.")


if __name__ == '__main__':
    main()
