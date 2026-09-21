#!/usr/bin/env python3
"""Run Real Browser (Google Chrome) and Real Uvicorn Backend End-to-End Acceptance.

Architecture:
- Real ASGI Server: Uvicorn 0.52.4 running FastAPI create_app on 127.0.0.1:<backend-port>
- Real Dev Server Proxy: Vite 5.x running on 127.0.0.1:<frontend-port> (proxying /v1 to backend)
- Real Browser: Google Chrome (Official Build, Blink engine)
- Zero Playwright network mocking on /v1: all API calls travel through Vite proxy to actual Uvicorn TCP socket.
- Endpoint: GET /v1/projects/{project}/runs/{run_id}/artifacts/content?path=src/server.ts
  executes canonical run_file -> artifact_content_response contract.
- Scenarios Tested:
  1. 'verified': Genuine 50 bytes + matching X-Content-SHA256 wire header -> WebCrypto passes, file saved to disk, [전송 확인 완료] banner rendered.
  2. 'mismatch': Corrupted bytes in transit vs original header -> WebCrypto detects mismatch, download blocked (0 bytes written), [전송 불일치 · 저장 차단] alert rendered.
  3. 'missing-header': Downgrade attack / header stripped -> Client detects missing header, download blocked (0 bytes written), [전송 헤더 누락 · 저장 차단] alert rendered.
- Separation of Tools and Evidence:
  This script is a permanent repository tool in tools/.
  All ephemeral runtime evidence (screenshots, binary downloads, JSON records)
  are output to --output-dir (defaults to scratch/, which is gitignored).
"""

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

# Resolve repository root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "control-plane" / "src"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import uvicorn
from inv.app import create_app
from inv.result_view import ResultView
from playwright.sync_api import sync_playwright
from starlette.responses import Response

DEFAULT_CHROME_PATH = os.environ.get(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.name == "nt"
    else "/usr/bin/google-chrome",
)

SAMPLE_CONTENT = b"saintvision-real-uvicorn-artifact-bytes-model-153\n"
SAMPLE_SHA256 = hashlib.sha256(SAMPLE_CONTENT).hexdigest()
SAMPLE_ARTIFACT = {
    "path": "outputs/metrics.json",
    "checksumSha256": SAMPLE_SHA256,
    "byteSize": len(SAMPLE_CONTENT),
    "verified": True,
    "evidenceId": "evd_00000000000000000000000000",
}

SAMPLE_NODE = {
    "nodeId": "nod_00000000000000000000000001",
    "hostname": "pacs-worker-01",
    "status": "online",
    "os": "linux",
    "heartbeatAt": "2026-09-22T04:00:00Z",
    "cpuCores": 16,
    "cpuUsagePercent": 30,
    "memoryTotalBytes": 68719476736,
    "memoryUsedBytes": 20000000000,
    "storageTotalBytes": 2199023255552,
    "storageUsedBytes": 500000000000,
    "gpuCount": 1,
    "gpuName": "NVIDIA A100",
    "gpuVramTotalBytes": 85899345920,
    "gpuVramUsedBytes": 20000000000,
}

VALID_SUBJECT_ID = "oidc:" + "a" * 64
VALID_TENANT_ID = "00000000-0000-4000-8000-000000000001"


class MockTokens:
    def verify(self, token):
        principal = SimpleNamespace(
            subject_id=VALID_SUBJECT_ID,
            tenant_id=VALID_TENANT_ID,
        )
        return SimpleNamespace(principal=principal, expires_at=int(time.time()) + 3600)


def build_real_backend_app(frontend_port: int, backend_port: int, scenario: str = "verified"):
    from inv.control import Control

    Control.projects = lambda self, principal: {
        "projects": [
            {
                "id": "prj_pacs_core",
                "projectId": "prj_pacs_core",
                "name": "SaintVision PACS AI Model Pipeline",
                "displayName": "SaintVision PACS AI Model Pipeline",
                "createdAt": "2026-09-22T00:00:00Z",
                "kernelLinked": True,
                "kernelEnabled": True,
            }
        ],
        "count": 1,
    }

    run_state = "failed" if scenario == "evidence-failed" else "succeeded"

    Control.list_runs = lambda self, principal, project, after=None, limit=50: {
        "items": [
            {
                "id": "run_pacs_pipeline_01",
                "runId": "run_pacs_pipeline_01",
                "projectId": "prj_pacs_core",
                "state": run_state,
                "version": 1,
                "attempt": 1,
                "stateUpdatedAt": "2026-09-22T04:00:00Z",
            }
        ],
        "count": 1,
        "nextCursor": None,
    }

    Control.get = lambda self, principal, project, run_id: {
        "id": "run_pacs_pipeline_01",
        "runId": "run_pacs_pipeline_01",
        "projectId": "prj_pacs_core",
        "state": run_state,
        "version": 1,
        "attempt": 1,
        "stateUpdatedAt": "2026-09-22T04:00:00Z",
        "resourceReleasePending": False,
    }

    Control.list_approvals = lambda self, principal, project, after=None, limit=50, run_id=None: {
        "items": [],
        "nextCursor": None,
    }

    # Bind result, download and artifacts on ResultView so canonical handlers use them
    def mock_result(self, principal, run_id, project=None):
        if scenario == "evidence-failed":
            return {
                "source": "execution-kernel",
                "runId": run_id,
                "projectId": project or "prj_pacs_core",
                "state": "failed",
                "version": 1,
                "attemptCount": 1,
                "stateUpdatedAt": "2026-09-22T04:00:00Z",
                "sealed": True,
                "executionConfirmed": True,
                "commandId": "00000000-0000-4000-8000-000000000002",
                "nodeId": None,
                "stopReceipt": {"exitCode": 1},
                "evidence": None,
                "completedAt": "2026-09-22T04:00:00Z",
                "output": None,
                "outputAbsentReason": "Execution aborted due to verification failure",
                "resourceReleasePending": False,
            }
        elif scenario == "evidence-unverified":
            return {
                "source": "execution-kernel",
                "runId": run_id,
                "projectId": project or "prj_pacs_core",
                "state": "succeeded",
                "version": 1,
                "attemptCount": 1,
                "stateUpdatedAt": "2026-09-22T04:00:00Z",
                "sealed": True,
                "executionConfirmed": True,
                "commandId": "00000000-0000-4000-8000-000000000002",
                "nodeId": None,
                "stopReceipt": {"exitCode": 0},
                "evidence": {
                    "evidenceId": "evd_00000000000000000000000000",
                },
                "completedAt": "2026-09-22T04:00:00Z",
                "output": None,
                "outputAbsentReason": "No committed output for this attempt",
                "resourceReleasePending": False,
            }
        else:
            return {
                "source": "execution-kernel",
                "runId": run_id,
                "projectId": project or "prj_pacs_core",
                "state": "succeeded",
                "version": 1,
                "attemptCount": 1,
                "stateUpdatedAt": "2026-09-22T04:00:00Z",
                "sealed": True,
                "executionConfirmed": True,
                "commandId": "00000000-0000-4000-8000-000000000002",
                "nodeId": None,
                "stopReceipt": {"exitCode": 0},
                "evidence": {
                    "evidenceId": "evd_00000000000000000000000000",
                },
                "completedAt": "2026-09-22T04:00:00Z",
                "output": {
                    "sha256": SAMPLE_SHA256,
                    "sizeBytes": len(SAMPLE_CONTENT),
                    "verified": True,
                },
                "outputAbsentReason": None,
                "resourceReleasePending": False,
            }

    ResultView.result = mock_result

    ResultView.artifacts = lambda self, principal, run_id, project=None: {
        "source": "execution-kernel",
        "runId": "run_pacs_pipeline_01",
        "artifacts": [SAMPLE_ARTIFACT],
        "count": 1,
        "verifiedCount": 1,
        "completedAt": "2026-09-22T04:00:00Z",
    }

    ResultView.download = lambda self, principal, run_id, path, project=None: {
        "content": SAMPLE_CONTENT,
        "artifact": SAMPLE_ARTIFACT,
    }

    app = create_app(
        database=object(),
        tokens=MockTokens(),
        allowed_origins=[
            f"http://127.0.0.1:{frontend_port}",
            f"http://localhost:{frontend_port}",
            f"http://127.0.0.1:{backend_port}",
            f"http://localhost:{backend_port}",
        ],
    )

    # Middleware to inject wire scenarios if requested
    @app.middleware("http")
    async def scenario_middleware(request, call_next):
        response = await call_next(request)
        if "/artifacts/content" in request.url.path:
            if scenario == "mismatch":
                # Wire tampering scenario: corrupted body transmitted, but header claims original hash
                corrupted_bytes = b"saintvision-tampered-wire-corrupted-bytes-attack-fail\n"
                return Response(
                    corrupted_bytes,
                    status_code=200,
                    media_type="application/octet-stream",
                    headers={
                        "Content-Disposition": 'attachment; filename="artifact.bin"',
                        "X-Content-SHA256": SAMPLE_SHA256,  # Original hash (deliberate mismatch)
                        "Content-Length": str(len(corrupted_bytes)),
                        "X-Content-Type-Options": "nosniff",
                    },
                )
            elif scenario == "missing-header":
                # Downgrade attack scenario: X-Content-SHA256 stripped from response
                return Response(
                    SAMPLE_CONTENT,
                    status_code=200,
                    media_type="application/octet-stream",
                    headers={
                        "Content-Disposition": 'attachment; filename="artifact.bin"',
                        "Content-Length": str(len(SAMPLE_CONTENT)),
                        "X-Content-Type-Options": "nosniff",
                        # X-Content-SHA256 is stripped
                    },
                )
        return response

    @app.get("/v1/nodes")
    def get_nodes():
        return {"items": [SAMPLE_NODE], "count": 1}

    @app.get("/v1/projects/prj_pacs_core/workspaces")
    def get_workspaces():
        return {"projectId": "prj_pacs_core", "workspaces": [], "count": 0}

    @app.get("/v1/health")
    def get_health():
        return {"status": "ok"}

    return app


def start_uvicorn_server(backend_port: int, frontend_port: int, scenario: str = "verified"):
    app = build_real_backend_app(frontend_port, backend_port, scenario)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=backend_port,
        log_level="warning",  # Keep output readable during multi-scenario runs
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    return server, thread


def run_scenario(
    scenario: str,
    backend_port: int = 8080,
    frontend_port: int = 3005,
    chrome_path: str = DEFAULT_CHROME_PATH,
    output_dir: str = str(REPO_ROOT / "scratch"),
    headless: bool = True,
) -> bool:
    frontend_url = f"http://127.0.0.1:{frontend_port}"
    backend_url = f"http://127.0.0.1:{backend_port}"

    print(f"\n{'='*70}")
    print(f"[Scenario: {scenario.upper()}] Starting Real Uvicorn Backend on {backend_url} ...")
    print(f"{'='*70}")
    server, server_thread = start_uvicorn_server(backend_port, frontend_port, scenario)
    time.sleep(1.5)  # Wait for TCP bind

    try:
        # Probe health
        with urllib.request.urlopen(f"{backend_url}/v1/health", timeout=5) as res:
            assert res.status == 200

        with urllib.request.urlopen(f"{frontend_url}/", timeout=5) as res:
            assert res.status == 200

        os.makedirs(output_dir, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=chrome_path,
                headless=headless,
                args=["--no-sandbox", "--disable-gpu", "--window-size=1920,1080"],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True,
            )
            page = context.new_page()

            # Mock only IdP token route for local OAuth transaction
            page.route(
                "**/oauth/**",
                lambda route: route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps({
                        "access_token": "mock_jwt_token_for_real_uvicorn",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }),
                )
                if "/oauth/token" in route.request.url
                else route.continue_(),
            )

            # Setup OAuth transaction
            page.add_init_script(f"""
                window.__SAINTVISION_CONFIG__ = {{
                    idpAuthorizeUrl: '{frontend_url}/oauth/authorize',
                    idpTokenUrl: '{frontend_url}/oauth/token',
                    clientId: 'saintvision-web',
                    scope: 'openid profile email'
                }};
                const tx = {{
                    state: 'real_uvicorn_state',
                    verifier: 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk',
                    createdAt: Date.now(),
                    redirectUri: '{frontend_url}/callback',
                    config: {{
                        idpAuthorizeUrl: '{frontend_url}/oauth/authorize',
                        idpTokenUrl: '{frontend_url}/oauth/token',
                        clientId: 'saintvision-web',
                        scope: 'openid profile email'
                    }}
                }};
                sessionStorage.setItem('saintvision.oauth.transaction', JSON.stringify(tx));
            """)

            # Navigate to Studio Step 4
            page.goto(f"{frontend_url}/callback?code=mock_code&state=real_uvicorn_state", wait_until="domcontentloaded")
            page.wait_for_timeout(1500)

            # -----------------------------------------------------------------
            # EvidenceViewer & RunDetail Acceptance Scenarios
            # -----------------------------------------------------------------
            if scenario.startswith("evidence-"):
                print(f"\n[Acceptance: {scenario.upper()}] Navigating to Runs tab...")
                runs_tab = page.locator('button:has-text("Runs 실행")')
                runs_tab.wait_for(state="visible", timeout=10000)
                runs_tab.click()
                page.wait_for_timeout(1500)

                # Click the Run row to open RunDetail
                print("[Acceptance] Selecting Run 'run_pacs_pipeline_01' in RunList...")
                run_row = page.locator('tr:has-text("run_pacs_pipeline_01")')
                run_row.wait_for(state="visible", timeout=10000)
                run_row.click()
                page.wait_for_timeout(1500)

                # Verify RunDetail is mounted
                print("[Acceptance] Verifying RunDetail mounted...")
                timeline_tab = page.locator('button:has-text("1. 상태 전이 타임라인")')
                timeline_tab.wait_for(state="visible", timeout=10000)
                rundetail_screenshot = os.path.join(output_dir, "real_chrome_rundetail_timeline.png")
                page.screenshot(path=rundetail_screenshot)
                print(f"✔ [RunDetail] Saved screenshot: {rundetail_screenshot}")

                # Click "🔍 불변 증거 열람" button
                print("[Acceptance] Clicking '🔍 불변 증거 열람' button...")
                evidence_btn = page.locator('button:has-text("🔍 불변 증거 열람")')
                evidence_btn.wait_for(state="visible", timeout=10000)
                evidence_btn.click()
                page.wait_for_timeout(1500)

                # Verify EvidenceViewer is mounted
                viewer_header = page.locator('h2:has-text("불변 증거 (Evidence) 패키지")')
                viewer_header.wait_for(state="visible", timeout=10000)
                print(f"✔ [EvidenceViewer] Mounted for {scenario}!")

                if scenario == "evidence-verified":
                    print("[Acceptance: evidence-verified] Checking PASS badge and policy specs...")
                    pass_badge = page.locator('span:has-text("✓ 출력 무결성 검증 통과 (PASS)")')
                    pass_badge.wait_for(state="visible", timeout=10000)
                    assert pass_badge.is_visible()

                    specs_box = page.locator('span:has-text("[시스템 정책 사양]")')
                    assert specs_box.is_visible()

                    screenshot_path = os.path.join(output_dir, "real_chrome_evidence_verified_pass.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [evidence-verified] PASS badge verified! Saved: {screenshot_path}")

                elif scenario == "evidence-unverified":
                    print("[Acceptance: evidence-unverified] Checking UNVERIFIED badge & notice banner...")
                    unverified_badge = page.locator('span:has-text("⚠️ 출력 무결성 미검증 (UNVERIFIED)")')
                    unverified_badge.wait_for(state="visible", timeout=10000)
                    assert unverified_badge.is_visible()

                    notice_banner = page.locator('[data-testid="evidence-unverified-notice"]')
                    notice_banner.wait_for(state="visible", timeout=10000)
                    notice_text = notice_banner.inner_text()
                    print(f"✔ [evidence-unverified] Notice banner: {notice_text.splitlines()[0]}")
                    assert "권장 조치" in notice_text
                    assert "미검증 (UNVERIFIED)" in notice_text

                    # Ensure PASS badge is NOT present
                    assert page.locator('span:has-text("✓ 출력 무결성 검증 통과 (PASS)")').count() == 0

                    screenshot_path = os.path.join(output_dir, "real_chrome_evidence_unverified_notice.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [evidence-unverified] UNVERIFIED banner verified! Saved: {screenshot_path}")

                elif scenario == "evidence-failed":
                    print("[Acceptance: evidence-failed] Checking FAIL badge...")
                    fail_badge = page.locator('span:has-text("✗ 출력 무결성 검증 실패 (FAIL)")')
                    fail_badge.wait_for(state="visible", timeout=10000)
                    assert fail_badge.is_visible()

                    # Ensure PASS badge is NOT present
                    assert page.locator('span:has-text("✓ 출력 무결성 검증 통과 (PASS)")').count() == 0

                    screenshot_path = os.path.join(output_dir, "real_chrome_evidence_failed.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [evidence-failed] FAIL badge verified! Saved: {screenshot_path}")

                # Test navigation back to RunDetail
                back_btn = page.locator('button:has-text("← 이전으로 돌아가기")')
                back_btn.click()
                page.wait_for_timeout(1000)
                timeline_tab.wait_for(state="visible", timeout=10000)
                print("✔ [Navigation] Returned to RunDetail successfully!")

            # -----------------------------------------------------------------
            # DeveloperStudio Step 4 Artifact Download Scenarios
            # -----------------------------------------------------------------
            else:
                studio_tab = page.locator('button:has-text("개발 Studio")')
                studio_tab.wait_for(state="visible", timeout=10000)
                studio_tab.click()
                page.wait_for_timeout(1500)

                step4_btn = page.locator('button:has-text("4. 실행 상태 & 실시간 로그")')
                step4_btn.wait_for(state="visible", timeout=10000)
                step4_btn.click()
                page.wait_for_timeout(1500)

                raw_download_btn = page.locator('[data-testid="artifact-raw-download-btn"]')
                raw_download_btn.wait_for(state="visible", timeout=10000)

                # -----------------------------------------------------------------
                # Branch 1: VERIFIED (Happy Path)
                # -----------------------------------------------------------------
                if scenario == "verified":
                    print("[Acceptance: VERIFIED] Expecting genuine download and [전송 확인 완료] banner...")
                    with page.expect_download(timeout=15000) as download_info:
                        raw_download_btn.click()

                    download = download_info.value
                    download_path = os.path.join(output_dir, "downloaded_real_uvicorn_artifact.bin")
                    download.save_as(download_path)

                    page.wait_for_timeout(1000)
                    notice_banner = page.locator('[role="status"]:has-text("[전송 확인 완료]")')
                    notice_banner.wait_for(state="visible", timeout=10000)
                    notice_text = notice_banner.inner_text()
                    print(f"✔ [VERIFIED] Banner verified: {notice_text.splitlines()[0]}")

                    assert "[전송 확인 완료]" in notice_text
                    assert "50 Bytes" in notice_text
                    assert "수신 바이트와 서버 헤더 일치" in notice_text

                    with open(download_path, "rb") as f:
                        downloaded_bytes = f.read()

                    assert downloaded_bytes == SAMPLE_CONTENT, "Downloaded bytes must match server byte-for-byte"
                    assert hashlib.sha256(downloaded_bytes).hexdigest() == SAMPLE_SHA256

                    screenshot_path = os.path.join(output_dir, "real_chrome_real_uvicorn_verified.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [VERIFIED] Saved screenshot: {screenshot_path}")

                # -----------------------------------------------------------------
                # Branch 2: MISMATCH (Corrupted / Tampered Wire Bytes)
                # -----------------------------------------------------------------
                elif scenario == "mismatch":
                    print("[Acceptance: MISMATCH] Expecting download blocked and [전송 불일치 · 저장 차단] alert...")
                    download_triggered = False

                    def on_download(d):
                        nonlocal download_triggered
                        download_triggered = True

                    page.on("download", on_download)
                    raw_download_btn.click()
                    page.wait_for_timeout(2000)

                    assert not download_triggered, "CRITICAL: Download MUST be blocked on checksum mismatch!"
                    print("✔ [MISMATCH] Chrome download event was blocked (0 bytes downloaded).")

                    notice_banner = page.locator('[role="alert"]:has-text("[전송 불일치 · 저장 차단]")')
                    notice_text = notice_banner.inner_text()
                    print(f"✔ [MISMATCH] Alert banner verified: {notice_text.splitlines()[0]}")

                    assert "[전송 불일치 · 저장 차단]" in notice_text
                    assert "전송 중 손상 위험으로 파일 저장을 차단했습니다" in notice_text

                    screenshot_path = os.path.join(output_dir, "real_chrome_real_uvicorn_mismatch_blocked.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [MISMATCH] Saved screenshot: {screenshot_path}")

                # -----------------------------------------------------------------
                # Branch 3: MISSING-HEADER (Downgrade Attack Prevention)
                # -----------------------------------------------------------------
                elif scenario == "missing-header":
                    print("[Acceptance: MISSING-HEADER] Expecting download blocked and [전송 헤더 누락 · 저장 차단] alert...")
                    download_triggered = False

                    def on_download(d):
                        nonlocal download_triggered
                        download_triggered = True

                    page.on("download", on_download)
                    raw_download_btn.click()
                    page.wait_for_timeout(2000)

                    assert not download_triggered, "CRITICAL: Download MUST be blocked on missing X-Content-SHA256 header!"
                    print("✔ [MISSING-HEADER] Chrome download event was blocked (0 bytes downloaded).")

                    notice_banner = page.locator('[role="alert"]:has-text("[전송 헤더 누락 · 저장 차단]")')
                    notice_banner.wait_for(state="visible", timeout=10000)
                    notice_text = notice_banner.inner_text()
                    print(f"✔ [MISSING-HEADER] Alert banner verified: {notice_text.splitlines()[0]}")

                    assert "[전송 헤더 누락 · 저장 차단]" in notice_text
                    assert "전송 검증 생략 및 조용한 강등 위험을 방지하기 위해 파일 저장을 차단했습니다" in notice_text

                    screenshot_path = os.path.join(output_dir, "real_chrome_real_uvicorn_missing_header_blocked.png")
                    page.screenshot(path=screenshot_path)
                    print(f"✔ [MISSING-HEADER] Saved screenshot: {screenshot_path}")

            browser.close()
            print(f"✔ [Scenario: {scenario.upper()}] PASSED!")
            return True

    finally:
        server.should_exit = True
        server_thread.join(timeout=3)


def run_acceptance(
    backend_port: int = 8080,
    frontend_port: int = 3005,
    chrome_path: str = DEFAULT_CHROME_PATH,
    output_dir: str = str(REPO_ROOT / "scratch"),
    headless: bool = True,
    scenario: str = "all",
) -> bool:
    if scenario == "all":
        scenarios = [
            "verified",
            "mismatch",
            "missing-header",
            "evidence-verified",
            "evidence-unverified",
            "evidence-failed",
        ]
    elif scenario == "all-artifacts":
        scenarios = ["verified", "mismatch", "missing-header"]
    elif scenario == "all-evidence":
        scenarios = ["evidence-verified", "evidence-unverified", "evidence-failed"]
    else:
        scenarios = [scenario]

    results = {}

    print("====================================================================")
    print(f"REAL CHROME + REAL UVICORN 0.52.4 END-TO-END ACCEPTANCE SUITE")
    print(f"Target Scenarios: {scenarios}")
    print("====================================================================")

    for sc in scenarios:
        ok = run_scenario(
            scenario=sc,
            backend_port=backend_port,
            frontend_port=frontend_port,
            chrome_path=chrome_path,
            output_dir=output_dir,
            headless=headless,
        )
        results[sc] = ok
        if not ok:
            print(f"\n✖ Scenario {sc} FAILED!")
            return False

    summary_file = os.path.join(output_dir, "chrome_real_uvicorn_acceptance_result.json")
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "server": "Uvicorn 0.52.4 (FastAPI create_app) on 127.0.0.1:8080",
                "proxy": "Vite 5.x on 127.0.0.1:3005",
                "browser": "Google Chrome (Official Build, Blink engine)",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "passed": True,
                "scenarios": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print("\n====================================================================")
    print("ALL TARGET SCENARIOS PASSED 100%!")
    print(f"Results recorded in: {summary_file}")
    print("====================================================================")
    return True


def main():
    parser = argparse.ArgumentParser(description="Real Browser + Real Uvicorn E2E Acceptance Tool")
    parser.add_argument("--backend-port", type=int, default=8080, help="Uvicorn backend port (default: 8080)")
    parser.add_argument("--frontend-port", type=int, default=3005, help="Vite frontend dev server port (default: 3005)")
    parser.add_argument("--chrome-path", type=str, default=DEFAULT_CHROME_PATH, help="Path to Google Chrome binary")
    parser.add_argument("--output-dir", type=str, default=str(REPO_ROOT / "scratch"), help="Directory for ephemeral evidence output")
    parser.add_argument("--headed", action="store_true", help="Run Chrome in headed mode (visible GUI)")
    parser.add_argument(
        "--scenario",
        type=str,
        default="all",
        choices=[
            "all",
            "all-artifacts",
            "all-evidence",
            "verified",
            "mismatch",
            "missing-header",
            "evidence-verified",
            "evidence-unverified",
            "evidence-failed",
        ],
        help="Acceptance scenario to run (default: all 6 branches)",
    )
    args = parser.parse_args()

    success = run_acceptance(
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        chrome_path=args.chrome_path,
        output_dir=args.output_dir,
        headless=not args.headed,
        scenario=args.scenario,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
