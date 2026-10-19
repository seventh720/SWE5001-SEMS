#!/usr/bin/env python3
"""Summarize completed local runs without copying credential-bearing input files."""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import statistics


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def memory_mib(value):
    number, unit = re.fullmatch(r'([\d.]+)(\w+)', value.split(' / ')[0]).groups()
    return float(number) * {'B': 1 / 1048576, 'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024}[unit]


def summarize_run(source, run):
    folder = source / run['run']
    summary = json.loads((folder / 'summary.json').read_text())
    meta, metrics = summary['metadata'], summary['metrics']
    selected = {key: value for key, value in metrics.items() if 'scenario:measurement' in key}
    thresholds = [t['ok'] for value in selected.values() for t in value.get('thresholds', {}).values()]
    result = dict(run, metadata=meta, thresholdsPassed=bool(thresholds) and all(thresholds),
                  successfulRps=metrics['successful_requests{scenario:measurement}']['values']['count'] / meta['duration'],
                  unexpectedErrorRate=metrics['unexpected_error_rate{scenario:measurement}']['values']['rate'],
                  unexpectedErrors=metrics['unexpected_error_rate{scenario:measurement}']['values']['passes'],
                  businessRejectionRate=metrics['business_rejection_rate{scenario:measurement}']['values']['rate'])
    result['operations'] = {}
    for op in ('list', 'detail') if run['mode'] == 'catalog' else ('book', 'receipt'):
        result['operations'][op] = {
            'p95Ms': metrics[f'operation_duration{{scenario:measurement,operation:{op}}}']['values']['p(95)'],
            'successfulRps': metrics[f'successful_requests{{scenario:measurement,operation:{op}}}']['values']['count'] / meta['duration']}
    statuses, mix, failures = collections.Counter(), collections.Counter(), []
    started, ended = None, None
    response_times = []
    with gzip.open(folder / 'raw.json.gz', 'rt') as stream:
        for line in stream:
            if '"metric":"http_reqs"' not in line or '"type":"Point"' not in line:
                continue
            data = json.loads(line)['data']
            tags = data['tags']
            if tags.get('scenario') != 'measurement':
                continue
            t = timestamp(data['time'])
            response_times.append(t)
            started = t if started is None else min(started, t)
            ended = t if ended is None else max(ended, t)
            statuses[tags.get('status', 'missing')] += data['value']
            mix[tags.get('operation', tags.get('name'))] += data['value']
            if tags.get('status') != '200':
                failures.append({'time': data['time'], 'status': tags.get('status'), 'operation': tags.get('operation'), 'errorCode': tags.get('error_code')})
    response_times.sort()
    max_gap = max((b - a for a, b in zip(response_times, response_times[1:])), default=0)
    result['measurementMaxResponseGapSeconds'] = max_gap
    result['wallClockContinuous'] = ended - started <= meta['duration'] + 30 and max_gap <= 15
    result.update(statusCounts=dict(statuses), operationCounts=dict(mix), failures=failures,
                  measurementFirstResponse=started, measurementLastResponse=ended)
    service = 'event-catalog' if run['mode'] == 'catalog' else 'admission'
    resources, gaps, previous = [], [], None
    collection_failures = 0
    for line in (folder / 'resources.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row.get('collectionError'):
            collection_failures += 1
            continue
        t = timestamp(row['observedAt'])
        if not started <= t <= started + meta['duration']:
            continue
        if previous is not None:
            gaps.append(t - previous)
        previous = t
        tested = [c for c in row['containers'] if c['Name'].startswith('sems-architecture-' + service + '-')]
        database = next(c for c in row['containers'] if c['Name'] == 'sems-architecture-postgres-1')
        resources.append({'serviceCpuCores': sum(float(c['CPUPerc'].rstrip('%')) for c in tested) / 100,
                          'serviceMemoryMiB': sum(memory_mib(c['MemUsage']) for c in tested),
                          'postgresCpuCores': float(database['CPUPerc'].rstrip('%')) / 100,
                          'allServiceCpuCores': sum(float(c['CPUPerc'].rstrip('%')) for c in row['containers']) / 100,
                          'dbConnections': row['database']['connections'], 'dbLockWaiters': row['database']['waiting']})
    result['resources'] = {key: {'mean': statistics.mean(r[key] for r in resources), 'max': max(r[key] for r in resources)} for key in resources[0]} if resources else {}
    result['resourceSamples'] = len(resources)
    result['resourceCollectionFailures'] = collection_failures
    result['resourceMaxGapSeconds'] = max(gaps, default=0)
    upstreams = collections.Counter()
    for line in (folder / 'gateway.jsonl').read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        path = row.get('path', '')
        if (run['mode'] == 'catalog' and path.startswith('/api/v1/events')) or (run['mode'] == 'booking' and path.startswith('/api/v1/bookings')):
            upstreams[row['upstream']] += 1
    result['gatewayUpstreamsWholeRun'] = dict(upstreams)
    result['replicaConfiguration'] = json.loads((folder / 'replicas.json').read_text())
    audit = json.loads((folder / 'inventory.json').read_text())
    result['inventory'] = {'passed': audit['passed'], 'ticketTypes': len(audit['inventory']), 'reserved': sum(x['reserved'] for x in audit['inventory'])}
    if run['fault']:
        result['faultEvents'] = [json.loads(line) for line in (folder / 'fault.jsonl').read_text().splitlines()]
        stop = timestamp(result['faultEvents'][0]['time'])
        result['faultFailureOffsetsSeconds'] = [timestamp(f['time']) - stop for f in failures if timestamp(f['time']) >= stop]
        attempts = [json.loads(line) for line in (folder / 'replay-attempts.jsonl').read_text().splitlines()]
        result['replayProbeStatuses'] = dict(collections.Counter(str(s) for r in attempts for s in r['statuses']))
        result['replayKeysWithFailedAttempt'] = sum(any(s != 200 for s in r['statuses']) for r in attempts)
        result['failedProbeKeysReconciled'] = [r['request']['requestKey'] for r in attempts if any(s != 200 for s in r['statuses'])]
    print('Summarized', run['run'], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--replacement-source', type=Path, help='Merge explicitly repeated runs into an existing analyzed report; retain superseded results')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    status = json.loads((args.source / 'progress.json').read_text())
    runs = json.loads((args.source / 'runs.json').read_text())
    if status['phase'] != 'complete' or len(runs) != 38:
        raise ValueError('Require all 38 completed runs for this formal matrix')
    superseded = []
    replacement_info = None
    if args.replacement_source:
        previous = json.loads((args.output / 'summary.json').read_text())
        replacement_status = json.loads((args.replacement_source / 'progress.json').read_text())
        if replacement_status['phase'] != 'complete':
            raise ValueError('Replacement experiment is not complete')
        replacement_environment = json.loads((args.replacement_source / 'environment.json').read_text())
        for field in ('snapshotSha256', 'dataset', 'commit', 'images', 'limits', 'warmupSeconds', 'measurementSeconds'):
            if previous['environment'][field] != replacement_environment[field]:
                raise ValueError('Replacement environment mismatch: ' + field)
        replacement_runs = json.loads((args.replacement_source / 'runs.json').read_text())
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            replacements = {r['run']: r for r in pool.map(lambda run: summarize_run(args.replacement_source, run), replacement_runs)}
        superseded = previous.get('supersededRuns', []) + [r for r in previous['runs'] if r['run'] in replacements]
        results = [replacements.get(r['run'], r) for r in previous['runs']]
        replacement_info = {'completion': replacement_status, 'environment': replacement_environment,
                            'runIds': sorted(replacements), 'reason': 'Original raw timestamps showed gaps inconsistent with continuous 10-minute measurement. Originals retained.'}
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda run: summarize_run(args.source, run), runs))
    groups = []
    for mode in ('catalog', 'booking'):
        for vus in (25, 50, 100):
            a = [r for r in results if not r['fault'] and r['mode'] == mode and r['vus'] == vus and r['replicas'] == 1]
            b = [r for r in results if not r['fault'] and r['mode'] == mode and r['vus'] == vus and r['replicas'] == 2]
            assert len(a) == len(b) == 3
            for pair in zip(a, b):
                for field in ('dataset', 'mode', 'vus', 'duration', 'warmup', 'base', 'commit'):
                    assert pair[0]['metadata'][field] == pair[1]['metadata'][field], field
            row = {'mode': mode, 'vus': vus}
            for label, items in [('one', a), ('two', b)]:
                row[label] = {'medianRps': statistics.median(r['successfulRps'] for r in items),
                              'minRps': min(r['successfulRps'] for r in items), 'maxRps': max(r['successfulRps'] for r in items),
                              'medianOperationP95Ms': {op: statistics.median(r['operations'][op]['p95Ms'] for r in items) for op in items[0]['operations']},
                              'maxErrorRate': max(r['unexpectedErrorRate'] for r in items),
                              'medianServiceCpuCores': statistics.median(r['resources']['serviceCpuCores']['mean'] for r in items),
                              'medianServiceMemoryMiB': statistics.median(r['resources']['serviceMemoryMiB']['mean'] for r in items)}
            row['ratioOfMedianSuccessfulRps'] = row['two']['medianRps'] / row['one']['medianRps']
            row['pairedRunRatios'] = [y['successfulRps'] / x['successfulRps'] for x, y in zip(a, b)]
            row['continuousPairedRepeats'] = [x['repeat'] for x, y in zip(a, b) if x['wallClockContinuous'] and y['wallClockContinuous']]
            row['formalComparisonEligible'] = len(row['continuousPairedRepeats']) == 3
            row['allThresholdsAndAuditsPassed'] = all(r['thresholdsPassed'] and r['auditPassed'] for r in a + b)
            groups.append(row)
    report = {'environment': json.loads((args.source / 'environment.json').read_text()), 'completion': status,
              'aggregation': 'Median of three per-run measurements; p95 is median of per-run p95, not pooled p95. Booking HTTP throughput includes POST plus receipt GET.',
              'groups': groups, 'runs': results, 'supersededRuns': superseded, 'replacement': replacement_info}
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    with (args.output / 'measurements.csv').open('w', newline='') as out:
        fields = ['mode', 'vus', 'replicas', 'repeat', 'successfulRps', 'unexpectedErrorRate', 'unexpectedErrors', 'businessRejectionRate', 'thresholdsPassed', 'auditPassed']
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: r[key] for key in fields} for r in results if not r['fault'])
    manifest = []
    sources = [args.source] + ([args.replacement_source] if args.replacement_source else [])
    for source in sources:
      for file in sorted(source.rglob('*')):
        if file.is_file():
            digest = hashlib.sha256()
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            manifest.append({'source': source.name, 'path': str(file.relative_to(source)), 'bytes': file.stat().st_size, 'sha256': digest.hexdigest()})
    (args.output / 'raw-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
