"""Hosted-only, anonymous built-dist boot regression; no API/user/Run acceptance.

Serve the exact dist bytes with the deployed canonical security-header values.
Chromium keeps its normal sandbox, CSP and TLS defaults. The probe first proves
string evaluation is blocked, then a separate page boots the actual artifact.
"""
from __future__ import annotations

import functools
import hashlib
import http.server
import json
from pathlib import Path
import re
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "apps/web/dist"
OUT = ROOT / "artifacts/portal-strict-csp"
HEADER_PATH = ROOT / "deploy/intranet/portal/security-headers.conf"
HEADERS = dict(re.findall(r'^add_header (\S+) "([^"]*)" always;', HEADER_PATH.read_text(), re.M))
CSP = HEADERS["Content-Security-Policy"]
assert "script-src 'self';" in CSP and "unsafe-eval" not in CSP


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        for key, value in HEADERS.items():
            self.send_header(key, value)
        super().end_headers()

    def do_GET(self):
        probes = {
            "/csp-probe.html": ("text/html", b'<script src="/csp-probe.js"></script>'),
            "/csp-probe.js": ("text/javascript", b'''
                window.probe = {functionBlocked: false, evalBlocked: false};
                try { new Function('return 1')(); }
                catch (e) { window.probe.functionBlocked = e.name === 'EvalError'; }
                try { eval('1'); }
                catch (e) { window.probe.evalBlocked = e.name === 'EvalError'; }
            '''),
        }
        if self.path in probes:
            mime, body = probes[self.path]
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, *_args):
        pass


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    assert (DIST / "index.html").is_file(), "Build the real frontend first"
    # The emitted module graph must not contain the compiler that caused CR-CSP-01.
    # Source maps, unlike a grep for minified variable names, expose bundled modules.
    sources = [source for path in DIST.rglob("*.js.map")
               for source in json.loads(path.read_text())["sources"]]
    assert sources, "Production source maps are required for the module audit"
    forbidden = [source for source in sources if re.search(
        r"node_modules/ajv/dist/(?:compile/|(?:core|ajv|2020|2019)\.js$)", source)]
    assert not forbidden, f"Browser contains runtime Ajv compiler: {forbidden}"
    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(DIST)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    report = {"fixtureOnly": True, "actualPC3BrowserAcceptance": False,
              "anonymousOnly": True, "sandbox": True, "csp": CSP,
              "securityHeadersSHA256": hashlib.sha256(HEADER_PATH.read_bytes()).hexdigest(),
              "distSHA256": {str(p.relative_to(DIST)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in sorted(DIST.rglob("*")) if p.is_file()},
              "bundledAjvCompilerModules": forbidden}
    errors, failures, responses, methods, csp_errors = [], [], [], [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True)
            try:
                report["browserVersion"] = browser.version
                probe = browser.new_page()
                response = probe.goto(origin + "/csp-probe.html")
                assert response.headers["content-security-policy"] == CSP
                probe.wait_for_function("window.probe?.functionBlocked && window.probe?.evalBlocked")
                report["negativeControl"] = probe.evaluate("window.probe")
                probe.close()
                page = browser.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("requestfailed", lambda req: failures.append({"url": req.url, "failure": req.failure}))
                page.on("request", lambda req: methods.append(req.method))
                page.on("response", lambda res: responses.append({"url": res.url, "status": res.status}))
                page.on("console", lambda msg: csp_errors.append(msg.text)
                        if msg.type == "error" and "Content Security Policy" in msg.text else None)
                response = page.goto(origin + "/")
                assert response.status == 200
                assert response.headers["content-security-policy"] == CSP
                # No session, login click, form POST, mock healthy data or user action.
                page.locator("#root h1").filter(has_text="SaintVision").wait_for(state="visible")
                page.locator("#root button").filter(has_text="로그인").wait_for(state="visible")
                report["rootChildren"] = page.locator("#root").evaluate("root => root.children.length")
                assert report["rootChildren"] > 0
                assert not errors, errors
                assert not failures, failures
                assert not csp_errors, csp_errors
                http_failures = [r for r in responses if r["status"] >= 400]
                # Base96 index references an absent favicon. Keep that observed 404 in
                # evidence without expanding this boot fix into unrelated icon work.
                # Every other failed HTTP response, including all executable assets,
                # CSS and auth-config, still fails this gate. No request is mocked.
                known_icon_failures = [r for r in http_failures
                                       if r["url"] == origin + "/favicon.svg" and r["status"] == 404]
                report["knownBase96MissingFavicon"] = known_icon_failures
                assert not [r for r in http_failures if r not in known_icon_failures], responses
                assert set(methods) == {"GET"}, methods
                assert any("/assets/" in r["url"] and ".js" in r["url"] for r in responses)
                assert any("/assets/" in r["url"] and ".css" in r["url"] for r in responses)
                assert any(r["url"].endswith("/auth-config.js") for r in responses)
                page.screenshot(path=str(OUT / "anonymous-login.png"))
                report["bootPassed"] = True
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        report.update(pageErrors=errors, requestFailures=failures, responses=responses,
                      requestMethods=methods, cspErrors=csp_errors)
        (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS: actual built frontend booted under canonical strict CSP; eval/Function blocked; anonymous hosted fixture only")


if __name__ == "__main__":
    main()
