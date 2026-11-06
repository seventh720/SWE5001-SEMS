#!/usr/bin/env python3
"""Offline checks for the explicitly authorized maintenance database boundary."""
import copy
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

spec = importlib.util.spec_from_file_location('maintenance', Path(__file__).with_name('cloud-maintenance.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BoundaryTest(unittest.TestCase):
    def test_replica_traffic_requires_business_requests(self):
        self.assertEqual(m.business_traffic_counts('GET /actuator/health 200 10\n', 'identity'), {})
        self.assertEqual(m.business_traffic_counts('GET /api/v1/auth/me 200 10\n', 'identity'), {'200': 1})
        self.assertEqual(m.business_traffic_counts('GET /api/v1/events 200 10\n', 'event-catalog'), {'200': 1})
        self.assertEqual(m.business_traffic_counts('POST /api/v1/bookings 200 10\n', 'admission'), {'200': 1})

    def test_original_and_arbitrary_database_names_are_rejected(self):
        for database in ('sems', 'postgres', 'sems_validation_', 'sems_validation_abcdef123456; DROP DATABASE sems',
                         'sems_validation_ABCDEF123456'):
            with self.subTest(database=database), self.assertRaises(ValueError):
                m.require_test_database(database)

    def test_active_target_requires_same_namespace_run_database_and_storage(self):
        state = {'testDatabase': 'sems_validation_abcdef123456', 'namespaceUid': 'namespace',
                 'runId': 'abcdef123456', 'postgresUid': 'pg', 'pvcUid': 'pvc'}
        namespace = {'metadata': {'name': 'sems-prod', 'uid': 'namespace'}}
        config = {'metadata': {'annotations': {m.ANNOTATION: state['runId']}},
                  'data': m.database_urls(state['testDatabase'])}
        pg = {'metadata': {'uid': 'pg'}}
        pvc = {'metadata': {'uid': 'pvc'}}
        m.validate_active(state, namespace, config, pg, pvc)
        cases = []
        original_db = copy.deepcopy(config)
        original_db['data']['ADMISSION_DB_URL'] = 'jdbc:postgresql://postgres:5432/sems?currentSchema=admission'
        cases.append((namespace, original_db, pg, pvc))
        cases.append((namespace, {'metadata': {}, 'data': config['data']}, pg, pvc))
        cases.append(({'metadata': {'name': 'sems-prod', 'uid': 'different'}}, config, pg, pvc))
        cases.append((namespace, config, {'metadata': {'uid': 'replacement'}}, pvc))
        cases.append((namespace, config, pg, {'metadata': {'uid': 'replacement'}}))
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.validate_active(state, *args)

    def test_maintenance_gate_keeps_internal_service_calls_and_health_readable(self):
        source = (m.ROOT / 'deployment/gateway/nginx.conf').read_text()
        text = m.gateway_config(source, 'a' * 48)
        self.assertIn('~^(GET|HEAD|OPTIONS): 1;', text)
        self.assertIn('~^[A-Z]+:' + 'a' * 48 + '$ 1;', text)
        self.assertIn('/tmp/sems-maintenance/access.jsonl', text)
        internal = text.split('listen 8080;')[1].split('listen 80;')[0]
        self.assertNotIn('if ($sems_maintenance_allowed', internal)
        self.assertEqual(text.count('if ($sems_maintenance_allowed'), 1)
        self.assertIn('benchmark_phase', text)

    def test_mutating_cli_requires_explicit_maintenance_authorization(self):
        result = subprocess.run([sys.executable, m.__file__, '--output', '/nonexistent', '--action', 'execute'],
                                capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Explicit --maintenance-window', result.stderr)


if __name__ == '__main__':
    unittest.main()
