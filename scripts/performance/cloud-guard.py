#!/usr/bin/env python3
"""Run on the cloud host; emit resource/health metadata, never runtime secrets."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.request


def command(arguments):
    return subprocess.check_output(arguments, text=True, timeout=10).strip()


def docker(*arguments):
    return command(['sudo', '-n', 'docker', *arguments])


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--load1-limit', type=float, default=8,
                    help='Three samples above this limit stop the run; 0 records load without stopping')
parser.add_argument('--health-latency-limit', type=float, default=5,
                    help='Three consecutive slow or failed health probes stop the run')
parser.add_argument('--health-timeout', type=float, default=6,
                    help='Per-probe timeout in seconds; must exceed the health latency limit')
parser.add_argument('--samples', type=int, default=0, help='0 streams until stopped; positive values bound a read-only check')
args = parser.parse_args()
assert args.load1_limit >= 0
assert args.samples >= 0
if not 0 < args.health_latency_limit < args.health_timeout < float('inf'):
    parser.error('Require 0 < --health-latency-limit < --health-timeout < infinity')
domain = docker('exec', 'swe5001-caddy-1', 'printenv', 'SEMS_DOMAIN')
bad = {}
container_names = docker('ps', '--format', '{{.Names}}').splitlines()
baseline_states = docker('inspect', '--format', '{{.Name}}|{{.State.StartedAt}}|{{.RestartCount}}', *container_names).splitlines()


def probe(name, url):
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=args.health_timeout) as response:
            content = response.read()
            ok = response.status == 200 and (name in ['swe5006-web', 'swe5001-web'] or json.loads(content)['status'] == 'UP')
        return name, {'ok': ok, 'seconds': round(time.monotonic() - started, 3)}
    except Exception:
        return name, {'ok': False, 'seconds': round(time.monotonic() - started, 3)}


sample_count = 0
while True:
    started = time.monotonic()
    sample = {'at': datetime.now(timezone.utc).isoformat()}
    try:
        memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
        sample['availableMemoryMiB'] = round(memory['MemAvailable'] / 1024, 2)
        sample['load1'] = float(Path('/proc/loadavg').read_text().split()[0])
        stats = docker('stats', '--no-stream', '--format', '{{json .}}')
        sample['containers'] = [{k: item[k] for k in ['Name', 'CPUPerc', 'MemUsage', 'MemPerc', 'PIDs']}
                                for item in map(json.loads, stats.splitlines())]
        raw = docker('inspect', '--format', '{{.Name}}|{{.State.Running}}|{{.State.OOMKilled}}|{{.RestartCount}}',
                     *container_names)
        sample['states'] = raw.splitlines()
        sample['identityChanged'] = docker('inspect', '--format', '{{.Name}}|{{.State.StartedAt}}|{{.RestartCount}}', *container_names).splitlines() != baseline_states
        sample['database'] = docker('exec', 'swe5001-postgres-1', 'sh', '-c',
            '''exec psql -XqAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT json_build_object('connections',count(*),'active',count(*) FILTER (WHERE state='active'),'lockWaiters',count(*) FILTER (WHERE wait_event_type='Lock'),'longestActiveSeconds',COALESCE(max(extract(epoch from now()-query_start)) FILTER (WHERE state='active'),0)) FROM pg_stat_activity WHERE datname=current_database();"''')
        with ThreadPoolExecutor(max_workers=6) as pool:
            sample['health'] = dict(pool.map(lambda item: probe(*item), [
                ('swe5006-api', 'https://swe5006.seventh720.com/actuator/health'),
                ('swe5006-web', 'https://swe5006.seventh720.com/healthz'),
                ('swe5001-web', 'https://' + domain + '/'),
                ('swe5001-identity', 'https://' + domain + '/health/identity'),
                ('swe5001-event-catalog', 'https://' + domain + '/health/event-catalog'),
                ('swe5001-admission', 'https://' + domain + '/health/admission'),
            ]))
        conditions = {'lowMemory': sample['availableMemoryMiB'] < 384,
                      'hostOverload': args.load1_limit > 0 and sample['load1'] > args.load1_limit,
                      'containerMemory': any(float(c['MemPerc'].rstrip('%')) > 95 for c in sample['containers'])}
        conditions.update({name: not value['ok'] or value['seconds'] > args.health_latency_limit
                           for name, value in sample['health'].items()})
        for name, value in conditions.items():
            bad[name] = bad.get(name, 0) + 1 if value else 0
        reasons = [name for name, count in bad.items() if count >= 3]
        if sample['identityChanged']:
            reasons.append('containerRestartedOrReplaced')
        if any(row.split('|')[1] != 'true' or row.split('|')[2] == 'true' for row in sample['states']):
            reasons.append('stoppedOrOOMContainer')
        sample['stopReasons'] = reasons
    except Exception as error:
        sample['error'] = type(error).__name__
        sample['stopReasons'] = ['monitorUnavailable']
    print(json.dumps(sample), flush=True)
    sample_count += 1
    if sample['stopReasons'] or (args.samples and sample_count >= args.samples):
        break
    time.sleep(max(0, 5 - (time.monotonic() - started)))
