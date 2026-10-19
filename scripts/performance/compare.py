#!/usr/bin/env python3
"""Compare matched k6 measurement results; does not infer HA from throughput."""
import argparse
import json


def measurement(report):
    metrics = report['metrics']
    selected = {k: v for k, v in metrics.items() if 'scenario:measurement' in k}
    success = metrics['successful_requests{scenario:measurement}']['values']['count']
    checks = [threshold['ok'] for metric in selected.values() for threshold in metric.get('thresholds', {}).values()]
    return {'successfulRps': success / report['metadata']['duration'],
            'thresholdsPassed': bool(checks) and all(checks),
            'metrics': {k: v['values'] for k, v in selected.items()}}


def compare(a, b):
    for field in ('dataset', 'mode', 'vus', 'warmup', 'duration', 'base', 'commit'):
        if a['metadata'][field] != b['metadata'][field]:
            raise ValueError('Unmatched experiment parameter: ' + field)
    if a['metadata']['commit'] == 'unrecorded' or any(r['metadata']['replicas'] == 'unrecorded' for r in (a, b)):
        raise ValueError('Record commit and replica configuration before comparing')
    first, second = measurement(a), measurement(b)
    return {'baseline': first, 'scaled': second,
            'successfulThroughputRatio': second['successfulRps'] / first['successfulRps'] if first['successfulRps'] else None,
            'eligibleForPerformanceClaim': first['thresholdsPassed'] and second['thresholdsPassed'],
            'note': 'Also compare resource budgets, raw time series and DB audit. Repeat matched runs; this is not HA evidence.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline')
    parser.add_argument('scaled')
    args = parser.parse_args()
    print(json.dumps(compare(json.load(open(args.baseline)), json.load(open(args.scaled))), indent=2))
