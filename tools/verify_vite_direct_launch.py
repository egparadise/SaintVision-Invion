"""Hosted-only clean direct vite.js/main-config browser boot regression.

Run before npm lint/test/build/dev hooks. Never delete source or generated files:
the owned hosted checkout must start with both ignored outputs absent.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web"
OUT = ROOT / "artifacts/vite-direct-launch"
OUTPUTS = [WEB / "src/contracts/node-certificate-validator.mjs",
           WEB / "src/contracts/node-certificate-validator.manifest.json"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert os.getenv("GITHUB_ACTIONS") == "true" and os.name == "posix", "Hosted Linux CI only"
    OUT.mkdir(parents=True, exist_ok=True)
    assert not subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT)
    for path in OUTPUTS:
        assert path.resolve().is_relative_to(WEB.resolve())
        assert not subprocess.check_output(["git", "ls-files", "--", str(path.relative_to(ROOT))], cwd=ROOT)
    missing = {str(path.relative_to(ROOT)): not path.exists() for path in OUTPUTS}
    assert all(missing.values()), "Fresh regression must precede every npm generation hook"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    argv = [shutil.which("node"), "node_modules/vite/bin/vite.js", "--config", "vite.config.ts",
            "--host", "127.0.0.1", "--port", str(port), "--strictPort"]
    report = {"fixtureOnly": True, "actualPC3BrowserAcceptance": False,
              "anonymousOnly": True, "npmLifecycleUsed": False,
              "command": argv, "cwd": str(WEB), "mainConfig": "apps/web/vite.config.ts",
              "mainConfigSHA256": sha256(WEB / "vite.config.ts"), "missingBefore": missing,
              "sourceSHA": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
              "sandbox": True, "deletedFiles": []}
    errors, failures, responses, methods = [], [], [], []
    child = None
    try:
        with (OUT / "direct-vite.log").open("wb") as log:
            child = subprocess.Popen(argv, cwd=WEB, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True)
            report["ownedChildPID"] = child.pid
            deadline = time.monotonic() + 30
            while True:
                assert child.poll() is None, "Direct Vite exited before readiness (including generation failure)"
                try:
                    with urlopen(origin + "/", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                assert time.monotonic() < deadline, "Direct Vite readiness deadline exceeded"
                time.sleep(0.1)
            assert all(path.is_file() for path in OUTPUTS), "Config did not generate both outputs before readiness"
            assert child.poll() is None, "Owned Vite exited after transport readiness"
            manifest = json.loads(OUTPUTS[1].read_text("utf8"))
            assert manifest["format"] == "esm" and manifest["selfContained"] is True
            assert manifest["schemaSHA256"] == sha256(ROOT / "contracts/v1alpha1/core.schema.json")
            assert manifest["lockSHA256"] == sha256(WEB / "package-lock.json")
            assert manifest["generatorSHA256"] == sha256(WEB / "scripts/node-certificate-validator.mjs")
            assert manifest["validatorSHA256"] == sha256(OUTPUTS[0])
            report["generatedAfter"] = {str(path.relative_to(ROOT)): sha256(path) for path in OUTPUTS}
            report["manifest"] = manifest
            # An index200 is only a transport probe. Success requires the actual
            # App module graph and login UI in an ordinary sandboxed browser.
            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True, chromium_sandbox=True)
                try:
                    report["browserVersion"] = browser.version
                    page = browser.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("requestfailed", lambda req: failures.append({"url": req.url, "failure": req.failure}))
                    page.on("request", lambda req: methods.append(req.method))
                    page.on("response", lambda res: responses.append({"url": res.url, "status": res.status}))
                    response = page.goto(origin + "/")
                    assert response.status == 200
                    page.locator("#root h1").filter(has_text="SaintVision").wait_for(state="visible")
                    page.locator("#root button").filter(has_text="로그인").wait_for(state="visible")
                    report["rootChildren"] = page.locator("#root").evaluate("root => root.children.length")
                    assert report["rootChildren"] > 0
                    assert not errors and not failures, (errors, failures)
                    http_errors = [row for row in responses if row["status"] >= 400]
                    known_icons = [row for row in http_errors if row["url"] == origin + "/favicon.svg" and row["status"] == 404]
                    report["knownBase96MissingFavicon"] = known_icons
                    assert not [row for row in http_errors if row not in known_icons], http_errors
                    assert set(methods) == {"GET"}, methods
                    modules = [row for row in responses if urlsplit(row["url"]).path ==
                               "/src/contracts/node-certificate-validator.mjs"]
                    assert modules and all(row["status"] == 200 for row in modules), modules
                    assert child.poll() is None, "Owned Vite exited while checking the browser graph"
                    report["validatorModuleResponses"] = modules
                    page.screenshot(path=str(OUT / "anonymous-login.png"))
                    report["bootPassed"] = True
                finally:
                    browser.close()
    finally:
        if child is not None:
            # Only the new session/group this script created, never a preexisting Vite.
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
            child.wait(timeout=10)
            report["ownedChildExitCode"] = child.returncode
        report.update(pageErrors=errors, requestFailures=failures, responses=responses, requestMethods=methods)
        (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print("PASS: clean direct vite.js/main config generated canonical ESM and rendered anonymous login; hosted fixture only")


if __name__ == "__main__":
    main()
