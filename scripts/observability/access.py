#!/usr/bin/env python3
"""Open a localhost-only Grafana console through the existing K3s SSH tunnel."""
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def main():
    children = []
    try:
        try:
            with socket.create_connection(('127.0.0.1', 16443), timeout=1):
                pass
        except OSError:
            children.append(subprocess.Popen([
                'ssh', '-N', '-i', str(ROOT / '.secrets/k3s-cloud/ssh.pem'),
                '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                '-o', 'UserKnownHostsFile="' + str(ROOT / '.secrets/k3s-cloud/known_hosts') + '"',
                '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30',
                '-L', '127.0.0.1:16443:127.0.0.1:6443', 'ubuntu@13.229.121.219']))
            for _ in range(30):
                time.sleep(0.2)
                if children[-1].poll() is not None:
                    raise RuntimeError('SSH tunnel did not start')
                try:
                    with socket.create_connection(('127.0.0.1', 16443), timeout=0.2):
                        break
                except OSError:
                    continue
        k = ['kubectl', '--kubeconfig', str(ROOT / '.secrets/k3s-cloud/kubeconfig'),
             '--context', 'sems-k3s', '--cache-dir', str(ROOT / '.secrets/observability/cache')]
        nodes = subprocess.check_output(k + ['get', 'nodes', '-o', 'name'], text=True)
        if set(nodes.split()) != {'node/sems-k3s-server', 'node/sems-k3s-worker'}:
            raise RuntimeError('Unexpected cluster on the local tunnel')
        log_path = ROOT / '.secrets/observability/access.log'
        log_path.touch(mode=0o600, exist_ok=True)
        log = log_path.open('a')
        print('Grafana: http://127.0.0.1:13000/d/sems-operations\n'
              'Credentials: .secrets/observability/grafana-login.txt\n'
              'Keep this terminal open; Ctrl-C closes the console tunnel.', flush=True)
        while True:
            console = subprocess.Popen(k + ['-n', 'observability', 'port-forward', '--address=127.0.0.1',
                                          'service/grafana', '13000:3000'], stdout=log, stderr=log)
            children.append(console)
            while console.poll() is None:
                time.sleep(5)
                try:
                    with urllib.request.urlopen('http://127.0.0.1:13000/api/health', timeout=5):
                        pass
                except Exception:
                    console.terminate()
                    console.wait(timeout=10)
                    break
            print('Reconnecting Grafana tunnel after Pod/connection change...', flush=True)
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.send_signal(signal.SIGTERM)
                child.wait(timeout=10)


if __name__ == '__main__':
    main()
