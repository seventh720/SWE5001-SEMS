#!/usr/bin/env python3
"""Check credential boundaries and literal .env handling using synthetic values."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('k8s_secrets', Path(__file__).with_name('secrets.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SecretTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = self.root / 'config.env'
        self.values = {key: 'unused-' + key.lower() for key in (
            'IDENTITY_DB_PASSWORD', 'CATALOG_DB_PASSWORD', 'ADMISSION_DB_PASSWORD',
            'ORGANIZATION_ACCESS_TOKEN', 'CATALOG_TO_ADMISSION_TOKEN',
            'ADMISSION_TO_CATALOG_TOKEN', 'POSTGRES_PASSWORD',
        )}
        (self.root / 'jwt-public.pem').write_text('fixture-public-key')
        (self.root / 'jwt-private.pem').write_text('fixture-private-key')
        self.write_env()

    def write_env(self):
        self.env.write_text(''.join(f'{key}={value}\n' for key, value in self.values.items()))

    def render(self, include_postgres=False):
        result = module.render(self.env, self.root, 'sems-local', include_postgres)
        return {item['metadata']['name']: {
            key: base64.b64decode(value).decode() for key, value in item['data'].items()
        } for item in result['items']}

    def test_service_credentials_and_signing_key_are_separate(self):
        secrets = self.render()
        self.assertNotIn('postgres-secrets', secrets)
        for name, prefix in [('identity', 'IDENTITY'), ('event-catalog', 'CATALOG'), ('admission', 'ADMISSION')]:
            actual = secrets[name + '-secrets']
            self.assertEqual(actual['DB_PASSWORD'], self.values[prefix + '_DB_PASSWORD'])
            self.assertNotIn(self.values['POSTGRES_PASSWORD'], actual.values())
            self.assertNotIn('fixture-private-key', actual.values())
            for other in ('IDENTITY', 'CATALOG', 'ADMISSION'):
                if other != prefix:
                    self.assertNotIn(self.values[other + '_DB_PASSWORD'], actual.values())
        self.assertEqual(secrets['jwt-public'], {'jwt-public.pem': 'fixture-public-key'})
        self.assertEqual(secrets['jwt-private'], {'jwt-private.pem': 'fixture-private-key'})
        self.assertEqual(set(self.render(True)['postgres-secrets']), {
            'POSTGRES_PASSWORD', 'IDENTITY_DB_PASSWORD', 'CATALOG_DB_PASSWORD', 'ADMISSION_DB_PASSWORD',
        })

    def test_environment_is_literal_and_not_executed(self):
        marker = self.root / 'must-not-exist'
        literal = f'$(touch {marker})'
        self.values['IDENTITY_DB_PASSWORD'] = literal
        self.write_env()
        self.assertEqual(self.render()['identity-secrets']['DB_PASSWORD'], literal)
        self.assertFalse(marker.exists())

    def test_missing_credentials_and_partial_bootstrap_are_rejected(self):
        self.values['CATALOG_DB_PASSWORD'] = ''
        self.write_env()
        with self.assertRaisesRegex(ValueError, 'CATALOG_DB_PASSWORD'):
            self.render()
        self.values['CATALOG_DB_PASSWORD'] = 'unused-catalog'
        self.values['SEMS_BOOTSTRAP_ADMIN_EMAIL'] = 'fixture@example.invalid'
        self.write_env()
        with self.assertRaisesRegex(ValueError, 'must both be set'):
            self.render()

    def test_duplicate_assignments_and_invalid_namespaces_are_rejected(self):
        self.env.write_text(self.env.read_text() + 'IDENTITY_DB_PASSWORD=duplicate\n')
        with self.assertRaisesRegex(ValueError, 'Duplicate environment key'):
            self.render()
        with self.assertRaisesRegex(ValueError, 'namespace name'):
            module.render(self.env, self.root, '../other-namespace')


if __name__ == '__main__':
    unittest.main()
