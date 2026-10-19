#!/usr/bin/env python3
"""Release validation: floating references or wrong commit IDs must not deploy."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('image_lock', Path(__file__).with_name('lock-images.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseLockTest(unittest.TestCase):
    def test_digest_manifest_and_reject_floating_image(self):
        with tempfile.TemporaryDirectory() as directory:
            for service in module.SERVICES:
                (Path(directory) / (service + '.ref')).write_text('ghcr.io/test/' + service + '@sha256:' + 'a' * 64)
            lock = module.lock(directory, 'b' * 40)
            self.assertEqual(set(lock['services']), set(module.SERVICES))
            self.assertEqual(lock['x-release-commit'], 'b' * 40)
            (Path(directory) / 'admission.ref').write_text('ghcr.io/test/admission:latest')
            with self.assertRaises(ValueError):
                module.lock(directory, 'b' * 40)
            with self.assertRaises(ValueError):
                module.lock(directory, 'main')


if __name__ == '__main__':
    unittest.main()
