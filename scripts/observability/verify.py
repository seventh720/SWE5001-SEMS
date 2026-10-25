#!/usr/bin/env python3
"""Verify live telemetry using read-only business requests and a synthetic alert gauge."""
import argparse
import base64
import contextlib
import datetime
import json
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]


def http(url, headers=None, data=None):
    if data is not None:
        data = json.dumps(data).encode()
        headers = {'Content-Type': 'application/json', **(headers or {})}
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}, data=data),
                                context=ctx, timeout=20) as response:
        body = response.read()
        return json.loads(body) if body else {}


@contextlib.contextmanager
def forward(k, service, remote):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(k + ['-n', 'observability', 'port-forward', '--address=127.0.0.1',
                                       'svc/' + service, str(port) + ':' + str(remote)], stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(service + ': private port-forward failed')
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError(service + ': port-forward timeout')
            yield 'http://127.0.0.1:' + str(port)
        finally:
            process.terminate()
            process.wait(timeout=10)


def wait_for(check, description, timeout=120):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        result = check()
        if result:
            return result
        time.sleep(5)
    raise RuntimeError('Timed out: ' + description)


def resource_spans(document):
    if isinstance(document, list):
        for item in document:
            yield from resource_spans(item)
    elif isinstance(document, dict):
        if 'resource' in document and ('scopeSpans' in document or 'instrumentationLibrarySpans' in document):
            yield document
        else:
            for value in document.values():
                if isinstance(value, (dict, list)):
                    yield from resource_spans(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--context', default='sems-k3s')
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--alert-smoke', action='store_true', help='Send clearly labelled synthetic firing/recovery notifications')
    args = parser.parse_args()
    k = ['kubectl', '--kubeconfig', args.kubeconfig, '--context', args.context,
         '--cache-dir', str(ROOT / '.secrets/observability/cache')]
    report = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'running', 'checks': []}

    def passed(name, **details):
        report['checks'].append({'name': name, 'status': 'passed', **details})
        print('PASS ' + name, flush=True)

    def get(kind, name=None, namespace='observability'):
        return json.loads(subprocess.check_output(k + ['-n', namespace, 'get', kind] + ([name] if name else []) + ['-o', 'json'], text=True))

    try:
        ns = get('namespace', 'sems-test', 'sems-test')
        assert ns['metadata']['annotations']['sems.seventh720.com/environment'] == 'production'
        backend_names = {'identity', 'event-catalog', 'admission'}
        deployments = get('deployment', namespace='sems-test')['items']
        images = {}
        for d in deployments:
            assert d['status'].get('availableReplicas') == d['spec']['replicas'] == 2
            name = d['metadata']['name']
            images[name] = d['spec']['template']['spec']['containers'][0]['image']
            if name in backend_names:
                assert d['spec']['template']['spec']['initContainers'][0]['name'] == 'otel-java-agent'
        passed('five applications retain two ready replicas', images=images)
        with forward(k, 'grafana', 3000) as grafana, forward(k, 'otel-collector', 4318) as otlp:
            secret = get('secret', 'grafana-admin')['data']
            username, password = [base64.b64decode(secret[key]).decode() for key in ['username', 'password']]
            auth = {'Authorization': 'Basic ' + base64.b64encode((username + ':' + password).encode()).decode()}

            def api(path):
                return http(grafana + path, headers=auth)

            def proxy(uid, path):
                return api('/api/datasources/proxy/uid/' + uid + path)

            def query(expression):
                return proxy('prometheus', '/api/v1/query?' + urllib.parse.urlencode({'query': expression}))['data']['result']

            assert api('/api/health')['database'] == 'ok'
            assert api('/api/dashboards/uid/sems-operations')['dashboard']['panels']
            for uid in ['prometheus', 'loki', 'tempo']:
                assert api('/api/datasources/uid/' + uid + '/health')['status'] == 'OK'
            # Alertmanager is a frontend data source; its backend /health is unsupported in Grafana 13.
            assert proxy('alertmanager', '/api/v2/status')['versionInfo']['version']
            passed('Grafana dashboard and all four data sources')
            targets = proxy('prometheus', '/api/v1/targets')['data']['activeTargets']
            assert len(targets) >= 17 and all(t['health'] == 'up' for t in targets), [(t['labels'].get('job'),t['lastError']) for t in targets if t['health'] != 'up']
            probes = query('probe_success{job="public-https"}')
            assert len(probes) == 4 and all(float(v['value'][1]) == 1 for v in probes)
            assert query('pg_up')[0]['value'][1] == '1'
            assert query('pg_exporter_last_scrape_error')[0]['value'][1] == '0'
            passed('node, Pod, control-plane, PostgreSQL and HTTPS scrapes', targetCount=len(targets))
            observations = {}
            for metric in ['jvm_memory_used_bytes', 'http_server_request_duration_seconds_count']:
                def current_pod_metrics():
                    rows = query('count by(service_name,k8s_pod_name) (' + metric + ')')
                    return rows if len({r['metric'].get('k8s_pod_name') for r in rows}) == 6 else None
                samples = wait_for(current_pod_metrics, 'metrics from six current Pods')
                assert {s['metric']['service_name'] for s in samples} == backend_names
                pods = {s['metric']['k8s_pod_name'] for s in samples}
                assert len(pods) == 6
                observations[metric] = len(samples)
            passed('JVM and HTTP metrics from all six backend Pods', seriesByPod=observations)
            site = 'https://swe5001.seventh720.com'
            listing = http(site + '/api/v1/events')
            assert listing['items'], 'No public event available for read-only trace verification'
            event = listing['items'][0]['id']
            trace_id = secrets.token_hex(16)
            parent_id = secrets.token_hex(8)
            http(site + '/api/v1/events/' + event + '/ticket-types', headers={'traceparent': '00-' + trace_id + '-' + parent_id + '-01'})

            def trace_ready():
                try:
                    result = proxy('tempo', '/api/traces/' + trace_id)
                    batches = list(resource_spans(result))
                    names = {a['value'].get('stringValue') for b in batches for a in b['resource'].get('attributes', []) if a['key'] == 'service.name'}
                    return batches if backend_names <= names else None
                except urllib.error.HTTPError as error:
                    if error.code == 404:
                        return None
                    raise

            batches = wait_for(trace_ready, 'one propagated trace across all three services')
            spans = {}
            for b in batches:
                service = next(a['value']['stringValue'] for a in b['resource']['attributes'] if a['key'] == 'service.name')
                for scope in b.get('scopeSpans', b.get('instrumentationLibrarySpans', [])):
                    for span in scope['spans']:
                        attrs = {a['key']: a['value'] for a in span.get('attributes', [])}
                        assert not {'url.query', 'db.statement', 'db.query.text'} & attrs.keys()
                        assert '?' not in attrs.get('url.full', {}).get('stringValue', '')
                        spans[span['spanId']] = (service, span)
            edges = set()
            for service, span in spans.values():
                parent = spans.get(span.get('parentSpanId'))
                if parent and parent[0] != service:
                    edges.add((parent[0], service))
            assert {('admission', 'event-catalog'), ('event-catalog', 'identity')} <= edges
            passed('real read-only Admission → Catalog → Identity trace', traceId=trace_id, spanCount=len(spans), crossServiceEdges=sorted(edges), queryTextRemoved=True)
            # Loki's default label lookback can omit quiet Java services after startup.
            # Inspect retained logs rather than requiring every service to emit hourly.
            log_window = urllib.parse.urlencode({'start': str(time.time_ns() - 48 * 3600 * 10**9),
                                                'end': str(time.time_ns())})
            logs = wait_for(lambda: proxy('loki', '/loki/api/v1/label/service_name/values?' + log_window)['data'],
                            'centralized logs within configured retention')
            assert backend_names <= set(logs)
            passed('centralized application logs', services=logs)
            # Ensure every dashboard PromQL expression is syntactically executable. Empty low-traffic rates are valid.
            dashboard = api('/api/dashboards/uid/sems-operations')['dashboard']
            panel_results = []
            for panel in dashboard['panels']:
                if panel.get('datasource', {}).get('uid') != 'prometheus':
                    continue
                expr = panel['targets'][0]['expr']
                panel_results.append({'title': panel['title'], 'series': len(query(expr))})
            passed('all dashboard metric queries execute', panels=panel_results)
            if args.alert_smoke:
                def gauge(value):
                    now = str(time.time_ns())
                    return http(otlp + '/v1/metrics', data={'resourceMetrics': [{'resource': {'attributes': [
                        {'key': 'service.name', 'value': {'stringValue': 'observability-smoke'}},
                        {'key': 'deployment.environment.name', 'value': {'stringValue': 'production'}}]},
                        'scopeMetrics': [{'scope': {'name': 'sems-observability-verifier'}, 'metrics': [
                            {'name': 'sems_observability_smoke', 'gauge': {'dataPoints': [{'asInt': str(value), 'timeUnixNano': now}]}}]}]}]})

                def smoke_active():
                    return query('ALERTS{alertname="ObservabilitySmokeTest",alertstate="firing"}')

                telegram = any(r['name'] == 'telegram' for r in proxy('alertmanager', '/api/v2/receivers'))
                def notifications():
                    result = query('sum(alertmanager_notifications_total{integration="telegram"})')
                    return float(result[0]['value'][1]) if result else 0
                baseline = notifications()
                try:
                    gauge(1)
                    wait_for(smoke_active, 'synthetic Prometheus alert firing', timeout=150)
                    wait_for(lambda: [a for a in proxy('alertmanager', '/api/v2/alerts') if a['labels'].get('alertname') == 'ObservabilitySmokeTest'], 'Alertmanager received synthetic alert', timeout=90)
                    # Give group_wait time to deliver before resolving. No business fault is induced.
                    if telegram:
                        wait_for(lambda: notifications() > baseline, 'Telegram firing delivery', timeout=120)
                    passed('synthetic alert reaches Alertmanager')
                finally:
                    gauge(0)
                wait_for(lambda: not smoke_active(), 'synthetic alert recovered', timeout=120)
                if telegram:
                    wait_for(lambda: notifications() >= baseline + 2, 'Telegram recovery delivery', timeout=150)
                    failed = query('sum(alertmanager_notifications_failed_total{integration="telegram"})')
                    assert not failed or float(failed[0]['value'][1]) == 0
                    passed('Telegram firing and recovery delivered', notifications=int(notifications() - baseline))
                passed('synthetic alert recovers after clearing the gauge')
            active = [s['metric'].get('alertname') for s in query('ALERTS{alertstate="firing",alertname!="ObservabilitySmokeTest"}')]
            assert not active, 'Operational alerts require review: ' + str(active)
            passed('no active operational alerts')
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
