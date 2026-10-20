#!/usr/bin/env python3
"""Real API acceptance for organization overview, filters and event lifecycle.

Default mode requires a disposable localhost Compose stack. --live uses public
APIs only, waits for a short event to end, and never changes database time/state.
All fixtures use unique names; finally cancels offerings and soft-deletes only
organizations created by this invocation. Accounts and audit history remain.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Acceptance:
    def __init__(self, args):
        self.args = args
        self.base = args.base_url.rstrip('/')
        self.run_id = 'qa' + uuid.uuid4().hex[:12]
        self.password = secrets.token_hex(6) + 'Aa1!'
        self.admin = None
        self.accounts = {}
        self.organizations = []
        self.events = []
        self.results = []
        self.auth_at = 0
        self.report = {'runId': self.run_id, 'baseUrl': self.base,
                       'mode': 'live-public-api' if args.live else 'disposable-compose',
                       'startedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
                       'accounts': [], 'organizations': [], 'events': [],
                       'checks': self.results, 'cleanup': {}, 'success': False}
        self.persist()

    def persist(self):
        if not self.args.report:
            return
        path = Path(self.args.report)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            json.dump(self.report, output, indent=2)
            output.write('\n')

    def passed(self, message):
        self.results.append(message)
        self.persist()
        print('PASS: ' + message, flush=True)

    def call(self, method, path, body=None, token=None, expected=200):
        # This fixture shares the production auth budget; never disable the limiter.
        if path.startswith('/api/v1/auth/') and method == 'POST':
            time.sleep(max(0, .3 - (time.monotonic() - self.auth_at)))
            self.auth_at = time.monotonic()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        request = urllib.request.Request(self.base + path, method=method, headers=headers,
                    data=None if body is None else json.dumps(body).encode())
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        # Never include bodies, tokens, credentials or passwords in error output.
        assert status in ((expected,) if isinstance(expected, int) else expected), \
            f'{method} {path}: expected {expected}, got {status}'
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            if status < 400:
                raise
            return None

    def login(self, email, password):
        return self.call('POST', '/api/v1/auth/login',
                         {'email': email, 'password': password})['accessToken']

    def account(self, label):
        email = f'{self.run_id}-{label}@example.com'
        user = self.call('POST', '/api/v1/auth/register',
                        {'username': self.run_id + label, 'email': email,
                         'password': self.password}, expected=201)
        self.report['accounts'].append({'id': user['id'], 'label': label, 'email': email})
        self.persist()
        self.accounts[label] = {**user, 'token': self.login(email, self.password)}
        return self.accounts[label]

    def organization(self, label, owner):
        org = self.call('POST', '/api/v1/admin/organizations',
                        {'name': f'[Acceptance {self.run_id}] {label}',
                         'slug': self.run_id + '-' + label, 'adminEmail': owner['email']},
                        self.admin)
        self.organizations.append((org, owner))
        self.report['organizations'].append({'id': org['id'], 'label': label})
        self.persist()
        return org

    def invite(self, org, owner, account, role):
        invitation = self.call('POST', f"/api/v1/organizations/{org['id']}/invitations",
                                {'email': account['email'], 'role': role}, owner['token'])
        self.call('POST', '/api/v1/invitations/accept', {'token': invitation['token']},
                  account['token'], 204)

    def listing(self, org, owner, **params):
        return self.call('GET', '/api/v1/organizer/events?' + urllib.parse.urlencode(
            {'organizationId': org['id'], **params}), token=owner['token'])

    def members(self, org, owner, **params):
        return self.call('GET', f"/api/v1/organizations/{org['id']}/members?" +
                         urllib.parse.urlencode(params), token=owner['token'])

    def overview(self, org, owner):
        return self.call('GET', f"/api/v1/organizer/organizations/{org['id']}/overview",
                         token=owner['token'])

    def expect_overview(self, org, owner, events, valid, checked):
        result = self.overview(org, owner)
        assert (result['totalEvents'], result['validTickets'], result['checkedIn']) == \
            (events, valid, checked), 'Organization totals differ from fixture ledger'
        assert result['checkedIn'] <= result['validTickets']
        assert dt.datetime.fromisoformat(result['updatedAt'].replace('Z', '+00:00')).tzinfo
        return result

    def current(self, event, owner):
        return self.call('GET', f"/api/v1/organizer/events/{event['id']}", token=owner['token'])

    def event(self, org, owner, label, start, end, visibility='ORGANIZATION_ONLY', publish=True):
        event = self.call('POST', '/api/v1/organizer/events',
                         {'organizationId': org['id'], 'title': self.run_id + ' ' + label,
                          'description': 'Isolated automatic acceptance fixture',
                          'location': 'Acceptance only', 'startsAt': start.isoformat(),
                          'endsAt': end.isoformat(), 'capacity': 20, 'visibility': visibility},
                         owner['token'], 201)
        self.events.append((event, owner))
        self.report['events'].append({'id': event['id'], 'label': label, 'organizationId': org['id']})
        self.persist()
        if not publish:
            return event, None
        inventory = self.call('PUT', f"/api/v1/organizer/events/{event['id']}/ticket-types",
                              {'eventVersion': event['version'], 'version': 0,
                               'ticketTypes': [{'name': 'General', 'quota': 20,
                                'opensAt': (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat(),
                                'closesAt': start.isoformat()}]}, owner['token'])
        event = self.current(event, owner)
        event = self.call('POST', f"/api/v1/organizer/events/{event['id']}/publish",
                           {'version': event['version'], 'ticketVersion': inventory['version']},
                           owner['token'])
        assert event['status'] == 'PUBLISHED'
        return event, inventory['ticketTypes'][0]

    def booking(self, event, ticket_type, attendee, quantity):
        request = {'eventId': event['id'], 'ticketTypeId': ticket_type['id'],
                   'quantity': quantity, 'requestKey': str(uuid.uuid4())}
        booking = self.call('POST', '/api/v1/bookings', request, attendee['token'])
        replay = self.call('POST', '/api/v1/bookings', request, attendee['token'])
        assert replay['id'] == booking['id'], 'Same-key replay created a second booking'
        return booking

    def check(self, event, booking, staff, index=0):
        path = f"/api/v1/events/{event['id']}/check-ins"
        body = {'credential': booking['tickets'][index]['credential']}
        first = self.call('POST', path, body, staff['token'])
        second = self.call('POST', path, body, staff['token'])
        assert not first['alreadyCheckedIn'] and second['alreadyCheckedIn']
        assert first['ticketId'] == second['ticketId']

    def cancel(self, event, owner):
        current = self.current(event, owner)
        if current['status'] in ('PUBLISHED', 'PAUSED'):
            self.call('POST', f"/api/v1/organizer/events/{event['id']}/cancel",
                      {'version': current['version'], 'reason': 'Automatic acceptance cleanup'},
                      owner['token'], (200, 202))
        for _ in range(30):
            current = self.current(event, owner)
            if current['status'] == 'CANCELLED':
                return
            time.sleep(1)
        raise AssertionError('Fixture cancellation did not finish')

    def local_time(self, event, phase):
        # Only own UUIDs are modified; this branch is unreachable in --live mode.
        assert not self.args.live
        uuid.UUID(event['id'])
        offsets = {'ONGOING': ("- interval '1 minute'", "+ interval '1 hour'"),
                   'ENDED': ("- interval '2 hours'", "- interval '1 hour'")}
        start, end = offsets[phase]
        sql = 'SET search_path TO catalog;\n' + '\n'.join(
            f"UPDATE {schema}.{table} SET starts_at=CURRENT_TIMESTAMP {start}, "
            f"ends_at=CURRENT_TIMESTAMP {end}, version=version+1 WHERE {key}='{event['id']}';"
            for schema, table, key in [('catalog', 'events', 'id'), ('admission', 'sales', 'event_id')])
        command = ['docker', 'compose', '--env-file', self.args.env_file,
                   '-f', self.args.compose_file, 'exec', '-T', 'postgres',
                   'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'sems', '-q']
        result = subprocess.run(command, input=sql, text=True, capture_output=True)
        assert result.returncode == 0, 'Local fixture time setup failed'

    def event_filters(self, org, owner, published, draft_public, draft_private, paused, cancelled):
        identities = set()
        for page in range(4):
            data = self.listing(org, owner, keyword=self.run_id.upper(), size=2, page=page)
            assert data['totalElements'] == 8 and data['totalPages'] == 4
            identities.update(e['id'] for e in data['items'])
        assert len(identities) == 8, 'Unfiltered pages duplicate or omit events'
        draft_pages = [self.listing(org, owner, status='DRAFT', timeStatus='UPCOMING',
                                   visibility='PUBLIC', keyword='draft', page=p, size=1)
                       for p in range(2)]
        assert all(p['totalElements'] == 2 and p['totalPages'] == 2 for p in draft_pages)
        assert {e['id'] for p in draft_pages for e in p['items']} == {e['id'] for e in draft_public}
        private = self.listing(org, owner, status='DRAFT', visibility='ORGANIZATION_ONLY')
        assert [e['id'] for e in private['items']] == [draft_private['id']]
        for status, event in [('PAUSED', paused), ('CANCELLED', cancelled)]:
            data = self.listing(org, owner, status=status)
            assert [e['id'] for e in data['items']] == [event['id']]
        assert self.listing(org, owner, status='PUBLISHED')['totalElements'] == published
        assert self.listing(org, owner, keyword='not-present-' + self.run_id)['totalElements'] == 0
        assert not self.listing(org, owner, status='DRAFT', page=50, size=1)['items']
        for bad in [{'status': 'INVALID'}, {'timeStatus': 'INVALID'}, {'visibility': 'INVALID'},
                    {'page': -1}, {'size': 0}, {'size': 51}]:
            self.call('GET', '/api/v1/organizer/events?' + urllib.parse.urlencode(
                       {'organizationId': org['id'], **bad}), token=owner['token'], expected=400)
        self.passed('combined event filters run before paging; all pages, empty and invalid queries')

    def member_filters(self, org, owner, organizer, member):
        first = self.members(org, owner, search=self.run_id.upper(), page=0, size=2)
        second = self.members(org, owner, search=self.run_id, page=1, size=2)
        assert first['totalElements'] == second['totalElements'] == 3
        assert first['totalMembers'] == second['totalMembers'] == 3
        assert {m['userId'] for p in [first, second] for m in p['items']} == \
            {owner['id'], organizer['id'], member['id']}
        for role, user in [('ORG_ADMIN', owner), ('ORGANIZER', organizer), ('MEMBER', member)]:
            data = self.members(org, owner, search=user['email'].upper(), role=role,
                                status='ACTIVE', size=1)
            assert data['totalElements'] == 1 and data['totalMembers'] == 3
            assert data['items'][0]['userId'] == user['id']
        target = self.members(org, owner, role='MEMBER')['items'][0]
        path = f"/api/v1/organizations/{org['id']}/members/{member['id']}"
        for state in ['SUSPENDED', 'REMOVED', 'ACTIVE']:
            self.call('PUT', path, {'role': 'MEMBER', 'status': state, 'version': target['version']},
                      owner['token'], 204)
            result = self.members(org, owner, role='MEMBER', status=state, search=self.run_id)
            assert result['totalElements'] == 1 and result['totalMembers'] == 3
            target = result['items'][0]
            assert target['status'] == state
            if state != 'ACTIVE':
                assert not self.members(org, owner, role='MEMBER', status='ACTIVE')['items']
        assert not self.members(org, owner, role='ORGANIZER', search=member['email'])['items']
        for bad in [{'role': 'ADMIN'}, {'status': 'INVALID'}, {'page': -1}, {'size': 51}]:
            self.call('GET', f"/api/v1/organizations/{org['id']}/members?" +
                      urllib.parse.urlencode(bad), token=owner['token'], expected=400)
        self.passed('member name/email, role and status filters; pagination and membership changes')

    def ended(self, org, owner, ongoing, ended, draft, empty):
        if self.args.live:
            end = dt.datetime.fromisoformat(ended['endsAt'].replace('Z', '+00:00'))
            seconds = max(0, (end - dt.datetime.now(dt.timezone.utc)).total_seconds())
            print(f'Waiting {seconds:.0f}s for the fixture to end naturally; no database writes.', flush=True)
            while dt.datetime.now(dt.timezone.utc) <= end + dt.timedelta(seconds=1):
                time.sleep(1)
        else:
            self.local_time(ongoing, 'ONGOING')
            self.local_time(ended, 'ENDED')
            self.local_time(draft, 'ENDED')
            phases = {'ONGOING': ongoing, 'ENDED': ended}
            for phase, event in phases.items():
                result = self.listing(org, owner, status='PUBLISHED', timeStatus=phase,
                                      visibility='ORGANIZATION_ONLY', keyword=self.run_id)
                assert [e['id'] for e in result['items']] == [event['id']]
        assert ended['id'] in [e['id'] for e in self.listing(org, owner, timeStatus='ENDED')['items']]
        current = self.current(ended, owner)
        future = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=3)
        changed = {**current, 'startsAt': future.isoformat(),
                   'endsAt': (future + dt.timedelta(hours=1)).isoformat()}
        root = f"/api/v1/organizer/events/{ended['id']}"
        self.call('PUT', root + '/revision', changed, owner['token'], 409)
        self.call('PATCH', root + '/presentation', {**current, 'title': 'Forbidden reopen'},
                  owner['token'], 409)
        if not self.args.live:
            current_draft = self.current(draft, owner)
            self.call('PUT', f"/api/v1/organizer/events/{draft['id']}",
                      {**current_draft, 'startsAt': future.isoformat(),
                       'endsAt': (future + dt.timedelta(hours=1)).isoformat()}, owner['token'], 409)
        unchanged = self.current(ended, owner)
        assert unchanged['version'] == current['version'] and unchanged['endsAt'] == current['endsAt']
        self.expect_overview(org, owner, 8, 7, 3)
        self.expect_overview(empty, self.accounts['outsider'], 0, 0, 0)
        self.passed('ended events remain in totals, reject edits/reopening and preserve version')

    def run(self):
        self.admin = self.login(os.environ['SEMS_BOOTSTRAP_ADMIN_EMAIL'],
                                os.environ['SEMS_BOOTSTRAP_ADMIN_PASSWORD'])
        for password in ['Ab12345', 'Ab123456789012345', 'Pass word', '密码Ab123456']:
            problem = self.call('POST', '/api/v1/auth/register',
                                {'username': self.run_id + 'bad',
                                 'email': self.run_id + '-bad@example.com', 'password': password},
                                expected=400)
            guidance = problem.get('fieldErrors', {}).get('password', '')
            assert '8–16' in guidance and 'English letters' in guidance
        self.passed('registration password boundaries and English error guidance')
        owner, organizer, member, outsider = [self.account(label) for label in
                                             ['owner', 'organizer', 'member', 'outsider']]
        org = self.organization('main', owner)
        empty = self.organization('empty', outsider)
        self.invite(org, owner, organizer, 'ORGANIZER')
        self.invite(org, owner, member, 'MEMBER')
        self.expect_overview(org, owner, 0, 0, 0)
        self.expect_overview(empty, outsider, 0, 0, 0)
        overview_path = f"/api/v1/organizer/organizations/{org['id']}/overview"
        self.call('GET', overview_path, expected=401)
        for user, status in [(organizer, 403), (member, 404), (outsider, 404)]:
            self.call('GET', overview_path, token=user['token'], expected=status)
        self.call('GET', overview_path, token=self.admin, expected=404)
        self.call('GET', f"/api/v1/organizations/{org['id']}/members",
                  token=outsider['token'], expected=403)
        self.call('GET', '/api/v1/organizer/events?organizationId=' + org['id'],
                  token=outsider['token'], expected=404)
        self.call('GET', '/internal/v1/organizations/' + org['id'] + '/attendance-summary', expected=404)
        self.passed('zero totals, administrator-only overview, organization isolation and internal route denial')
        self.member_filters(org, owner, organizer, member)
        now = dt.datetime.now(dt.timezone.utc)
        near, near_end = now + dt.timedelta(minutes=2), now + dt.timedelta(minutes=4)
        later, later_end = now + dt.timedelta(days=3), now + dt.timedelta(days=3, hours=1)
        active, at = self.event(org, owner, 'active', near, near_end)
        ending, et = self.event(org, owner, 'ending', near, near_end)
        paused, pt = self.event(org, organizer, 'paused', later, later_end)
        cancelled, ct = self.event(org, owner, 'cancelled', near, near_end)
        drafts = [self.event(org, owner, f'draft public {i}', later, later_end,
                              visibility='PUBLIC', publish=False)[0] for i in range(2)]
        private_draft = self.event(org, owner, 'draft private', later, later_end, publish=False)[0]
        ended_draft = self.event(org, owner, 'historical setup', later, later_end, visibility='PUBLIC', publish=False)[0]
        for event in [active, ending, cancelled]:
            self.call('PUT', f"/api/v1/organizer/events/{event['id']}/staff",
                      {'userId': organizer['id'], 'active': True}, owner['token'], 204)
        directory = self.call('GET', '/api/v1/events?' + urllib.parse.urlencode(
            {'organizationId': org['id'], 'keyword': self.run_id}), token=member['token'])
        assert active['id'] in [e['id'] for e in directory['items']]
        self.call('GET', '/api/v1/events/' + active['id'], token=outsider['token'], expected=404)
        details = self.call('GET', '/api/v1/events/' + active['id'], token=member['token'])
        assert details['id'] == active['id']
        self.call('GET', '/api/v1/events/' + active['id'] + '/ticket-types', token=member['token'])
        active_booking = self.booking(active, at, member, 4)
        receipt = self.call('GET', '/api/v1/bookings/' + active_booking['id'], token=member['token'])
        assert len(receipt['tickets']) == 4
        assert len({t['credential'] for t in receipt['tickets']}) == 4
        ended_booking = self.booking(ending, et, member, 2)
        self.booking(paused, pt, member, 1)
        cancelled_booking = self.booking(cancelled, ct, member, 2)
        cancelled_order = self.booking(active, at, member, 1)
        self.call('POST', '/api/v1/bookings/' + cancelled_order['id'] + '/cancel',
                  token=member['token'])
        self.call('POST', f"/api/v1/events/{active['id']}/check-ins",
                  {'credential': active_booking['tickets'][0]['credential']}, owner['token'], 403)
        self.check(active, active_booking, organizer, 0)
        self.check(active, active_booking, organizer, 1)
        self.check(ending, ended_booking, organizer)
        self.check(cancelled, cancelled_booking, organizer)
        self.call('GET', '/api/v1/bookings/' + active_booking['id'], token=outsider['token'], expected=404)
        self.expect_overview(org, owner, 8, 9, 4)
        self.cancel(cancelled, owner)
        summary = self.call('GET', f"/api/v1/organizer/events/{cancelled['id']}/summary", token=owner['token'])
        assert summary['attendance'] == 1 and summary['confirmedTickets'] == 0
        paused = self.current(paused, organizer)
        paused = self.call('PUT', f"/api/v1/organizer/events/{paused['id']}/revision",
                           {**paused, 'publicationStatus': 'PAUSED'}, organizer['token'])
        assert paused['status'] == 'PAUSED'
        summary = self.call('GET', f"/api/v1/organizer/events/{active['id']}/summary", token=organizer['token'])
        assert (summary['confirmedTickets'], summary['attendance']) == (4, 2)
        self.expect_overview(org, owner, 8, 7, 3)
        self.passed('book/replay/cancel/check-in loop; paused tickets included; cancelled event attendance excluded')
        self.event_filters(org, owner, 2, drafts, private_draft, paused, cancelled)
        # A query and a different list page must not narrow organization totals.
        self.listing(org, owner, status='DRAFT', visibility='PUBLIC', size=1, page=1)
        self.expect_overview(org, owner, 8, 7, 3)
        self.ended(org, owner, active, ending, ended_draft, empty)
        self.report['success'] = True

    def cleanup(self):
        errors = []
        for event, owner in self.events:
            try:
                current = self.current(event, owner)
                if current['status'] in ('PUBLISHED', 'PAUSED', 'CANCELLING'):
                    self.cancel(event, owner)
            except Exception:
                errors.append('event:' + event['id'])
        for org, owner in self.organizations:
            try:
                query = urllib.parse.urlencode({'search': org['slug'], 'size': 50})
                current = next(o for o in self.call('GET', '/api/v1/admin/organizations?' + query,
                               token=self.admin)['items'] if o['id'] == org['id'])
                self.call('DELETE', f"/api/v1/admin/organizations/{org['id']}?version={current['version']}",
                          token=self.admin, expected=204)
                for _ in range(45):
                    remaining = self.call('GET', '/api/v1/admin/organizations?' + query,
                                           token=self.admin)['items']
                    if not any(o['id'] == org['id'] for o in remaining):
                        break
                    time.sleep(1)
                else:
                    raise AssertionError('Organization closure did not complete')
                assert not self.call('GET', '/api/v1/me/organizations', token=owner['token'])
            except Exception:
                errors.append('organization:' + org['id'])
        self.report['cleanup'] = {'complete': not errors, 'failedFixtureIds': errors,
                                 'accountsRetained': len(self.report['accounts']),
                                 'historyRetained': True}
        self.report['success'] = self.report['success'] and not errors
        self.report['completedAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
        self.persist()
        assert not errors, 'Fixture cleanup incomplete; see report IDs'
        print('PASS: fixture events cancelled, organizations soft-deleted and memberships revoked; accounts/history retained', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default=os.environ.get('SEMS_BASE_URL', 'http://localhost:18080'))
    parser.add_argument('--env-file', default=os.environ.get('SEMS_ENV_FILE', '.env'))
    parser.add_argument('--compose-file', default=os.environ.get('SEMS_COMPOSE_FILE', 'deployment/compose.yaml'))
    parser.add_argument('--live', action='store_true', help='Public APIs only; wait for fixture end; retains accounts/history')
    parser.add_argument('--report', help='JSON report with fixture IDs and cleanup status; never credentials')
    args = parser.parse_args()
    target = urllib.parse.urlsplit(args.base_url)
    if not args.live and target.hostname not in ('localhost', '127.0.0.1', '::1'):
        parser.error('Default mode is disposable localhost Compose only; never point it at a remote database')
    if args.live and not args.report:
        parser.error('--live requires --report so fixture IDs and cleanup results can be audited')
    if args.live and (target.scheme != 'https' or target.hostname != 'swe5001.seventh720.com'):
        parser.error('--live is restricted to the requested HTTPS staging host')
    suite = Acceptance(args)
    try:
        suite.run()
    finally:
        suite.cleanup()
    print('PASS: organization management acceptance complete', flush=True)


if __name__ == '__main__':
    main()
