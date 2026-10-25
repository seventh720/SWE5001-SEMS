#!/usr/bin/env python3
"""Verify live namespaces stop fixture/fault entry points before any mutation."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from environment_guard import require_disposable_namespace

ROOT = Path(__file__).resolve().parents[2]


class EnvironmentGuardTest(unittest.TestCase):
    def test_test_and_legacy_unmarked_namespaces_remain_supported(self):
        for annotations in ({}, {'sems.seventh720.com/environment': 'test'}):
            with patch('environment_guard.subprocess.check_output', return_value=json.dumps(
                    {'metadata': {'annotations': annotations}})):
                require_disposable_namespace(['kubectl'])

    def test_production_name_is_protected_without_annotation(self):
        with patch('environment_guard.subprocess.check_output', return_value=json.dumps(
                {'metadata': {'annotations': {}}})):
            with self.assertRaises(RuntimeError):
                require_disposable_namespace(['kubectl'], namespace='sems-prod')

    def test_unavailable_cluster_fails_closed(self):
        with patch('environment_guard.subprocess.check_output', side_effect=subprocess.CalledProcessError(1, 'kubectl')):
            with self.assertRaises(subprocess.CalledProcessError):
                require_disposable_namespace(['kubectl'])

    def test_five_live_entry_points_refuse_before_any_cluster_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / 'commands.jsonl'
            stub = root / 'kubectl'
            stub.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
with Path(os.environ['SEMS_GUARD_TEST_LOG']).open('a') as f:
    f.write(json.dumps(sys.argv[1:])+'\\n')
if sys.argv[-5:] != ['get','namespace','sems-test','-o','json']:
    raise SystemExit(92)
print(json.dumps({'metadata': {'annotations': {'sems.seventh720.com/environment':'production'}}}))
''')
            stub.chmod(0o700)
            # catalog-recovery reads only these settings before constructing its runtime.
            env_file = root / 'fixture.env'
            env_file.write_text('SEMS_BOOTSTRAP_ADMIN_EMAIL=test@example.invalid\nSEMS_BOOTSTRAP_ADMIN_PASSWORD=not-a-real-password\n')
            cases = {
                'business-regression.py': ['--env-file', str(env_file), '--output', str(root/'reports')],
                'catalog-recovery.py': ['--env-file', str(env_file), '--report', str(root/'catalog.json')],
                'service-lifecycle.py': ['--report', str(root/'lifecycle.json')],
                'postgres-acceptance.py': ['--report', str(root/'postgres.json')],
                'local-acceptance.py': ['--environment','k3s','--env-file',str(env_file),'--report',str(root/'business.json')],
            }
            env = {**os.environ, 'PATH': str(root)+os.pathsep+os.environ['PATH'],
                   'SEMS_GUARD_TEST_LOG': str(log)}
            for name, arguments in cases.items():
                with self.subTest(script=name):
                    result = subprocess.run([sys.executable,str(ROOT/'scripts/k8s'/name),
                                             '--kubeconfig',str(root/'unused-kubeconfig'),*arguments],
                                            cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
                    self.assertNotEqual(result.returncode,0)
                    self.assertIn('Refusing fixture/fault tests in production namespace', result.stderr)
            self.assertEqual(len(log.read_text().splitlines()),len(cases))


if __name__ == '__main__':
    unittest.main()
