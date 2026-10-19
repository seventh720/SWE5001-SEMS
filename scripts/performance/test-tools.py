#!/usr/bin/env python3
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('comparison', Path(__file__).with_name('compare.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report(count, passed=True):
    return {'metadata': {'dataset': 'same', 'mode': 'booking', 'vus': 25, 'warmup': 60,
        'duration': 600, 'base': 'http://test', 'commit': 'abc', 'replicas': 'admission1'},
        'metrics': {
            'successful_requests{scenario:measurement,operation:book}': {'values': {'count': count // 2}},
            'successful_requests{scenario:measurement}': {'values': {'count': count}, 'thresholds': {'count>0': {'ok': True}}},
            'unexpected_error_rate{scenario:measurement}': {'values': {'rate': 0 if passed else .1}, 'thresholds': {'rate<0.01': {'ok': passed}}}}}


class ComparisonTest(unittest.TestCase):
    def test_total_success_uses_measurement_duration_not_warmup_or_operation_subset(self):
        result = module.compare(report(600), report(1200))
        self.assertEqual(result['baseline']['successfulRps'], 1)
        self.assertEqual(result['successfulThroughputRatio'], 2)
        self.assertTrue(result['eligibleForPerformanceClaim'])

    def test_failed_threshold_cannot_be_reported_as_successful_performance(self):
        self.assertFalse(module.compare(report(600), report(1200, False))['eligibleForPerformanceClaim'])

    def test_mismatched_workload_rejected(self):
        other = copy.deepcopy(report(600))
        other['metadata']['vus'] = 100
        with self.assertRaises(ValueError):
            module.compare(report(600), other)


if __name__ == '__main__':
    unittest.main()
