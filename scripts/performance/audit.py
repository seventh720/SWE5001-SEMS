#!/usr/bin/env python3
"""Check persisted inventory/booking/ticket invariants for one benchmark dataset."""
import argparse
import json
import os
import subprocess
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    data = json.load(open(args.dataset))
    ids = ','.join("'" + str(uuid.UUID(e['eventId'])) + "'" for e in data['events'])
    if not ids:
        parser.error('Dataset has no events')
    compose = ['docker', 'compose', '--env-file', os.environ.get('SEMS_ENV_FILE', '.env')]
    for path in os.environ.get('SEMS_COMPOSE_FILE', 'deployment/compose.yaml').split(os.pathsep):
        compose += ['-f', path]
    query = f"""SELECT coalesce(json_agg(row_to_json(x)), '[]'::json) FROM (
        SELECT t.id, t.quota, t.reserved,
          (SELECT coalesce(sum(b.quantity),0) FROM admission.bookings b
           WHERE b.ticket_type_id=t.id AND b.status='CONFIRMED') AS confirmed,
          (SELECT count(*) FROM admission.tickets k JOIN admission.bookings b ON b.id=k.booking_id
           WHERE b.ticket_type_id=t.id AND k.state IN ('VALID','CHECKED_IN')) AS tickets
        FROM admission.ticket_types t WHERE t.event_id IN ({ids}) ORDER BY t.id) x"""
    rows = json.loads(subprocess.check_output(compose + ['exec', '-T', 'postgres', 'psql',
        '-U', 'postgres', '-d', 'sems', '-Atq', '-c', query], text=True))
    ok = len(rows) == len(data['events']) and all(
        0 <= row['reserved'] <= row['quota'] and row['reserved'] == row['confirmed'] == row['tickets'] for row in rows)
    with open(args.output, 'x') as out:
        json.dump({'dataset': data['runId'], 'passed': ok, 'inventory': rows}, out, indent=2)
    if not ok:
        raise SystemExit('Inventory invariant failed; inspect audit output')
    print('PASS: reserved = confirmed quantities = active tickets, within quota')


if __name__ == '__main__':
    main()
