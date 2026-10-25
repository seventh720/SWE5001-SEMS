#!/usr/bin/env python3
"""Validate real component configs in isolated, pinned containers; no cluster access."""
import concurrent.futures
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'deployment/observability/config'
IMAGES = json.loads((CONFIG.parent / 'images.lock.json').read_text())


def check(name, arguments, entrypoint=None):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--memory', '768m',
           '--tmpfs', '/var/lib/otelcol:mode=1777',
           '-v', str(CONFIG) + ':/config:ro', '-v', str(CONFIG) + ':/etc/prometheus:ro']
    if entrypoint:
        cmd += ['--entrypoint', entrypoint]
    result = subprocess.run(cmd + [IMAGES[name]['image']] + arguments,
                            capture_output=True, text=True, timeout=240)
    return name, result.returncode, result.stdout + result.stderr


def main():
    tasks = [
        ('prometheus', ['check', 'config', '--syntax-only', '/config/prometheus.yml'], '/bin/promtool'),
        ('prometheus', ['test', 'rules', '/config/rules.test.yml'], '/bin/promtool'),
        ('alertmanager', ['check-config', '/config/alertmanager.yml'], '/bin/amtool'),
        ('otel-collector', ['validate', '--config=/config/otel.yml']),
        ('otel-collector', ['validate', '--config=/config/log-agent.yml']),
        ('loki', ['-config.file=/config/loki.yml', '-verify-config=true']),
        ('tempo', ['-config.file=/config/tempo.yml', '-config.verify=true']),
    ]
    failed = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(check, *task) for task in tasks]
        for future in concurrent.futures.as_completed(futures):
            name, code, output = future.result()
            print(('PASS ' if code == 0 else 'FAIL ') + name, flush=True)
            if code:
                print(output[-6000:], flush=True)
                failed = True
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
