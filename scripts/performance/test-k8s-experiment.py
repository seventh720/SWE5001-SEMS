#!/usr/bin/env python3
"""Offline checks for destructive-target guards and benchmark business evidence."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

spec = importlib.util.spec_from_file_location('k8s_experiment', Path(__file__).with_name('k8s-experiment.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def config(server='https://127.0.0.1:12345'):
    return {'contexts': [{'name': module.CONTEXT, 'context': {'cluster': module.CONTEXT}}],
            'clusters': [{'name': module.CONTEXT, 'cluster': {'server': server}}]}


def namespace(name=module.NAMESPACE, environment='benchmark'):
    return {'metadata': {'name': name, 'annotations': {'sems.seventh720.com/environment': environment}}}


class GuardTest(unittest.TestCase):
    def test_explicit_local_benchmark_is_allowed(self):
        module.validate_target(config(), namespace())

    def test_remote_api_and_production_namespace_are_rejected(self):
        cases = [(config('https://13.229.121.219:6443'), namespace()),
                 (config(), namespace('sems-prod')),
                 (config(), namespace(environment='production')),
                 (config(), {'metadata': {'name': module.NAMESPACE}})]
        for target, ns in cases:
            with self.subTest(target=target, namespace=ns), self.assertRaises(ValueError):
                module.validate_target(target, ns)

    def test_similar_context_name_cannot_select_a_different_cluster(self):
        target = config()
        target['contexts'][0]['context']['cluster'] = 'sems-k3s'
        with self.assertRaises(ValueError):
            module.validate_target(target, namespace())

    def test_entrypoint_rejects_live_marker_before_creating_output_or_mutating_cluster(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'commands.jsonl'
            stub = root / 'kubectl'
            stub.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
with Path(os.environ['SEMS_BENCHMARK_TEST_LOG']).open('a') as stream:
    stream.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[-4:] == ['config','view','-o','json']:
    print(os.environ['SEMS_BENCHMARK_TEST_CONFIG'])
elif sys.argv[-5:] == ['get','namespace','sems-benchmark','-o','json']:
    print(os.environ['SEMS_BENCHMARK_TEST_NAMESPACE'])
else:
    raise SystemExit(92)
''')
            stub.chmod(0o700)
            env_file = root / 'runtime.env'
            env_file.write_text('SEMS_BOOTSTRAP_ADMIN_EMAIL=fake@example.invalid\nSEMS_BOOTSTRAP_ADMIN_PASSWORD=fake\n')
            out = module.ROOT / '.performance' / ('guard-test-' + uuid.uuid4().hex)
            result = subprocess.run([sys.executable, str(Path(module.__file__)), '--kubeconfig', str(root/'unused'),
                                     '--env-file', str(env_file), '--output', str(out)], cwd=module.ROOT,
                                    env={**os.environ, 'PATH': str(root)+os.pathsep+os.environ['PATH'],
                                         'SEMS_BENCHMARK_TEST_LOG': str(log),
                                         'SEMS_BENCHMARK_TEST_CONFIG': json.dumps(config()),
                                         'SEMS_BENCHMARK_TEST_NAMESPACE': json.dumps(namespace(environment='production'))},
                                    capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('explicitly marked disposable', result.stderr)
            self.assertFalse(out.exists())
            self.assertEqual(len(log.read_text().splitlines()), 2)


class EvidenceTest(unittest.TestCase):
    def test_database_cpu_cleanup_restores_resources_without_touching_storage(self):
        experiment = object.__new__(module.Experiment)
        experiment.kube = ['kubectl']
        resources = {'requests': {'cpu': '100m', 'memory': '128Mi'},
                     'limits': {'cpu': '1', 'memory': '512Mi'}}
        experiment.original_postgres = {'metadata': {}, 'spec': {'containers': [
            {'name': 'postgres', 'resources': resources}]}}
        current = {'metadata': {'annotations': {module.CPU_ROUND_ANNOTATION: 'round1'}},
                   'spec': {'containers': [{'name': 'postgres', 'resources': {
                       'requests': resources['requests'], 'limits': {'cpu': '2', 'memory': '512Mi'}}}]}}
        experiment.kube_json = lambda *_: {'spec': {'template': current}}
        commands = []
        experiment.command = lambda args, **_: commands.append(args)
        experiment.postgres_ready = lambda: None
        experiment.restore_postgres_template()
        patch = json.loads(commands[0][-1])
        self.assertEqual(patch, [
            {'op': 'replace', 'path': '/spec/template/spec/containers/0/resources', 'value': resources},
            {'op': 'remove', 'path': '/spec/template/metadata/annotations'}])

    def test_database_cpu_cli_rejects_simultaneously_changing_admission_replicas(self):
        result = subprocess.run([sys.executable, module.__file__, '--kubeconfig', 'unused',
            '--env-file', 'unused', '--output', '.performance/not-created-db-cpu-check',
            '--modes', 'booking', '--replica-counts', '1', '2', '--postgres-cpu-limits', '1', '2'],
            capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Admission fixed at 2', result.stderr)

    def test_gateway_requires_complete_measurement_and_detects_hidden_retry(self):
        entry = {'status': 200, 'server_port': 80, 'path': '/api/v1/bookings',
                 'benchmark_run': 'run1', 'benchmark_phase': 'measurement', 'upstream_status': '200'}
        internal = {'status': 200, 'server_port': 8080, 'path': '/internal/v1/events/id',
                    'upstream_status': '504, 200'}
        clean = module.gateway_evidence([json.dumps(entry)], 'run1', 1)
        self.assertTrue(clean['serverGatePassed'])
        self.assertFalse(module.gateway_evidence([json.dumps(entry)], 'run1', 2)['measurementCoveragePassed'])
        retry = module.gateway_evidence(map(json.dumps, [entry, internal]), 'run1', 1)
        self.assertTrue(retry['measurementCoveragePassed'])
        self.assertFalse(retry['serverGatePassed'])
        self.assertEqual(retry['upstreamErrorsByStatus'], {'504': 1})
        self.assertFalse(module.gateway_evidence([json.dumps({**entry, 'status': 500,
            'upstream_status': '-'})], 'run1', 1)['serverGatePassed'])
        self.assertFalse(module.gateway_evidence(['broken'], 'run1', 1)['serverGatePassed'])

    def test_sleep_or_clock_jump_invalidates_continuous_sampling(self):
        module.check_sample_continuity(None, '2026-10-25T16:00:00+00:00')
        module.check_sample_continuity('2026-10-25T16:00:00+00:00', '2026-10-25T16:00:05+00:00')
        for current in ('2026-10-25T16:02:46+00:00', '2026-10-25T15:59:59+00:00'):
            with self.subTest(current=current), self.assertRaises(RuntimeError):
                module.check_sample_continuity('2026-10-25T16:00:00+00:00', current)

    def test_audit_rejects_overselling_missing_inventory_and_ticket_mismatch(self):
        good = [{'quota': 10, 'reserved': 3, 'confirmed': 3, 'tickets': 3}]
        self.assertTrue(module.inventory_passed(good, 1))
        for rows in ([], [{**good[0], 'reserved': 11, 'confirmed': 11, 'tickets': 11}],
                     [{**good[0], 'tickets': 2}], [{**good[0], 'reserved': -1}]):
            self.assertFalse(module.inventory_passed(rows, 1))

    def test_dataset_ids_cannot_inject_a_sql_query(self):
        with self.assertRaises(ValueError):
            module.inventory_query({'events': [{'eventId': "x'; DROP TABLE bookings; --"}]})
        with self.assertRaises(ValueError):
            module.inventory_query({'events': []})

    def test_ready_and_internal_calls_do_not_prove_business_traffic(self):
        logs = '\n'.join(['GET /actuator/health/readiness 200 3',
                          'GET /internal/v1/events/abc 200 5',
                          'GET /api/v1/events 200 11', 'GET /api/v1/events/abc 503 15',
                          'POST /api/v1/bookings 200 21', 'GET /api/v1/bookings/def 200 5'])
        self.assertEqual(module.traffic_counts(logs, 'catalog'), {'200': 1, '503': 1})
        self.assertEqual(module.traffic_counts(logs, 'booking'), {'200': 2})


if __name__ == '__main__':
    unittest.main()
