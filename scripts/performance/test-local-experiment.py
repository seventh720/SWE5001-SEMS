#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import datetime as dt

spec = importlib.util.spec_from_file_location('experiment', Path(__file__).with_name('local-experiment.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RecoveryTest(unittest.TestCase):
    def report(self, failed_seconds=(), slow_operation=False, seconds=65):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'raw.json'
            with path.open('w') as out:
                for sec in range(seconds):
                    for operation in ('book', 'receipt'):
                        for metric, value in [('unexpected_error_rate', int(sec in failed_seconds)),
                                              ('operation_duration', 4000 if slow_operation and operation == 'book' else 10)]:
                            out.write(json.dumps({'type': 'Point', 'metric': metric, 'data': {
                                'time': dt.datetime.fromtimestamp(1000 + sec + .5, dt.timezone.utc).isoformat(),
                                'value': value, 'tags': {'operation': operation}}}) + '\n')
            return module.recovery(path, 1000)

    def test_no_errors_can_recover_without_waiting_for_replica_restart(self):
        self.assertEqual(self.report()['recoverySeconds'], 0)

    def test_outage_prevents_stable_window_until_last_error(self):
        report = self.report(failed_seconds=range(5))
        self.assertEqual(report['recoverySeconds'], 5)
        self.assertEqual(report['failedRequestsAfterStop'], 10)

    def test_fast_receipts_do_not_hide_slow_booking(self):
        self.assertIsNone(self.report(slow_operation=True)['recoverySeconds'])

    def test_insufficient_observation_is_not_recovery(self):
        self.assertIsNone(self.report(seconds=15)['recoverySeconds'])


if __name__ == '__main__':
    unittest.main()
