#!/usr/bin/env python3
"""Run the existing business assertions against sems-k3s/sems-test, without Docker.

The legacy suites express fixture SQL and service lifecycle operations as Compose
commands. This adapter translates only those known operations into real kubectl
operations; unsupported container commands fail closed. Each suite has its own
Python process, unique fixtures, log and JSON result. It deliberately excludes
the legacy-data migration and Docker-specific topology tests.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace

from environment_guard import require_disposable_namespace

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://sems-test.seventh720.com'
SUITES = (
    'business-fixes', 'organization', 'catalog-read', 'organization-security',
    'event-directory', 'organization-management', 'visibility', 'notifications',
    'membership-notifications', 'organization-governance', 'event-cancellation',
    'predeployment-fixes',
)
SERVICES = ('identity', 'event-catalog', 'admission', 'gateway', 'web')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


class KubernetesRuntime:
    def __init__(self, kubeconfig):
        self.k = ['kubectl', '--kubeconfig', str(Path(kubeconfig).resolve()),
                  '--context', 'sems-k3s', '--cache-dir', str(ROOT / '.secrets/k3s-cloud/cache'),
                  '-n', 'sems-test']
        require_disposable_namespace(self.k)
        self.run = subprocess.run
        self.replicas = {}
        self.actions = []

    def command(self, *args):
        result = self.run(self.k + list(args), capture_output=True, text=True, timeout=240)
        if result.returncode:
            raise RuntimeError('kubectl ' + ' '.join(args[:2]) + ': ' + result.stderr.strip())
        return result.stdout.strip()

    def snapshot(self):
        data = json.loads(self.command('get', 'deployments', '-o', 'json'))
        self.replicas = {d['metadata']['name']: d['spec']['replicas'] for d in data['items']}
        assert set(self.replicas) == set(SERVICES), 'Unexpected test deployment inventory'
        assert all(n == 2 for n in self.replicas.values()), 'Expected two replicas per test deployment'

    def scale(self, service, count):
        self.command('scale', 'deployment/' + service, '--replicas=' + str(count))
        if count:
            self.command('rollout', 'status', 'deployment/' + service, '--timeout=210s')
        else:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                pods = json.loads(self.command('get', 'pods', '-l', 'app.kubernetes.io/name=' + service, '-o', 'json'))
                if not pods['items']:
                    return
                time.sleep(.5)
            raise RuntimeError('Pods did not stop: ' + service)

    def restore(self):
        errors = []
        for service, count in self.replicas.items():
            try:
                actual = int(self.command('get', 'deployment/' + service, '-o', 'jsonpath={.spec.replicas}'))
                if actual != count:
                    self.scale(service, count)
                else:
                    self.command('rollout', 'status', 'deployment/' + service, '--timeout=210s')
            except Exception as error:
                errors.append(str(error))
        if errors:
            raise RuntimeError('; '.join(errors))

    def dispatch(self, command, *positional, **options):
        if not isinstance(command, (list, tuple)) or not command or command[0] != 'docker':
            return self.run(command, *positional, **options)
        assert command[:2] == ['docker', 'compose'], 'Docker-specific operations are unsupported in K3s'
        index = 2
        while command[index] in ('--env-file', '-f'):
            index += 2
        operation, *arguments = command[index:]
        if operation == 'exec':
            assert arguments.pop(0) == '-T'
            service = arguments.pop(0)
            assert service in ('postgres', 'gateway'), 'Unsupported fixture exec target'
            target = 'postgres-0' if service == 'postgres' else 'deployment/gateway'
            return self.run(self.k + ['exec', '-i', target, '--'] + arguments, *positional, **options)
        assert operation in ('stop', 'start', 'restart'), 'Unsupported legacy operation: ' + operation
        assert arguments and all(s in self.replicas for s in arguments)
        for service in arguments:
            print('K3S: ' + operation + ' ' + service, flush=True)
            self.actions.append({'at': now(), 'operation': operation, 'deployment': service})
            if operation == 'restart':
                self.command('rollout', 'restart', 'deployment/' + service)
                self.command('rollout', 'status', 'deployment/' + service, '--timeout=210s')
            else:
                self.scale(service, 0 if operation == 'stop' else self.replicas[service])
        # Lifecycle callers discard stdout. All actual operations above must succeed.
        return subprocess.CompletedProcess(command, 0, '' if options.get('text') else b'', '' if options.get('text') else b'')


def child(args):
    runtime = KubernetesRuntime(args.kubeconfig)
    report = {'suite': args.suite, 'startedAt': now(), 'baseUrl': BASE,
              'environment': 'sems-k3s/sems-test', 'status': 'running'}
    script = ROOT / ('scripts/' + args.suite + '-acceptance.py')
    report['assertionScriptSha256'] = hashlib.sha256(script.read_bytes()).hexdigest()
    try:
        runtime.snapshot()
        subprocess.run = runtime.dispatch
        # This directory also has a credential renderer named secrets.py. Legacy
        # assertions import the standard-library secrets module, so don't expose
        # the renderer directory as a general Python import search path.
        directory = Path(__file__).resolve().parent
        sys.path[:] = [entry for entry in sys.path if Path(entry or os.curdir).resolve() != directory]
        sys.path.insert(0, str(ROOT / 'scripts'))
        if args.suite == 'organization-management':
            # Reuse its full assertion class with the explicit K3s fixture transport.
            # Its CLI intentionally restricts the old Compose mode to localhost.
            namespace = runpy.run_path(str(script), run_name='k3s_organization_management')
            options = SimpleNamespace(base_url=BASE, live=False, report=str(args.output / 'organization-management-details.json'),
                                      env_file=args.env_file, compose_file='deployment/compose.yaml')
            suite = namespace['Acceptance'](options)
            suite.report['mode'] = 'k3s-test-fixtures'
            try:
                suite.run()
            finally:
                suite.cleanup()
        else:
            sys.argv = [str(script)]
            runpy.run_path(str(script), run_name='__main__')
        report['status'] = 'passed'
    except BaseException as error:
        report['status'] = 'failed'
        report['error'] = type(error).__name__ + ': ' + str(error)
        traceback.print_exc()
    finally:
        subprocess.run = runtime.run
        try:
            runtime.restore()
            report['replicasRestored'] = True
        except Exception as error:
            report['replicasRestored'] = False
            report['cleanupError'] = str(error)
            report['status'] = 'failed'
        report['actions'] = runtime.actions
        report['completedAt'] = now()
        save(args.output / (args.suite + '.json'), report)
    return 0 if report['status'] == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--suite', choices=SUITES, help=argparse.SUPPRESS)
    parser.add_argument('--only', nargs='+', choices=SUITES)
    args = parser.parse_args()
    os.chdir(ROOT)
    if not args.suite:
        KubernetesRuntime(args.kubeconfig)  # Refuse live data before launching fixture suites.
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('k8s_secrets', ROOT / 'scripts/k8s/secrets.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = module.read_env(args.env_file)
    for key in ('SEMS_BOOTSTRAP_ADMIN_EMAIL', 'SEMS_BOOTSTRAP_ADMIN_PASSWORD', 'ADMISSION_TO_CATALOG_TOKEN'):
        os.environ[key] = values[key]
    os.environ['SEMS_BASE_URL'] = BASE
    os.environ['SEMS_ENV_FILE'] = str(Path(args.env_file).resolve())
    # Use the verified OS/certifi trust store; never disable certificate checking.
    try:
        import certifi
    except ImportError:
        pass  # Python's system trust store remains enabled.
    else:
        os.environ['SSL_CERT_FILE'] = certifi.where()
    if args.suite:
        return child(args)
    report = {'environment': 'sems-k3s/sems-test', 'baseUrl': BASE, 'startedAt': now(),
              'status': 'running', 'suites': [],
              'excluded': ['legacy-data migration (separate migration exercise)',
                           'Docker DNS scaling (replaced by K3s service lifecycle acceptance)',
                           'Docker cold restart (separate native K3s recovery test)']}
    for name in (args.only or SUITES):
        print('START: ' + name, flush=True)
        log = args.output / (name + '.log')
        with log.open('w') as output:
            result = subprocess.run([sys.executable, '-u', str(Path(__file__).resolve()),
                '--kubeconfig', args.kubeconfig, '--env-file', args.env_file,
                '--output', str(args.output), '--suite', name], stdout=output, stderr=subprocess.STDOUT)
        item = json.loads((args.output / (name + '.json')).read_text())
        lines = log.read_text().splitlines()
        # Summaries contain statuses and assertion descriptions, never fixture secrets.
        item['passedAssertionGroups'] = [line.removeprefix('PASS: ') for line in lines if line.startswith('PASS: ')]
        item['log'] = log.name
        report['suites'].append(item)
        print(item['status'].upper() + ': ' + name + ' (' + str(len(item['passedAssertionGroups'])) + ' groups)', flush=True)
        if result.returncode:
            print(item.get('error', item.get('cleanupError', 'Child failed')), flush=True)
        save(args.output / 'summary.json', report)
        time.sleep(3)  # Separate authentication budgets between suites.
    report['completedAt'] = now()
    report['status'] = 'passed' if all(s['status'] == 'passed' for s in report['suites']) else 'failed'
    save(args.output / 'summary.json', report)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
