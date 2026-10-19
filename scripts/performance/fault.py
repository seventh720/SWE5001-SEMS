#!/usr/bin/env python3
"""Stop one of >=2 service replicas for a bounded experiment, then restore it."""
import argparse
import datetime
import json
import os
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service', choices=['event-catalog', 'admission'], required=True)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.seconds < 1:
        parser.error('Duration must be positive')
    compose = ['docker', 'compose', '--env-file', os.environ.get('SEMS_ENV_FILE', '.env')]
    for path in os.environ.get('SEMS_COMPOSE_FILE', 'deployment/compose.yaml').split(os.pathsep):
        compose += ['-f', path]
    ids = subprocess.check_output(compose + ['ps', '-q', args.service], text=True).split()
    if len(ids) < 2:
        parser.error('At least two running replicas are required')
    # Opening before disruption prevents an output-file error from causing an unrecorded outage.
    with open(args.output, 'x') as out:
        def record(event):
            out.write(json.dumps({'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                  'event': event, 'service': args.service, 'container': ids[-1]}) + '\n')
            out.flush()
        try:
            record('stop-requested')
            subprocess.run(['docker', 'stop', '--time', '0', ids[-1]], check=True, stdout=subprocess.DEVNULL)
            record('replica-stopped')
            time.sleep(args.seconds)
        finally:
            record('restore-requested')
            subprocess.run(['docker', 'start', ids[-1]], check=True, stdout=subprocess.DEVNULL)
            record('container-started-not-readiness-confirmed')


if __name__ == '__main__':
    main()
