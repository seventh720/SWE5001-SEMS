#!/usr/bin/env python3
"""Release boundary tests using the actual K3s manifests, without a live cluster."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml
from k3s_release import APPLICATIONS, REGISTRY, render, validate_release


class K3sReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit = 'a' * 40
        cls.release_id = cls.commit + '-123-1'
        cls.documents = list(yaml.safe_load_all(subprocess.check_output(
            ['kubectl', 'kustomize', 'deployment/k8s/overlays/k3s'], text=True)))
        cls.lock = {'x-release-commit': cls.commit, 'services': {
            service: {'image': REGISTRY + service + '@sha256:' + 'b' * 64}
            for service in (*APPLICATIONS, 'postgres', 'caddy')}}

    def release(self, lock=None):
        return render(lock or self.lock, self.commit, self.release_id, self.documents)

    def test_actual_manifests_only_update_applications(self):
        release = self.release()
        resources = release['resources']
        self.assertEqual({r['metadata']['name'] for r in resources if r['kind'] == 'Deployment'}, set(APPLICATIONS))
        self.assertFalse(any(r['kind'] in ('Secret', 'Namespace', 'StatefulSet', 'PersistentVolumeClaim',
                                         'StorageClass', 'NetworkPolicy') for r in resources))
        self.assertFalse(any(r['metadata']['name'].startswith('postgres') for r in resources))
        for r in resources:
            self.assertEqual(r['metadata']['namespace'], 'sems-test')
            if r['kind'] == 'Deployment':
                self.assertEqual(r['spec']['template']['spec']['containers'][0]['image'], self.lock['services'][r['metadata']['name']]['image'])

    def test_gateway_references_the_generated_config(self):
        resources = self.release()['resources']
        gateway = next(r for r in resources if r['kind'] == 'Deployment' and r['metadata']['name'] == 'gateway')
        names = {r['metadata']['name'] for r in resources if r['kind'] == 'ConfigMap'}
        self.assertIn(gateway['spec']['template']['spec']['volumes'][0]['configMap']['name'], names)

    def test_two_node_rollout_keeps_hard_per_service_placement(self):
        for resource in self.release()['resources']:
            if resource['kind'] != 'Deployment': continue
            update = resource['spec']['strategy']['rollingUpdate']
            self.assertEqual(update, {'maxSurge': 0, 'maxUnavailable': 1})
            anti = resource['spec']['template']['spec']['affinity']['podAntiAffinity']['requiredDuringSchedulingIgnoredDuringExecution']
            self.assertEqual(anti[0]['topologyKey'], 'kubernetes.io/hostname')
            self.assertEqual(anti[0]['matchLabelKeys'], ['app.kubernetes.io/name'])

    def test_gateway_and_backend_readiness_have_different_contracts(self):
        spec = importlib.util.spec_from_file_location('k3s_deployer', Path(__file__).with_name('deploy-k3s.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        self.assertTrue(module.health_up('/health/gateway', b'ok\n'))
        self.assertFalse(module.health_up('/health/gateway', b'{"status":"UP"}'))
        self.assertTrue(module.health_up('/health/admission', b'{"status":"UP"}'))
        self.assertFalse(module.health_up('/health/admission', b'ok\n'))

    def test_rollback_selects_verified_predecessor_not_partial_live_snapshot(self):
        spec = importlib.util.spec_from_file_location('k3s_rollback', Path(__file__).with_name('deploy-k3s.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        release = self.release()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); prior = root / 'releases' / self.release_id; prior.mkdir(parents=True)
            (prior / 'release.json').write_text(json.dumps(release))
            (prior / 'result.json').write_text('{"status":"passed"}')
            candidate = root / 'releases' / ('c' * 40 + '-124-1'); candidate.mkdir()
            pointer = {'releaseId': self.release_id, 'sourceCommit': self.commit}
            (candidate / 'before-pointer.json').write_text(json.dumps(pointer))
            (candidate / 'before.json').write_text('[]')
            resources, actual = module.rollback_target(root, candidate.name)
            self.assertEqual(resources, release['resources']); self.assertEqual(actual, pointer)
            (prior / 'result.json').write_text('{"status":"failed"}')
            with self.assertRaises(RuntimeError): module.rollback_target(root, candidate.name)
            (candidate / 'before-pointer.json').write_text('null')
            with self.assertRaises(RuntimeError): module.rollback_target(root, candidate.name)

    def test_reject_wrong_commit_or_release_id(self):
        bad = copy.deepcopy(self.lock); bad['x-release-commit'] = 'c' * 40
        with self.assertRaises(ValueError): self.release(bad)
        release = self.release(); release['releaseId'] = 'c' * 40 + '-123-1'
        with self.assertRaises(ValueError): validate_release(release)

    def test_reject_floating_or_foreign_images(self):
        for ref in (REGISTRY + 'identity:latest', 'ghcr.io/other/identity@sha256:' + 'b' * 64):
            bad = copy.deepcopy(self.lock); bad['services']['identity']['image'] = ref
            with self.assertRaises(ValueError): self.release(bad)

    def test_reject_infrastructure_or_wrong_namespace(self):
        for resource in ({'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'identity-secrets', 'namespace': 'sems-test'}},
                         {'apiVersion': 'v1', 'kind': 'Service', 'metadata': {'name': 'postgres', 'namespace': 'sems-test'}}):
            release = self.release(); release['resources'].append(resource)
            with self.assertRaises(ValueError): validate_release(release)
        release = self.release(); release['resources'][0]['metadata']['namespace'] = 'default'
        with self.assertRaises(ValueError): validate_release(release)

    def test_rollback_requires_compatibility_confirmation(self):
        release = {'operation': 'rollback', 'releaseId': self.release_id}
        with self.assertRaises(ValueError): validate_release(release)
        release['databaseCompatibilityConfirmed'] = True
        self.assertEqual(validate_release(release)['operation'], 'rollback')


if __name__ == '__main__':
    unittest.main()
