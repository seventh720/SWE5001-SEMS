#!/usr/bin/env python3
"""Manage the separate SEMS observability stack through an explicit kubeconfig."""
import argparse
import contextlib
import base64
import datetime
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
BACKENDS = ('identity', 'event-catalog', 'admission')


def run(command, data=None, check=True, timeout=90):
    result = subprocess.run(command, input=data, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        # Inputs may contain Secrets. Never echo stdin, full command arguments or Secret objects.
        raise RuntimeError('Kubernetes operation failed: ' + result.stderr[-1500:])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--context', default='sems-k3s')
    parser.add_argument('--private-dir', type=Path, default=ROOT / '.secrets/observability')
    parser.add_argument('operation', choices=['install', 'instrument', 'telegram'])
    args = parser.parse_args()
    with cd_lock() if args.operation == 'instrument' else contextlib.nullcontext():
        execute(args)


@contextlib.contextmanager
def cd_lock():
    ssh = ['ssh', '-i', str(ROOT / '.secrets/k3s-cloud/ssh.pem'),
           '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
           '-o', 'ConnectTimeout=10', '-o', 'UserKnownHostsFile="' + str(ROOT / '.secrets/k3s-cloud/known_hosts') + '"',
           'ubuntu@13.229.121.219',
           "sudo flock -n /var/lib/sems-cd/deploy.lock python3 -u -c 'import sys;print(\"LOCKED\",flush=True);sys.stdin.readline()'"]
    process = subprocess.Popen(ssh, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    acquired = False
    try:
        if process.stdout.readline().strip() != 'LOCKED':
            raise RuntimeError('CD deployment lock unavailable; no application instrumentation applied')
        acquired = True
        print('Acquired existing CD deployment lock', flush=True)
        yield
    finally:
        if process.poll() is None:
            process.stdin.close()
            process.wait(timeout=15)
        if acquired:
            print('Released CD deployment lock', flush=True)


def execute(args):
    args.private_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(args.private_dir, 0o700)
    k = ['kubectl', '--kubeconfig', args.kubeconfig, '--context', args.context,
         '--cache-dir', str(args.private_dir / 'cache')]

    def out(*command, **kw):
        return run(k + list(command), **kw).stdout

    def get(kind, name, namespace):
        return json.loads(out('-n', namespace, 'get', kind, name, '-o', 'json'))

    def apply(obj, dry=False):
        cmd = ['apply', '-f', '-'] + (['--dry-run=server'] if dry else [])
        out(*cmd, data=json.dumps(obj))

    def ensure_secret(name, generate):
        result = run(k + ['-n', 'observability', 'get', 'secret', name, '-o', 'json'], check=False)
        if result.returncode == 0:
            return {n: base64.b64decode(v).decode() for n, v in json.loads(result.stdout)['data'].items()}
        if 'NotFound' not in result.stderr:
            raise RuntimeError('Cannot read existing observability Secret')
        values = generate()
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': name, 'namespace': 'observability'},
               'type': 'Opaque', 'stringData': values})
        return values

    ns = get('namespace', 'sems-test', 'sems-test')
    if ns['metadata'].get('annotations', {}).get('sems.seventh720.com/environment') != 'production':
        raise RuntimeError('Expected the explicitly marked SEMS production namespace')
    nodes = json.loads(out('get', 'nodes', '-o', 'json'))['items']
    if {n['metadata']['name'] for n in nodes} != {'sems-k3s-server', 'sems-k3s-worker'}:
        raise RuntimeError('Refusing an unexpected cluster layout')
    before = get('pod', 'postgres-0', 'sems-test')
    claim = get('pvc', 'data-postgres-0', 'sems-test')
    if args.operation == 'install':
        rendered = subprocess.check_output(['kubectl', 'kustomize', str(ROOT / 'deployment/observability')], text=True)
        # Kustomize can emit JSON directly through kubectl, avoiding a runtime YAML dependency.
        import yaml
        objects = list(yaml.safe_load_all(rendered))
        namespace = next(o for o in objects if o['kind'] == 'Namespace')
        existing = run(k + ['get', 'namespace', 'observability', '-o', 'json'], check=False)
        if existing.returncode == 0 and json.loads(existing.stdout)['metadata'].get('labels', {}).get('app.kubernetes.io/part-of') != 'sems-observability':
            raise RuntimeError('Refusing to adopt an unrelated observability namespace')
        apply(namespace)
        creds = ensure_secret('grafana-admin', lambda: {'username': 'admin', 'password': secrets.token_urlsafe(30)})
        login = args.private_dir / 'grafana-login.txt'
        login.write_text('URL: https://grafana.seventh720.com\nUsername: ' + creds['username'] + '\nPassword: ' + creds['password'] + '\n')
        login.chmod(0o600)
        ensure_secret('alertmanager-config', lambda: {'alertmanager.yml': (ROOT / 'deployment/observability/config/alertmanager.yml').read_text()})
        monitor = ensure_secret('postgres-monitor', lambda: {'password': secrets.token_urlsafe(30)})
        # Only a new monitoring role changes; no business tables, app grants or passwords are touched.
        password = monitor['password'].replace("'", "''")
        sql = ("DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='sems_monitor') THEN "
               "CREATE ROLE sems_monitor LOGIN; END IF; END $$;\n"
               "ALTER ROLE sems_monitor WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '" + password + "';\n"
               "GRANT pg_monitor TO sems_monitor;\n"
               "GRANT CONNECT ON DATABASE sems TO sems_monitor;\n"
               "ALTER ROLE sems_monitor SET default_transaction_read_only=on;\n"
               "ALTER ROLE sems_monitor SET statement_timeout='5s';\n")
        result = run(k + ['-n', 'sems-test', 'exec', '-i', 'postgres-0', '--',
                          'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres', '-d', 'sems', '-f', '-'],
                     data=sql, check=False)
        if result.returncode:
            raise RuntimeError('Monitoring role setup failed; SQL and credentials suppressed')
        bundle = {'apiVersion': 'v1', 'kind': 'List', 'items': objects}
        apply(bundle, dry=True)
        out('apply', '--dry-run=server', '-f', str(ROOT / 'deployment/observability/postgres-network.yaml'))
        apply(bundle)
        out('apply', '-f', str(ROOT / 'deployment/observability/postgres-network.yaml'))
        print('Applied observability stack with authenticated Grafana HTTPS and read-only database monitoring', flush=True)
        for obj in objects:
            if obj['kind'] not in ('Deployment', 'DaemonSet'):
                continue
            name = obj['metadata']['name']
            print('Waiting for ' + name, flush=True)
            out('-n', 'observability', 'rollout', 'status', obj['kind'].lower() + '/' + name,
                '--timeout=240s', timeout=260)
        print('Ready. Private Grafana credentials: ' + str(login), flush=True)
    elif args.operation == 'instrument':
        import yaml
        # The caller holds the host CD flock. Save exact before specs for recovery.
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        snapshots = []
        for name in BACKENDS:
            deployment = get('deployment', name, 'sems-test')
            snapshots.append(deployment)
        snapshot = args.private_dir / ('before-instrumentation-' + stamp + '.json')
        snapshot.write_text(json.dumps(snapshots)); snapshot.chmod(0o600)
        for name in BACKENDS:
            patch = yaml.safe_load((ROOT / 'deployment/k8s/components/telemetry' / (name + '.yaml')).read_text())
            # Patch only instrumentation; preserve live app image, replica placement and all credentials.
            data = json.dumps(patch)
            for dry in [True, False]:
                cmd = ['-n', 'sems-test', 'patch', 'deployment', name, '--type=strategic', '--patch-file=/dev/stdin']
                if dry:
                    cmd.append('--dry-run=server')
                out(*cmd, data=data)
            print('Rolling out instrumentation: ' + name, flush=True)
            try:
                out('-n', 'sems-test', 'rollout', 'status', 'deployment/' + name, '--timeout=240s', timeout=260)
            except Exception:
                # Restore only this template (including its original image), before proceeding to any next service.
                prior = next(d for d in snapshots if d['metadata']['name'] == name)
                replacement = [{'op': 'replace', 'path': '/spec/template', 'value': prior['spec']['template']}]
                out('-n', 'sems-test', 'patch', 'deployment', name, '--type=json', '--patch-file=/dev/stdin', data=json.dumps(replacement))
                out('-n', 'sems-test', 'rollout', 'status', 'deployment/' + name, '--timeout=240s', timeout=260)
                raise RuntimeError(name + ': instrumentation failed and its original template was restored')
        print('Instrumented all three backends without changing business images or data', flush=True)
    else:
        # Read dotenv as data; never source shell code from a credentials file.
        env = {}
        for line in (args.private_dir / 'telegram.env').read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
        token, chat = env.get('TELEGRAM_BOT_TOKEN', ''), env.get('TELEGRAM_CHAT_ID', '')
        if not token or not chat or not chat.lstrip('-').isdigit():
            raise RuntimeError('Fill the private telegram.env first; do not paste its values into chat')
        # Validate the existing bot/chat without sending any message or logging its token-bearing URL.
        import urllib.parse
        import urllib.request
        import ssl
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ctx = ssl.create_default_context()
        for method in ['getMe', 'getChat?' + urllib.parse.urlencode({'chat_id': chat})]:
            try:
                with urllib.request.urlopen('https://api.telegram.org/bot' + token + '/' + method,
                                            context=ctx, timeout=15) as response:
                    if not json.load(response).get('ok'):
                        raise RuntimeError('Telegram returned a failed validation')
            except Exception:
                raise RuntimeError('Telegram bot/chat verification failed; check the private configuration') from None
        import yaml
        config = yaml.safe_load((ROOT / 'deployment/observability/config/alertmanager.yml').read_text())
        config['receivers'].append({'name': 'telegram', 'telegram_configs': [{
            'bot_token_file': '/run/telegram/bot-token', 'chat_id': int(chat), 'send_resolved': True,
            'parse_mode': '', 'message': '{{ .Status | toUpper }} · SEMS\n{{ range .Alerts }}{{ .Labels.alertname }} [{{ .Labels.severity }}]\n{{ .Annotations.summary }}\n{{ end }}'}]})
        config['route']['receiver'] = 'telegram'
        # Test alerts also traverse the real receiver; use a clearly named synthetic signal only.
        apply({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'alertmanager-config', 'namespace': 'observability'},
               'type': 'Opaque', 'stringData': {'bot-token': token, 'alertmanager.yml': yaml.safe_dump(config, sort_keys=False)}})
        patch = {'spec': {'template': {'metadata': {'annotations': {'sems.seventh720.com/receiver-updated-at': str(time.time_ns())}},
            'spec': {'volumes': [{'name': 'config', 'configMap': None, 'secret': {'secretName': 'alertmanager-config'}}]}}}}
        out('-n', 'observability', 'patch', 'deployment', 'alertmanager', '--type=strategic', '--patch-file=/dev/stdin', data=json.dumps(patch))
        out('-n', 'observability', 'rollout', 'status', 'deployment/alertmanager', '--timeout=120s', timeout=140)
        print('Telegram receiver enabled; firing and resolved notifications configured', flush=True)
    after = get('pod', 'postgres-0', 'sems-test')
    after_claim = get('pvc', 'data-postgres-0', 'sems-test')
    if after['metadata']['uid'] != before['metadata']['uid'] or after_claim['metadata']['uid'] != claim['metadata']['uid']:
        raise RuntimeError('Unexpected database Pod/PVC identity change')
    print('Database Pod and PVC identities preserved', flush=True)


if __name__ == '__main__':
    main()
