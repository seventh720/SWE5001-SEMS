#!/usr/bin/env python3
"""Record time-series snapshots beside a load run. Run on the Compose host."""
import argparse
import datetime
import json
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=720)
    parser.add_argument('--interval', type=int, default=10)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if min(args.seconds, args.interval) < 1:
        parser.error('Durations must be positive')
    deadline = time.monotonic() + args.seconds
    with open(args.output, 'x') as out:
        while time.monotonic() < deadline:
            started = time.monotonic()
            result = subprocess.run(['python3', 'scripts/observe-platform.py', f'{args.interval}s'],
                                    capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                row = json.loads(result.stdout)
            else:
                row = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                       'collectionError': True, 'exitCode': result.returncode}
            out.write(json.dumps(row) + '\n')
            out.flush()
            time.sleep(max(0, min(deadline - time.monotonic(), args.interval - (time.monotonic() - started))))


if __name__ == '__main__':
    main()
