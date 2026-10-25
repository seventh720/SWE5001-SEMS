"""Keep fixture and fault-injection suites away from the migrated live database."""
import json
import subprocess


def require_disposable_namespace(kubectl, namespace='sems-test'):
    resource = json.loads(subprocess.check_output(
        [*kubectl, 'get', 'namespace', namespace, '-o', 'json'], text=True, timeout=30))
    environment = resource['metadata'].get('annotations', {}).get(
        'sems.seventh720.com/environment')
    if environment == 'production' or namespace == 'sems-prod':
        raise RuntimeError(
            'Refusing fixture/fault tests in production namespace ' + namespace
            + '; it contains migrated original data. Use an isolated test environment.')
