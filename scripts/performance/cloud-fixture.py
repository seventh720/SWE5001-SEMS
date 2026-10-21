#!/usr/bin/env python3
"""Prepare a separate 100-place contention event, or close only this cloud fixture."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import time

from seed import call, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare-hot', 'cleanup'])
    parser.add_argument('--dataset', type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text())
    base = data['baseUrl']
    if base != 'https://swe5001.seventh720.com' or not data.get('organizationId'):
        parser.error('Require a seeded SWE5001 cloud fixture')
    organizer = data['users'][0]
    token = call(base, 'POST', '/api/v1/auth/login',
                 {'email': organizer['email'], 'password': data['password']})['accessToken']
    if args.action == 'prepare-hot':
        if data.get('hotEvent'):
            parser.error('Hot event already recorded; do not reuse its inventory')
        start = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)
        event = call(base, 'POST', '/api/v1/organizer/events', {
            'organizationId': data['organizationId'], 'visibility': 'PUBLIC',
            'title': f"Benchmark {data['runId']} contention", 'description': 'Disposable capacity fixture',
            'location': 'Benchmark venue', 'startsAt': start.isoformat(),
            'endsAt': (start + dt.timedelta(hours=2)).isoformat(), 'capacity': 100}, token)
        data['hotEvent'] = {'eventId': event['id'], 'quota': 100}
        save(args.dataset, data)
        path = '/api/v1/organizer/events/' + event['id']
        tickets = call(base, 'PUT', path + '/ticket-types', {'eventVersion': event['version'],
            'version': 0, 'ticketTypes': [{'name': 'General', 'quota': 100,
                'opensAt': (start - dt.timedelta(days=8)).isoformat(), 'closesAt': start.isoformat()}]}, token)
        data['hotEvent']['ticketTypeId'] = tickets['ticketTypes'][0]['id']
        save(args.dataset, data)
        event = call(base, 'GET', path, token=token)
        result = call(base, 'POST', path + '/publish',
                      {'version': event['version'], 'ticketVersion': tickets['version']}, token)
        assert result['status'] == 'PUBLISHED', 'Hot event publication incomplete'
        print('Prepared dedicated 100-place contention event')
        return
    # Cancel and wait for the product's normal cross-service workflow first.
    for event in data['events'] + ([data['hotEvent']] if data.get('hotEvent') else []):
        path = '/api/v1/organizer/events/' + event['eventId']
        current = call(base, 'GET', path, token=token)
        if current['status'] in ('PUBLISHED', 'PAUSED'):
            call(base, 'POST', path + '/cancel',
                 {'version': current['version'], 'reason': 'Cloud capacity experiment cleanup'}, token)
        for _ in range(60):
            if call(base, 'GET', path, token=token)['status'] in ('CANCELLED', 'DRAFT'):
                break
            time.sleep(1)
        else:
            raise RuntimeError('Fixture cancellation incomplete')
    admin = call(base, 'POST', '/api/v1/auth/login', {
        'email': os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],
        'password': os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD']})['accessToken']
    # The delete endpoint has an empty response, unlike seed.call's JSON contract.
    import urllib.request
    query = '/api/v1/admin/organizations?search=benchmark-' + data['runId'] + '&size=50'
    current = next(org for org in call(base, 'GET', query, token=admin)['items']
                   if org['id'] == data['organizationId'])
    request = urllib.request.Request(base + '/api/v1/admin/organizations/' + data['organizationId'] +
        '?version=' + str(current['version']),
        method='DELETE', headers={'Authorization': 'Bearer ' + admin})
    with urllib.request.urlopen(request, timeout=30) as response:
        assert response.status in (202, 204)
    for _ in range(60):
        remaining = call(base, 'GET', query, token=admin)
        if not any(org['id'] == data['organizationId'] for org in remaining['items']):
            break
        time.sleep(1)
    else:
        raise RuntimeError('Organization closure incomplete')
    call(base, 'PUT', f"/api/v1/admin/users/{organizer['id']}/roles", {'roles': ['ATTENDEE']}, admin)
    data['cleanup'] = {'productCleanupComplete': True, 'at': dt.datetime.now(dt.timezone.utc).isoformat(),
                       'accountsRetained': len(data['users']), 'historyRetained': True}
    save(args.dataset, data)
    print('Fixture activities cancelled, organization closed and organizer role revoked')


if __name__ == '__main__':
    main()
