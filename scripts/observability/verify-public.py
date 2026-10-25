#!/usr/bin/env python3
"""Check Grafana's trusted public TLS, login enforcement and secure browser session."""
import argparse
import base64
import datetime
import http.cookiejar
import json
from pathlib import Path
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kubeconfig', required=True)
    parser.add_argument('--context', default='sems-k3s')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    anonymous = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
    jar = http.cookiejar.CookieJar()
    authenticated = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                                urllib.request.HTTPSHandler(context=ctx))
    base = 'https://grafana.seventh720.com'
    report = {'startedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'url': base, 'status': 'running', 'checks': []}

    def request(opener, url, body=None):
        headers = {'Content-Type': 'application/json'} if body is not None else {}
        req = urllib.request.Request(url, headers=headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        try:
            with opener.open(req, timeout=20) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.headers, error.read()

    def passed(name, **details):
        report['checks'].append({'name': name, 'status': 'passed', **details})
        print('PASS ' + name, flush=True)

    try:
        # Retry only certificate issuance/startup, never weaken certificate verification.
        for _ in range(36):
            try:
                code, _, _ = request(anonymous, base + '/login')
                if code == 200:
                    break
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(5)
        else:
            raise RuntimeError('Trusted HTTPS login page did not become ready')
        passed('trusted HTTPS login page')
        code, headers, _ = request(anonymous, 'http://grafana.seventh720.com/login')
        assert code in (301, 302, 307, 308) and headers['Location'].startswith(base)
        passed('HTTP redirects to HTTPS', response=code)
        for path in ['/api/dashboards/uid/sems-operations',
                     '/api/datasources/proxy/uid/prometheus/api/v1/query?query=up', '/metrics']:
            code, _, _ = request(anonymous, base + path)
            assert code in (401, 403), (path, code)
        code, headers, _ = request(anonymous, base + '/d/sems-operations')
        assert code in (301, 302, 303, 307, 308) and '/login' in headers.get('Location', '')
        passed('anonymous dashboard, datasource and metrics access denied')
        code, _, _ = request(anonymous, base + '/login',
                             {'user': 'sems-invalid-login-probe', 'password': 'deliberately-incorrect'})
        assert code in (401, 403)
        passed('incorrect login rejected')
        secret = json.loads(subprocess.check_output([
            'kubectl', '--kubeconfig', args.kubeconfig, '--context', args.context,
            '-n', 'observability', 'get', 'secret', 'grafana-admin', '-o', 'json'], text=True))['data']
        credentials = {key: base64.b64decode(secret[key]).decode() for key in ['username', 'password']}
        code, _, _ = request(authenticated, base + '/login',
                             {'user': credentials['username'], 'password': credentials['password']})
        assert code == 200, 'Existing Grafana login failed'
        session = next(cookie for cookie in jar if cookie.name == 'grafana_session')
        assert session.secure and 'HttpOnly' in session._rest
        assert session._rest.get('SameSite', '').lower() == 'lax'
        passed('existing account login with Secure, HttpOnly, SameSite session')
        code, _, body = request(authenticated, base + '/api/dashboards/uid/sems-operations')
        assert code == 200 and json.loads(body)['dashboard']['panels']
        query = urllib.parse.urlencode({'query': 'up'})
        code, _, body = request(authenticated, base + '/api/datasources/proxy/uid/prometheus/api/v1/query?' + query)
        data = json.loads(body)
        assert code == 200 and data['status'] == 'success' and len(data['data']['result']) >= 17
        passed('authenticated dashboard and live metric data', targets=len(data['data']['result']))
        # End this probe's browser session; no credential or session value enters its report.
        request(authenticated, base + '/logout')
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
        raise
    finally:
        report['finishedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
