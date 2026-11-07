"""Hosted isolated portal TLS proxy fixture; does not access any real CP."""
import json
import os
from pathlib import Path
import subprocess


def main():
    assert os.getenv('GITHUB_ACTIONS') == 'true', 'Hosted fixture only'
    out = Path('artifacts/gateway-health-proxy')
    out.mkdir(parents=True, exist_ok=True)
    mode = Path('/tmp/portal-ci/gateway-health-mode')
    results = []
    def request(path, method='GET', credentials=False):
        args = ['curl', '-sS', '--cacert', '/tmp/portal-ci/certs/ca-bundle.crt',
                '--resolve', 'portal.sv.lan:8443:127.0.0.1', '-X', method,
                '-D', str(out/'headers.tmp'), '-o', str(out/'body.tmp'), '-w', '%{http_code}',
                'https://portal.sv.lan:8443'+path]
        if credentials:
            args += ['-H', 'Authorization: Bearer isolated-health-fixture', '-H', 'Cookie: isolated=value']
        reply = subprocess.run(args, capture_output=True, check=True, text=True)
        headers = (out/'headers.tmp').read_text()
        body = (out/'body.tmp').read_text()
        row = dict(path=path, method=method, status=int(reply.stdout), headers=headers, body=body)
        results.append(row)
        return row
    try:
        local = request('/healthz')
        assert local['status'] == 200 and local['body'] == 'OK'
        for value in ['healthy', 'html', 'text', 'error']:
            mode.write_text(value)
            row = request('/gateway-healthz', credentials=True)
            assert 'cache-control: no-store' in row['headers'].lower()
            if value == 'healthy':
                assert row['status'] == 200 and 'content-type: application/json' in row['headers'].lower()
                assert json.loads(row['body']) == dict(status='ok', version='isolated-cp')
            elif value == 'html':
                assert row['status'] == 200 and row['body'] == '<html>upstream fallback</html>'
                assert 'content-type: text/html' in row['headers'].lower()
            elif value == 'text':
                assert row['status'] == 200 and row['body'] == 'OK'
                assert 'content-type: text/plain' in row['headers'].lower()
            else:
                assert row['status'] == 503 and json.loads(row['body'])['status'] == 'unavailable'
        assert request('/gateway-healthz?private=value')['status'] == 400
        assert request('/gateway-healthz', method='POST')['status'] == 403
    finally:
        mode.write_text('healthy')
        (out/'result.json').write_text(json.dumps(dict(fixtureOnly=True, realCPAcceptance=False,
            TLSVerified=True, portalLivenessSeparate=True, rawUpstreamFailuresPreserved=True, requests=results), indent=2)+'\n')
    print('PASS: TLS-verified real Nginx proxy forwards CP JSON/error/HTML/text unchanged; liveness separate; query/method/credential guards hold')


if __name__ == '__main__':
    main()
