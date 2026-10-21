#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('capacity', Path(__file__).with_name('cloud-capacity.py'))
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)


class CapacityTest(unittest.TestCase):
    def test_ladder_respects_ceiling_and_measures_500_and_1000_for_three_minutes(self):
        full = capacity.plan(1000)
        self.assertEqual(full[:2], [('read', 1, '5s'), ('mixed', 1, '5s')])
        for mode in ('read', 'mixed'):
            self.assertIn((mode, 500, '180s'), full)
            self.assertIn((mode, 1000, '180s'), full)
        self.assertEqual(full[-1], ('contention', 1000, '60s'))
        smaller = capacity.plan(250)
        self.assertTrue(all(vus <= 250 for _, vus, _ in smaller))
        self.assertNotIn(('read', 500, '180s'), smaller)

    def test_selected_workload_does_not_run_other_workloads_or_contention(self):
        self.assertEqual(capacity.plan(50, ['mixed'], False),
                         [('mixed', 1, '5s'), ('mixed', 50, '30s')])

    def test_export_failed_boolean_is_not_confused_with_pass_boolean(self):
        metrics = {
            'http_reqs': {'count': 100}, 'unexpected_failure': {'value': 0, 'thresholds': {'rate<0.01': False}},
            'http_req_duration': {'p(95)': 100},
            'http_req_duration{phase:hold}': {'p(95)': 3200, 'thresholds': {'p(95)<3000': True}},
            'http_reqs{name:events,phase:hold}': {'count': 50},
            'bookings_created': {'count': 10}, 'sold_out': {'count': 90},
        }
        result = capacity.summarize(metrics)
        self.assertEqual(result['p95Ms'], 3200)
        self.assertEqual(result['failedThresholds'], ['http_req_duration{phase:hold}'])
        self.assertEqual(result['bookings_created'], 10)
        self.assertEqual(result['sold_out'], 90)
        metrics['http_req_duration{phase:hold}']['thresholds']['p(95)<3000'] = False
        self.assertFalse(capacity.summarize(metrics)['failedThresholds'])
        metrics['http_reqs{name:events,phase:hold}']['count'] = 0
        metrics['http_req_duration{phase:hold}']['p(95)'] = 0
        self.assertIsNone(capacity.summarize(metrics)['p95Ms'])


if __name__ == '__main__':
    unittest.main()
