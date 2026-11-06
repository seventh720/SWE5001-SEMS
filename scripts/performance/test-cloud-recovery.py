#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).with_name('cloud-recovery.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class BusinessRecoveryTest(unittest.TestCase):
    def test_missing_background_booking_ack_cannot_claim_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            log, raw = Path(directory) / 'load.log', Path(directory) / 'raw.json'
            ack = {'kind': 'booking-ack', 'scenario': 'measurement',
                   'confirmed': True, 'validSingleTicket': True,
                   'bookingId': '00000000-0000-0000-0000-000000000001',
                   'requestKey': '00000000-0000-0000-0000-000000000002'}
            log.write_text('k6 status text\n' + json.dumps({'source': 'console', 'msg': json.dumps(ack)}) + '\n')
            point = {'type': 'Point', 'metric': 'successful_requests', 'data': {
                'value': 1, 'tags': {'operation': 'book', 'scenario': 'measurement'}}}
            raw.write_text(json.dumps(point) + '\n')
            self.assertTrue(m.load_booking_acks(log, raw)[1]['passed'])
            raw.write_text((json.dumps(point) + '\n') * 2)
            self.assertFalse(m.load_booking_acks(log, raw)[1]['passed'])

    def test_running_pod_database_url_is_checked_in_addition_to_configmap(self):
        driver = object.__new__(m.Recovery)
        driver.state = {'testDatabase': 'sems_validation_abcdef123456'}
        driver.pods = lambda: [{'metadata': {'name': service, 'labels': {'app.kubernetes.io/name': service}}}
                               for service in m.m.BACKENDS]
        urls = m.m.database_urls(driver.state['testDatabase'])
        def actual(*args):
            service = args[1]
            schema = 'catalog' if service == 'event-catalog' else service
            return urls[schema.upper() + '_DB_URL'].encode()
        driver.k = actual
        driver.runtime_guard()
        driver.k = lambda *args: b'jdbc:postgresql://postgres:5432/sems?currentSchema=admission' if args[1] == 'admission' else actual(*args)
        with self.assertRaises(ValueError):
            driver.runtime_guard()

    def test_seeded_snapshot_cannot_select_a_different_host_or_small_dataset(self):
        state = {'baselineSha256': 'matched'}
        data = {'baseUrl': m.m.BASE, 'users': [None] * 1000, 'events': [None] * 100}
        m.validate_seed_source(state, data, 'matched')
        for changed, digest in (({**data, 'baseUrl': 'http://localhost:18087'}, 'matched'),
                                ({**data, 'users': []}, 'matched'), (data, 'different')):
            with self.subTest(data=changed['baseUrl'], digest=digest), self.assertRaises(ValueError):
                m.validate_seed_source(state, changed, digest)

    def test_continuous_success_reports_zero_business_interruption(self):
        points = [{'time': t / 10, 'operation': 'book', 'durationMs': 100, 'error': False} for t in range(900)]
        self.assertEqual(m.healthy_window(points, 0, 90, ['book']), 0)

    def test_failure_interval_and_slow_tail_delay_healthy_window(self):
        points = [{'time': t, 'operation': 'book', 'durationMs': 4000 if t < 10 else 100, 'error': t < 10}
                  for t in range(90)]
        self.assertEqual(m.healthy_window(points, 0, 90, ['book']), 10)

    def test_missing_operation_or_short_observation_cannot_pass(self):
        points = [{'time': t, 'operation': 'book', 'durationMs': 100, 'error': False} for t in range(90)]
        self.assertIsNone(m.healthy_window(points, 0, 90, ['book', 'receipt']))
        self.assertIsNone(m.healthy_window(points, 0, 29, ['book']))

    def test_separate_error_and_latency_series_do_not_assume_request_order(self):
        durations = [{'time': t, 'operation': 'book', 'durationMs': 100, 'error': None} for t in range(90)]
        errors = [{'time': t, 'operation': 'book', 'durationMs': None, 'error': t < 10} for t in range(90)]
        self.assertEqual(m.healthy_window(durations + errors, 0, 90, ['book']), 10)
        self.assertIsNone(m.healthy_window(durations, 0, 90, ['book']))


if __name__ == '__main__':
    unittest.main()
