#!/usr/bin/env python3
"""Run a guarded cloud capacity ladder from a separate local Docker generator."""
import argparse
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import subprocess
import threading
import uuid


def plan(max_vus, modes=('read', 'mixed'), contention=True):
    levels = [n for n in (50, 100, 250, 500, 1000) if n <= max_vus]
    return [(mode, 1, '5s') for mode in modes] + [
        (mode, n, '180s' if n >= 500 else '30s')
        for mode in modes for n in levels
    ] + ([('contention', max_vus, '60s')] if contention else [])


def now():
    return datetime.now(timezone.utc).isoformat()


def summarize(metrics):
    hold_samples = sum(v['count'] for k, v in metrics.items()
                       if k.startswith('http_reqs{') and 'phase:hold' in k)
    result = {
        'requests': metrics['http_reqs']['count'],
        'unexpectedErrorRate': metrics['unexpected_failure']['value'],
        'p95Ms': (metrics['http_req_duration{phase:hold}']['p(95)'] if hold_samples else None)
                 if 'http_req_duration{phase:hold}' in metrics else metrics['http_req_duration']['p(95)'],
        'holdRequests': hold_samples,
        'overallP95Ms': metrics['http_req_duration']['p(95)'],
        'observedPeakVUs': metrics.get('vus', {}).get('max'),
        # --summary-export booleans mean threshold FAILED, unlike handleSummary().
        'failedThresholds': [k for k, v in metrics.items() if any(v.get('thresholds', {}).values())],
    }
    for key in ('bookings_created', 'sold_out'):
        if key in metrics:
            result[key] = metrics[key]['count']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--identity-file', type=Path, required=True)
    parser.add_argument('--known-hosts', type=Path, required=True)
    parser.add_argument('--host', default='ubuntu@18.139.212.35')
    parser.add_argument('--max-vus', type=int, choices=[50, 100, 250, 500, 1000], default=1000)
    parser.add_argument('--modes', nargs='+', choices=['read', 'mixed'], default=['read', 'mixed'])
    parser.add_argument('--skip-contention', action='store_true', help='Run only the selected steady workloads')
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    dataset = args.dataset.resolve(strict=True)
    data = json.loads(dataset.read_text())
    if (data['baseUrl'] != 'https://swe5001.seventh720.com' or len(data['users']) < args.max_vus
            or not data.get('hotEvent', {}).get('ticketTypeId') or not data.get('events')
            or any(not u.get('token') for u in data['users'][:args.max_vus])):
        parser.error('Require cloud fixtures, sufficient distinct users and a dedicated hot event')
    # Reject credentials that cannot cover the complete ladder comfortably.
    refreshed = datetime.fromisoformat(data['tokensRefreshedAt'])
    if (datetime.now(timezone.utc) - refreshed).total_seconds() > 900:
        parser.error('Refresh dataset tokens before starting this suite')
    reports = args.reports.resolve()
    reports.mkdir(parents=True, exist_ok=True)
    if (reports / 'run.json').exists():
        parser.error('Choose a fresh reports directory')
    script = Path(__file__).with_name('cloud-capacity.js').resolve()
    guard = Path(__file__).with_name('cloud-guard.py').resolve()
    run_id = uuid.uuid4().hex[:12]
    container = 'sems5001-capacity-' + run_id
    remote_guard = '/tmp/sems5001-capacity-guard-' + run_id + '.py'
    ssh = ['ssh', '-i', str(args.identity_file.resolve(strict=True)), '-o', 'BatchMode=yes',
           '-o', 'StrictHostKeyChecking=yes', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
           '-o', 'UserKnownHostsFile=' + str(args.known_hosts.resolve(strict=True)), args.host]
    with guard.open() as source:
        subprocess.run(ssh + ['umask 077; cat > ' + remote_guard], stdin=source, check=True)
    monitor = subprocess.Popen(ssh + ['python3 -u ' + remote_guard + ' --load1-limit 0'],
                               stdout=subprocess.PIPE, text=True)
    stopping = threading.Event()
    ready = threading.Event()
    state = {'runId': run_id, 'applicationCommit': args.commit, 'dataset': data['runId'],
             'fixtureUsers': len(data['users']), 'fixtureEvents': len(data['events']) + 1,
             'scriptSha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in (Path(__file__), script, guard)},
             'target': data['baseUrl'], 'maxVUs': args.max_vus, 'startedAt': now(),
             'plan': plan(args.max_vus, args.modes, not args.skip_contention), 'status': 'RUNNING', 'suite': [],
             'cloud': {'cpus': 2, 'memoryMiB': 3832, 'sharedWith': 'SWE5006', 'replicasPerJavaService': 1},
             'model': {'thinkSeconds': 1, 'rampSeconds': 30, 'readRequestsPerIteration': 4,
                       'mixedWriteEveryIterations': 5, 'maxWritesPerVU': 60},
             'generator': {'k6': '1.3.0', 'cpuLimit': 4, 'memoryGiB': 2},
             'guard': {'healthSeconds': 5, 'probeTimeoutSeconds': 6, 'badSamples': 3,
                       'availableMemoryMiB': 384, 'containerMemoryPercent': 95,
                       'latencyGoalMs': 3000, 'stopAfterAnyFailedStage': True}}

    def save():
        (reports / 'run.json').write_text(json.dumps(state, indent=2) + '\n')

    def stop_load():
        subprocess.run(['docker', 'stop', '--time', '3', container], capture_output=True, timeout=20)

    def watch():
        try:
            with (reports / 'resources.jsonl').open('x') as out:
                for line in monitor.stdout:
                    sample = json.loads(line)
                    out.write(line)
                    out.flush()
                    if sample.get('stopReasons'):
                        state['guardStop'] = sample
                        break
                    ready.set()
        except Exception as error:
            state['monitorError'] = type(error).__name__
        finally:
            if not stopping.is_set():
                state.setdefault('guardStop', {'stopReasons': ['monitorDisconnected']})
                stopping.set()
                stop_load()

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    save()
    try:
        if not ready.wait(30) or stopping.is_set():
            raise RuntimeError('Cloud monitor unavailable or unhealthy')
        for mode, vus, hold in plan(args.max_vus, args.modes, not args.skip_contention):
            if stopping.is_set():
                raise RuntimeError('Health guard stopped the experiment')
            name = f'{mode}-{vus}vu'
            command = ['docker', 'run', '--rm', '--name', container, '--cpus', '4', '--memory', '2g',
                       '--user', f'{os.getuid()}:{os.getgid()}', '-e', 'DATASET=/run/dataset.json',
                       '-e', f'MODE={mode}', '-e', f'VUS={vus}', '-e', f'HOLD={hold}', '-e', f'RUN_ID={run_id}',
                       '-v', f'{dataset}:/run/dataset.json:ro', '-v', f'{script}:/scripts/capacity.js:ro',
                       '-v', f'{reports}:/reports', 'grafana/k6:1.3.0', 'run', '--quiet',
                       '--summary-export', f'/reports/{name}.json', '/scripts/capacity.js']
            record = {'name': name, 'mode': mode, 'targetVUs': vus, 'plannedHold': hold, 'startedAt': now()}
            print('START', name, now(), flush=True)
            with (reports / f'{name}.log').open('x') as log:
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                with (reports / 'generator-resources.jsonl').open('a') as generator:
                    while process.poll() is None:
                        if stopping.is_set():
                            stop_load()
                        sample = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', container],
                                                capture_output=True, text=True, timeout=15)
                        if sample.returncode == 0 and sample.stdout.strip():
                            generator.write(json.dumps({'at': now(), 'stage': name, 'stats': json.loads(sample.stdout)}) + '\n')
                            generator.flush()
                        stopping.wait(3)
                code = process.wait()
            record.update(exitCode=code, endedAt=now())
            summary = reports / f'{name}.json'
            record['summaryPresent'] = summary.exists()
            if summary.exists():
                metrics = json.loads(summary.read_text())['metrics']
                record.update(summarize(metrics))
            state['suite'].append(record)
            save()
            print('END', json.dumps(record), flush=True)
            if code or not record['summaryPresent'] or record.get('failedThresholds') or stopping.is_set():
                raise RuntimeError(f'{name} failed; higher stages were not scheduled')
            if stopping.wait(10):
                raise RuntimeError('Health guard stopped during recovery interval')
        state['status'] = 'PASSED'
    except BaseException as error:
        state.update(status='STOPPED', reason=str(error))
        raise
    finally:
        stopping.set()
        stop_load()
        monitor.terminate()
        monitor.wait(timeout=15)
        watcher.join(timeout=15)
        subprocess.run(ssh + ['rm -f ' + remote_guard], capture_output=True, timeout=20)
        state['endedAt'] = now()
        save()


if __name__ == '__main__':
    main()
