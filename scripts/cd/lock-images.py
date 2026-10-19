#!/usr/bin/env python3
"""Write a Compose overlay with digest-only runtime image references."""
import json
from pathlib import Path
import re
import sys

SERVICES = ('identity', 'event-catalog', 'admission', 'web', 'postgres', 'gateway', 'caddy')


def lock(directory, sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Expected a full commit SHA')
    images = {}
    for service in SERVICES:
        ref = (Path(directory) / (service + '.ref')).read_text().strip()
        if not re.fullmatch(r'[a-z0-9./:_-]+@sha256:[0-9a-f]{64}', ref):
            raise ValueError(f'{service}: expected an immutable image digest')
        images[service] = {'image': ref, 'pull_policy': 'always'}
    return {'x-release-commit': sha, 'services': images}


if __name__ == '__main__':
    Path(sys.argv[3]).write_text(json.dumps(lock(sys.argv[1], sys.argv[2]), indent=2) + '\n')
