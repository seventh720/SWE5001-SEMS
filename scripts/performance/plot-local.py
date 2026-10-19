#!/usr/bin/env python3
"""Render local experiment figures (requires matplotlib) from verified summary JSON."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('summary', type=Path)
    args = parser.parse_args()
    report = json.loads(args.summary.read_text())
    folder = args.summary.parent
    if not all(g['formalComparisonEligible'] and g['allThresholdsAndAuditsPassed'] for g in report['groups']):
        raise ValueError('Resolve invalid/incomplete comparisons before rendering final figures')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'axes.titleweight': 'bold', 'savefig.dpi': 180})
    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8), layout='constrained')
    csv_rows = []
    for col, mode in enumerate(('catalog', 'booking')):
        operation = 'list' if mode == 'catalog' else 'book'
        for replicas, color in [(1, '#7257bc'), (2, '#007f7b')]:
            values, errors, latency, latency_errors = [], [], [], []
            for vus in (25, 50, 100):
                runs = [r for r in report['runs'] if not r['fault'] and r['mode'] == mode and r['vus'] == vus and r['replicas'] == replicas]
                throughput = [r['successfulRps'] if mode == 'catalog' else r['operations']['book']['successfulRps'] for r in runs]
                p95 = [r['operations'][operation]['p95Ms'] for r in runs]
                median = statistics.median(throughput)
                median_p95 = statistics.median(p95)
                values.append(median)
                errors.append([median - min(throughput), max(throughput) - median])
                latency.append(median_p95)
                latency_errors.append([median_p95 - min(p95), max(p95) - median_p95])
                for r in runs:
                    for op, metrics in r['operations'].items():
                        csv_rows.append({'mode': mode, 'replicas': replicas, 'vus': vus, 'repeat': r['repeat'], 'operation': op,
                                         'successfulRps': metrics['successfulRps'], 'p95Ms': metrics['p95Ms']})
            label = f'{replicas} replica' + ('s' if replicas == 2 else '')
            axes[0, col].errorbar([25, 50, 100], values, yerr=list(zip(*errors)), color=color, marker='o', capsize=5, label=label)
            axes[1, col].errorbar([25, 50, 100], latency, yerr=list(zip(*latency_errors)), color=color, marker='o', capsize=5, label=label)
        axes[0, col].set_title('Catalog: successful HTTP requests' if mode == 'catalog' else 'Admission: successful bookings (POST only)')
        axes[0, col].set_ylabel('Successful requests / second' if mode == 'catalog' else 'Bookings / second')
        axes[1, col].set_title('Event list p95' if mode == 'catalog' else 'Booking POST p95')
        axes[1, col].set_ylabel('Latency (ms)')
        for row in range(2):
            axes[row, col].set_xticks([25, 50, 100])
            axes[row, col].set_xlabel('Concurrent virtual users (VU)')
            axes[row, col].set_ylim(bottom=0)
            axes[row, col].grid(axis='y', alpha=.2)
            axes[row, col].legend(frameon=False)
    figure.suptitle('Local replica scaling experiment — fixed 0.5 CPU / 768 MiB per tested replica', fontsize=14)
    figure.supxlabel('Median of 3 runs; error bars = min–max. 60s warm-up + 600s measurement.\nLocal Docker Desktop; generator shares host. Not a cloud capacity or host-HA claim.', fontsize=9)
    figure.savefig(folder / 'scaling.png')
    figure.savefig(folder / 'scaling.pdf')
    plt.close(figure)
    with (folder / 'operation-measurements.csv').open('w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.5), layout='constrained')
    for ax, field, label in [(axes[0], 'medianServiceCpuCores', 'Mean CPU use (cores)'),
                             (axes[1], 'medianServiceMemoryMiB', 'Mean memory use (MiB)')]:
        for mode, marker in [('catalog', 'o'), ('booking', 's')]:
            for replicas, color, style in [('one', '#7257bc', '--'), ('two', '#007f7b', '-')]:
                groups = [g for g in report['groups'] if g['mode'] == mode]
                ax.plot([g['vus'] for g in groups], [g[replicas][field] for g in groups], marker=marker,
                        linestyle=style, color=color, label=f'{mode}: {1 if replicas == "one" else 2} replica(s)')
        ax.set_xlabel('Concurrent virtual users (VU)')
        ax.set_ylabel(label)
        ax.set_xticks([25, 50, 100])
        ax.set_ylim(bottom=0)
        ax.grid(axis='y', alpha=.2)
        ax.legend(fontsize=8, frameon=False)
    figure.suptitle('Measured resource cost of the scaled service only', fontsize=14)
    figure.supxlabel('Median of 3 run means; all replicas summed. Sampled Docker stats, excluding generator.\nLimits increase from 0.5 CPU / 768 MiB to 1 CPU / 1536 MiB. No cloud billing measurement.', fontsize=9)
    figure.savefig(folder / 'resources.png')
    figure.savefig(folder / 'resources.pdf')


if __name__ == '__main__':
    main()
