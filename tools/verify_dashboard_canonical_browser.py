"""Hosted sandboxed browser + main Vite proxy, exact public wire replay only."""
from datetime import datetime, timedelta
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import threading
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'apps/web'
INPUT = ROOT / 'docs/vault/30_Development/Evidence/fleet5-dashboard-canonical-resource-health-r1-20261108-codex/root-inputs/actual-canonical-API-inputs'
OUT = ROOT / 'artifacts/dashboard-canonical-browser'


def main():
    assert os.getenv('GITHUB_ACTIONS') == 'true' and os.name == 'posix', 'Hosted Linux only'
    OUT.mkdir(parents=True, exist_ok=True)
    nodes = json.loads((INPUT / 'nodes.json').read_text())
    ids = [node['nodeId'] for node in nodes['items']]
    usage = {node: json.loads((INPUT / f'resource-usage-{node}.json').read_text()) for node in ids}
    mode = dict(health='healthy', resources='healthy')
    requests, errors, failures, http_errors = [], [], [], []

    class Fixture(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(dict(path=self.path, health=mode['health'], resources=mode['resources']))
            status, mime = 200, 'application/json'
            if self.path == '/healthz':
                assert not self.headers.get('Authorization') and not self.headers.get('Cookie'), 'Health credentials leaked'
                value = dict(status='ok', version='isolated-replay')
                if mode['health'] == 'html':
                    mime, value = 'text/html', '<html>fallback</html>'
                elif mode['health'] == 'text':
                    mime, value = 'text/plain', 'OK'
                elif mode['health'] == 'error':
                    status, value = 503, dict(status='unavailable')
            elif self.path.endswith('/nodes'):
                value = nodes
            elif self.path.endswith('/resource-usage'):
                node = self.path.split('/')[-2]
                value = json.loads(json.dumps(usage[node]))
                if mode['resources'] == 'partial' and node == ids[0]:
                    for row in value['resources']:
                        if row['kind'] == 'memory':
                            row.update(measured=False, reserved=None, spare=None, observedAt=None)
                if mode['resources'] == 'error' and node == ids[0]:
                    status, value = 503, dict(detail='isolated deliberate resource failure')
            else:
                status, value = 404, dict(detail='unserved isolated path')
            body = (json.dumps(value) if mime == 'application/json' else value).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    argv = [shutil.which('node'), 'node_modules/vite/bin/vite.js', '--config', 'vite.config.ts',
            '--host', '127.0.0.1', '--port', str(port), '--strictPort']
    frozen = datetime.fromisoformat(usage[ids[0]]['stateAsOf']) + timedelta(seconds=2)
    report = dict(fixtureOnly=True, realUserOrHardwareAcceptance=False, sandbox=True,
                  sourceSHA=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
                  command=argv, recordedReplayClock=frozen.isoformat(), wireTimestampsModified=False,
                  inputs={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in [INPUT / 'nodes.json', *[INPUT / f'resource-usage-{node}.json' for node in ids]]})
    child = None
    try:
        with (OUT / 'vite.log').open('wb') as log:
            child = subprocess.Popen(argv, cwd=WEB, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, env={**os.environ, 'VITE_API_PROXY_TARGET': f'http://127.0.0.1:{server.server_port}'})
            deadline = time.monotonic() + 30
            while True:
                assert child.poll() is None
                try:
                    with urlopen(origin + '/', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                assert time.monotonic() < deadline
                time.sleep(.1)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel='chrome', headless=True, chromium_sandbox=True)
                try:
                    page = browser.new_page(viewport=dict(width=1440, height=1200))
                    page.clock.set_fixed_time(frozen)  # Date only; real polling/timers/frames continue.
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('requestfailed', lambda req: failures.append(dict(url=req.url, failure=req.failure)))
                    page.on('response', lambda res: http_errors.append(dict(url=res.url, status=res.status)) if res.status >= 400 else None)
                    page.goto(origin + '/tests/browser/dashboard.html')
                    expect(page.get_by_test_id('shared-total-cpu')).to_contain_text('제공 1500m')
                    expect(page.get_by_test_id('shared-total-memory')).to_contain_text('제공 192 MiB')
                    for node in ids:
                        expect(page.get_by_test_id(f'node-status-badge-{node}')).to_contain_text('ONLINE')
                        expect(page.get_by_test_id(f'node-cpu-{node}')).to_contain_text('제공 500m')
                        expect(page.get_by_test_id(f'node-memory-{node}')).to_contain_text('제공 64 MiB')
                    gateway = page.get_by_title('Control Plane Gateway 실시간 RTT 지연시간')
                    expect(gateway).to_contain_text('ms')
                    assert '0 GiB' not in page.locator('#root').inner_text()
                    page.evaluate("""() => {
                        window.replayCards = [...document.querySelectorAll('[data-testid^="node-item-"]')];
                        window.replayBadges = [...document.querySelectorAll('[data-testid^="node-status-badge-"]')];
                        window.replayRemoved = 0;
                        window.replayObserver = new MutationObserver(records => records.forEach(record => {
                            for (const removed of record.removedNodes) if ([...window.replayCards, ...window.replayBadges].some(node => removed === node || removed.contains(node))) window.replayRemoved++;
                        }));
                        window.replayObserver.observe(document.querySelector('#root'), {childList:true, subtree:true});
                    }""")
                    start = time.monotonic()
                    page.wait_for_timeout(30000)
                    report['hostedReplayObservationSeconds'] = time.monotonic() - start
                    stable = page.evaluate("""() => ({removed:window.replayRemoved,
                        cards:window.replayCards.every(node => node.isConnected),
                        badges:window.replayBadges.every(node => node.isConnected)})""")
                    assert stable == dict(removed=0, cards=True, badges=True), stable
                    report['stableDOM'] = stable
                    assert len([row for row in requests if row['path'].endswith('/resource-usage')]) >= 21
                    page.screenshot(path=str(OUT / 'canonical-resources.png'), full_page=True)
                    mode['resources'] = 'partial'
                    expect(page.get_by_test_id('shared-total-memory')).to_contain_text('제공 128 MiB', timeout=7000)
                    expect(page.get_by_test_id('shared-total-cpu')).to_contain_text('제공 1500m')
                    mode['resources'] = 'error'
                    expect(page.get_by_test_id(f'node-item-{ids[0]}')).to_contain_text('자원 조회 실패', timeout=7000)
                    expect(page.get_by_test_id(f'node-cpu-{ids[0]}')).to_contain_text('이전 제공 500m')
                    expect(page.get_by_test_id('shared-total-cpu')).to_contain_text('제공 1000m')
                    for value in ['html', 'text', 'error']:
                        mode['health'] = value
                        expect(gateway).to_contain_text('비정상 응답', timeout=7000)
                        # Ensure each distinct proxy response has actually been consumed.
                        page.wait_for_timeout(5100)
                        assert any(row['path'] == '/healthz' and row['health'] == value for row in requests)
                    mode.update(health='healthy', resources='healthy')
                    expect(gateway).to_contain_text('ms', timeout=7000)
                    expect(page.get_by_test_id('shared-total-memory')).to_contain_text('제공 192 MiB', timeout=7000)
                    assert not errors and not failures, (errors, failures)
                    assert all(row['status'] == 503 and ('/gateway-healthz' in row['url'] or f'/{ids[0]}/resource-usage' in row['url']) for row in http_errors), http_errors
                    report.update(browserVersion=browser.version, passed=True, partialMemoryRetainedCPU=True,
                                  lastGoodExcludedFromCurrent=True, CPJSONRequired=True)
                finally:
                    browser.close()
    finally:
        if child is not None:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
            report['ownedChildExitCode'] = child.returncode
        server.shutdown()
        report.update(pageErrors=errors, requestFailures=failures, httpErrors=http_errors, fixtureRequests=requests)
        (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: sandboxed canonical dashboard HTTP replay, 30sec stable DOM, partial/failure recovery, genuine CP JSON health')


if __name__ == '__main__':
    main()
