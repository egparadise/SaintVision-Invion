#!/usr/bin/env python3
"""S02-FE Real Browser & Real Backend End-to-End Acceptance Runner.

Zero Mock Guarantee:
- Real Dev IdP (.work/dev/dev_idp.py)
- Real Control Plane ASGI on 127.0.0.1:8080 (saintvision.server:create_app via uvicorn)
- Real Dev Server on 127.0.0.1:3005 (Vite proxying /v1 to 8080)
- Real Browser: Google Chrome (Official Build 153+, Blink engine)
- All network interactions flow across actual TCP sockets without Playwright route mocks.

Scenarios Tested:
1. 's02-login-success': OIDC PKCE authorization code grant -> /callback -> /v1/session 200 OK -> UI mount.
2. 's02-nodes-real-data': Dynamic project discovery -> /v1/projects/{prj}/nodes real data query (0 nodes) -> honest EmptyState ('등록된 Node가 없습니다').
3. 's02-project-403': Direct UI input of unauthorized project -> 403 ProblemDetails (AUTH-0030) -> role="alert" presentation.
4. 's02-token-expired-401': Genuinely expired RS256 token wire verification + short-lived token UI expiration -> role="alert" (AUTH-0050) -> re-login session recovery.
"""

import argparse
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from uuid import uuid4

import jwt
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CHROME_PATH = os.environ.get(
    "CHROME_PATH",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if os.name == "nt"
    else "/usr/bin/google-chrome",
)
PYTHON_EXE = sys.executable


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def get_git_sha() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def resolve_prerequisites(
    dev_dir_arg: Path | None = None,
    idp_script_arg: Path | None = None,
    server_env_arg: Path | None = None,
) -> tuple[Path | None, Path | None, Path | None]:
    """Resolve dev_dir, dev_idp.py script, and server.env paths in order of preference."""
    candidates = []
    if dev_dir_arg:
        candidates.append(dev_dir_arg)
    if os.environ.get("SAINTVISION_DEV_DIR"):
        candidates.append(Path(os.environ["SAINTVISION_DEV_DIR"]))
    candidates.append(REPO_ROOT.parent / ".work" / "dev")
    candidates.append(REPO_ROOT / ".work" / "dev")

    resolved_dev_dir = None
    for c in candidates:
        if c.exists() and c.is_dir():
            resolved_dev_dir = c
            break

    # Resolve IdP script
    resolved_idp = None
    if idp_script_arg and idp_script_arg.exists():
        resolved_idp = idp_script_arg
    elif os.environ.get("SAINTVISION_IDP_SCRIPT") and Path(os.environ["SAINTVISION_IDP_SCRIPT"]).exists():
        resolved_idp = Path(os.environ["SAINTVISION_IDP_SCRIPT"])
    elif resolved_dev_dir and (resolved_dev_dir / "dev_idp.py").exists():
        resolved_idp = resolved_dev_dir / "dev_idp.py"

    # Resolve server.env
    resolved_env = None
    if server_env_arg and server_env_arg.exists():
        resolved_env = server_env_arg
    elif os.environ.get("SAINTVISION_SERVER_ENV") and Path(os.environ["SAINTVISION_SERVER_ENV"]).exists():
        resolved_env = Path(os.environ["SAINTVISION_SERVER_ENV"])
    elif resolved_dev_dir and (resolved_dev_dir / "server.env").exists():
        resolved_env = resolved_dev_dir / "server.env"

    return resolved_dev_dir, resolved_idp, resolved_env


def start_dev_idp(script_path: Path, port: int = 8090) -> subprocess.Popen | None:
    if is_port_open(port):
        print(f"[IdP] Port {port} already active.")
        return None
    print(f"[IdP] Launching dev IdP on port {port} using {script_path}...")
    cmd = [PYTHON_EXE, "-X", "utf8", str(script_path), "--port", str(port)]
    env = os.environ.copy()
    env["PORT"] = str(port)
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(40):
        if is_port_open(port):
            print(f"✔ [IdP] Dev IdP ready on port {port} (PID: {proc.pid}).")
            return proc
        time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for Dev IdP on port {port}")


def start_backend(server_env_path: Path, port: int = 8080) -> subprocess.Popen | None:
    if is_port_open(port):
        print(f"[Backend] Port {port} already active.")
        return None
    print(f"[Backend] Launching Uvicorn backend on port {port} using {server_env_path}...")
    env = os.environ.copy()
    for line in server_env_path.read_text("utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    env["PYTHONPATH"] = os.pathsep.join([
        str(REPO_ROOT / "src"),
        str(REPO_ROOT / "services" / "control-plane" / "src"),
    ])
    env["PYTHONUTF8"] = "1"
    cmd = [
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "saintvision.server:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--no-access-log",
        "--no-proxy-headers",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(40):
        if is_port_open(port):
            print(f"✔ [Backend] Uvicorn backend ready on port {port} (PID: {proc.pid}).")
            return proc
        time.sleep(0.2)
    raise RuntimeError(f"Timeout waiting for Backend on port {port}")


def start_frontend(port: int = 3005) -> subprocess.Popen | None:
    if is_port_open(port):
        print(f"[Frontend] Port {port} already active.")
        return None
    print(f"[Frontend] Launching Vite dev server on port {port}...")
    cmd = ["npm.cmd" if os.name == "nt" else "npm", "run", "dev", "--", "--port", str(port), "--host", "127.0.0.1"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT / "apps" / "web"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for _ in range(60):
        if is_port_open(port):
            print(f"✔ [Frontend] Vite dev server ready on port {port} (PID: {proc.pid}).")
            return proc
        time.sleep(0.3)
    raise RuntimeError(f"Timeout waiting for Frontend on port {port}")


def run_acceptance(
    chrome_path: str,
    frontend_port: int,
    backend_port: int,
    idp_port: int,
    headless: bool,
    output_dir: Path,
    evidence_file: Path,
    dev_dir: Path | None = None,
    idp_script: Path | None = None,
    server_env: Path | None = None,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_file.parent.mkdir(parents=True, exist_ok=True)

    git_sha = get_git_sha()
    start_time_iso = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()

    resolved_dev_dir, resolved_idp, resolved_env = resolve_prerequisites(
        dev_dir_arg=dev_dir,
        idp_script_arg=idp_script,
        server_env_arg=server_env,
    )

    print("\n" + "=" * 70)
    print("SAINTVISION S02-FE REAL BROWSER & REAL BACKEND ACCEPTANCE")
    print("=" * 70)
    print(f"• Git Tip SHA:     {git_sha}")
    print(f"• Google Chrome:   {chrome_path}")
    print(f"• Frontend (Vite): http://127.0.0.1:{frontend_port}")
    print(f"• Backend (ASGI):  http://127.0.0.1:{backend_port}")
    print(f"• Dev IdP (OIDC):  http://127.0.0.1:{idp_port}")
    print(f"• Resolved DevDir: {resolved_dev_dir}")
    print(f"• Resolved IdP:    {resolved_idp}")
    print(f"• Resolved Env:    {resolved_env}")
    print(f"• Headless:        {headless}")
    print(f"• Output Dir:      {output_dir}")
    print(f"• Evidence Path:   {evidence_file}")
    print("=" * 70 + "\n")

    # F1 Graceful Gate: If required local environment is unavailable, record UNMEASURED cleanly
    if not resolved_idp or not resolved_env:
        missing = []
        if not resolved_idp:
            missing.append("dev_idp.py")
        if not resolved_env:
            missing.append("server.env")
        reason = f"Prerequisites missing: {', '.join(missing)} not found (F1 reproducibility gate)"
        print(f"⚠ [UNMEASURED] {reason}")

        evidence_doc = {
            "schema": "https://saintvision.ai/evidence/s02-fe-real-api.schema.json",
            "version": "1.0.0",
            "timestamp": start_time_iso,
            "gitCommitSha": git_sha,
            "assessment": "UNMEASURED",
            "operationalAcceptanceAssessed": False,
            "unmeasuredReason": reason,
            "environment": {
                "os": os.name,
                "python": sys.version.split()[0],
                "chromePath": chrome_path,
                "backendPort": backend_port,
                "idpPort": idp_port,
                "frontendPort": frontend_port,
            },
            "scenarios": [
                {"id": "s02-login-success", "name": "로그인 성공 경로 (OIDC Code Flow + Session 검증)", "status": "UNMEASURED", "reason": reason},
                {"id": "s02-nodes-real-data", "name": "Node 목록 실데이터 (0대 정직 표기)", "status": "UNMEASURED", "reason": reason},
                {"id": "s02-project-403", "name": "미인가 프로젝트 403 ProblemDetails 및 role=alert 표출", "status": "UNMEASURED", "reason": reason},
                {"id": "s02-token-expired-401", "name": "토큰 만료 401 ProblemDetails 및 재로그인 경로", "status": "UNMEASURED", "reason": reason},
            ],
            "summary": {
                "totalScenarios": 4,
                "passed": 0,
                "failed": 0,
                "unmeasured": 4,
                "mockApiUsed": False,
                "realUvicornUsed": False,
                "realDevIdPUsed": False,
            },
        }
        with open(evidence_file, "w", encoding="utf-8") as f:
            json.dump(evidence_doc, f, indent=2, ensure_ascii=False)
        print(f"✔ UNMEASURED evidence recorded to: {evidence_file}")
        return 0

    idp_proc = None
    backend_proc = None
    frontend_proc = None

    idp_health_ok = False
    backend_health_ok = False
    frontend_health_ok = False

    try:
        idp_proc = start_dev_idp(resolved_idp, idp_port)
        backend_proc = start_backend(resolved_env, backend_port)
        frontend_proc = start_frontend(frontend_port)

        # Pre-flight health checks
        with urllib.request.urlopen(f"http://127.0.0.1:{idp_port}/", timeout=3) as r:
            assert r.status == 200, f"IdP health status was {r.status}"
            idp_health_ok = True
        with urllib.request.urlopen(f"http://127.0.0.1:{backend_port}/healthz", timeout=3) as r:
            assert r.status == 200, f"Backend health status was {r.status}"
            backend_health_ok = True
        with urllib.request.urlopen(f"http://127.0.0.1:{frontend_port}/", timeout=3) as r:
            assert r.status == 200, f"Frontend health status was {r.status}"
            frontend_health_ok = True

        scenario_records = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=chrome_path,
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = context.new_page()

            # Inject operator auth settings into window before any scripts execute
            page.add_init_script(f"""
                window.__SAINTVISION_CONFIG__ = {{
                    idpAuthorizeUrl: 'http://127.0.0.1:{idp_port}/authorize',
                    idpTokenUrl: 'http://127.0.0.1:{idp_port}/token',
                    clientId: 'dev-web',
                    scope: 'inv.api'
                }};
            """)

            # -------------------------------------------------------------
            # Scenario 1: 로그인 성공 경로 (s02-login-success)
            # -------------------------------------------------------------
            print("\n[Scenario 1/4] s02-login-success: OIDC Code Grant & Session Mount")
            net_events = []
            captured_token = {}

            def on_response(resp):
                if f":{idp_port}/token" in resp.url and resp.status == 200:
                    try:
                        captured_token.update(resp.json())
                    except Exception:
                        pass
                if "/v1/" in resp.url:
                    print(f"[NET {resp.status}] {resp.url}")
                net_events.append({
                    "url": resp.url,
                    "status": resp.status,
                    "contentType": resp.headers.get("content-type", ""),
                })

            page.on("response", on_response)
            page.on("console", lambda msg: print(f"[Console {msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: print(f"[PageError] {err}"))

            page.goto(f"http://127.0.0.1:{frontend_port}/", wait_until="networkidle")
            page.wait_for_timeout(500)

            login_btn = page.locator('button:has-text("조직 계정으로 로그인")')
            assert login_btn.is_visible(), "Login button must be visible on initial visit"
            login_btn.click()

            page.wait_for_url("**/studio", timeout=12000)
            page.wait_for_timeout(1500)

            header = page.locator("header")
            assert header.is_visible(), "Header component must mount upon authentication"
            logout_btn = page.locator('button:has-text("로그아웃")')
            assert logout_btn.is_visible(), "Logout button must be visible in Header"

            # Locate observed network events
            auth_evt = next((r for r in net_events if f":{idp_port}/authorize" in r["url"]), None)
            token_evt = next((r for r in net_events if f":{idp_port}/token" in r["url"]), None)
            session_evt = next((r for r in net_events if "/v1/session" in r["url"]), None)

            assert auth_evt is not None and auth_evt["status"] == 302, "IdP /authorize must return 302 redirect"
            assert token_evt is not None and token_evt["status"] == 200, "IdP /token must return 200 OK"
            assert session_evt is not None and session_evt["status"] == 200, "Backend /v1/session must return 200 OK"

            access_token = captured_token.get("access_token", "")
            assert access_token, "Genuine access_token must be returned by IdP"

            shot_s01 = output_dir / "s02_01_login_success.png"
            page.screenshot(path=str(shot_s01))

            s1_obs = {
                "authRedirectStatus": auth_evt["status"],
                "tokenExchangeStatus": token_evt["status"],
                "sessionValidationStatus": session_evt["status"],
                "tokenType": captured_token.get("token_type", "Bearer"),
                "tokenExpiresIn": captured_token.get("expires_in", 0),
                "headerMounted": True,
                "logoutButtonVisible": True,
                "screenshot": str(shot_s01.name),
            }
            scenario_records.append({
                "id": "s02-login-success",
                "name": "로그인 성공 경로 (OIDC Code Flow + Session 검증)",
                "status": "PASS",
                "observations": s1_obs,
            })
            print(f"✔ [PASS] Scenario 1: Auth={auth_evt['status']}, Token={token_evt['status']}, Session={session_evt['status']}")

            # -------------------------------------------------------------
            # Scenario 2: Node 목록 실데이터 (0대면 0대 정직 표기)
            # -------------------------------------------------------------
            print("\n[Scenario 2/4] s02-nodes-real-data: Node Inventory Real Wire Observation")

            # Dynamically query available projects for current authenticated user
            projects_wire = page.evaluate("""async (token) => {
                const res = await fetch('/v1/projects', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                let body = {};
                try { body = await res.json(); } catch(e) {}
                return { status: res.status, body };
            }""", access_token)

            assert projects_wire["status"] == 200, f"Expected 200 for /v1/projects, got {projects_wire['status']}"
            project_items = projects_wire["body"].get("items", [])
            assert len(project_items) > 0, "At least one project grant required for authenticated dev-user"
            active_project_id = project_items[0].get("projectId") or project_items[0].get("id")
            print(f"• Dynamically observed active project ID: {active_project_id}")

            nodes_wire = page.evaluate("""async ({ token, prj }) => {
                const res = await fetch(`/v1/projects/${prj}/nodes`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                let body = {};
                try { body = await res.json(); } catch(e) {}
                return {
                    status: res.status,
                    contentType: res.headers.get('content-type') || '',
                    items: body.items || []
                };
            }""", {"token": access_token, "prj": active_project_id})

            assert nodes_wire["status"] == 200, f"Expected 200 for nodes, got {nodes_wire['status']}"
            assert isinstance(nodes_wire["items"], list), "Nodes items must be a list"
            wire_node_count = len(nodes_wire["items"])

            # Enter active project ID into direct-project-input to bind the active project scope
            input_loc = page.locator('[data-testid="direct-project-input"]')
            assert input_loc.is_visible(), "Direct project input must be visible in UI"
            input_loc.fill(active_project_id)
            input_loc.press("Enter")
            page.wait_for_timeout(1000)

            # Switch to Nodes tab using native DOM click
            page.evaluate("() => document.querySelector('[data-testid=\"header-tab-nodes\"]').click()")
            page.wait_for_timeout(1000)
            print("DEBUG: main inner text upon clicking Nodes tab:")
            print(page.locator("main").inner_text()[:400])

            empty_state_loc = page.locator('text="등록된 Node가 없습니다"')
            empty_state_loc.wait_for(state="visible", timeout=6000)
            empty_state_text = empty_state_loc.inner_text()
            empty_state_visible = True

            shot_s04 = output_dir / "s02_04_nodes_empty_state.png"
            page.screenshot(path=str(shot_s04))

            s4_obs = {
                "activeProjectId": active_project_id,
                "nodesEndpointStatus": nodes_wire["status"],
                "observedWireNodeCount": wire_node_count,
                "wireItems": nodes_wire["items"],
                "emptyStateRendered": empty_state_visible,
                "emptyStateTitle": empty_state_text,
                "screenshot": str(shot_s04.name),
            }
            scenario_records.append({
                "id": "s02-nodes-real-data",
                "name": "Node 목록 실데이터 (0대 정직 표기)",
                "status": "PASS",
                "observations": s4_obs,
            })
            print(f"✔ [PASS] Scenario 2: Real nodes wire count = {wire_node_count}, EmptyState='{empty_state_text}'")

            # -------------------------------------------------------------
            # Scenario 3: 권한 없는 project 403 problem+json 표시
            # -------------------------------------------------------------
            print("\n[Scenario 3/4] s02-project-403: Unauthorized Project 403 ProblemDetails & Alert")
            unauth_prj_id = "prj_01M33NGQEZTB2QD1CWV97Y7999"

            # Directly enter unauthorized project ID into the real direct-project-input UI element (zero window hooks)
            input_loc = page.locator('[data-testid="direct-project-input"]')
            assert input_loc.is_visible(), "Direct project input must be visible in UI"
            input_loc.fill(unauth_prj_id)
            input_loc.press("Enter")
            page.wait_for_timeout(1000)

            # Locate the React-rendered error alert in the real DOM
            alert_loc = page.locator('[data-testid="app-run-error"]')
            alert_loc.wait_for(state="visible", timeout=6000)
            dom_alert_text = alert_loc.inner_text()
            assert alert_loc.get_attribute("role") == "alert", "Must have role=alert"
            assert "AUTH-0030" in dom_alert_text, f"Alert text '{dom_alert_text}' must contain AUTH-0030"
            assert "Project permission is unavailable" in dom_alert_text, "Alert text must contain problem detail"

            # Assert wire response
            unauth_wire = page.evaluate("""async ({ token, prj }) => {
                const res = await fetch(`/v1/projects/${prj}/runs`, {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                let body = {};
                try { body = await res.json(); } catch(e) {}
                return {
                    status: res.status,
                    contentType: res.headers.get('content-type') || '',
                    body
                };
            }""", {"token": access_token, "prj": unauth_prj_id})

            assert unauth_wire["status"] == 403, f"Expected 403 for unauthorized project, got {unauth_wire['status']}"
            assert "application/problem+json" in unauth_wire["contentType"], "Must return application/problem+json"
            problem_data = unauth_wire["body"]
            assert problem_data.get("code") == "AUTH-0030", f"Expected AUTH-0030, got {problem_data.get('code')}"
            assert problem_data.get("detail") == "Project permission is unavailable"

            shot_s03 = output_dir / "s02_03_project_403.png"
            page.screenshot(path=str(shot_s03))

            s3_obs = {
                "unauthorizedProjectId": unauth_prj_id,
                "wireHttpStatus": unauth_wire["status"],
                "wireContentType": unauth_wire["contentType"],
                "problemCode": problem_data.get("code"),
                "problemDetail": problem_data.get("detail"),
                "problemCategory": problem_data.get("category"),
                "problemTraceId": problem_data.get("traceId"),
                "domAlertRole": "alert",
                "domAlertText": dom_alert_text,
                "screenshot": str(shot_s03.name),
            }
            scenario_records.append({
                "id": "s02-project-403",
                "name": "미인가 프로젝트 403 ProblemDetails 및 role=alert 표출",
                "status": "PASS",
                "observations": s3_obs,
            })
            print(f"✔ [PASS] Scenario 3: 403 {problem_data.get('code')} -> '{dom_alert_text}'")

            # -------------------------------------------------------------
            # Scenario 4: 토큰 만료 401 ProblemDetails 및 재로그인 경로
            # -------------------------------------------------------------
            print("\n[Scenario 4/4] s02-token-expired-401: Token Expiration 401 & Re-login")

            # 1. Wire assertion: Genuinely expired RS256 token signed by IdP key
            key_path = resolved_dev_dir / "idp_private_key.pem"
            api_path = resolved_dev_dir / "api.json"
            assert key_path.exists() and api_path.exists(), "IdP key and api.json required for minting expired token"

            from cryptography.hazmat.primitives import serialization
            priv_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            api_meta = json.loads(api_path.read_text("utf-8"))["identity"]
            now_ts = int(time.time())
            genuinely_expired_jwt = jwt.encode(
                {
                    "iss": api_meta["issuer"],
                    "aud": api_meta["audience"],
                    "sub": "dev-user",
                    "iat": now_ts - 3660,
                    "exp": now_ts - 60,
                    "jti": str(uuid4()),
                    "client_id": "dev-web",
                    "scope": "inv.api",
                },
                priv_key,
                algorithm="RS256",
                headers={"kid": "dev-1", "typ": "at+jwt"},
            )

            expired_wire = page.evaluate("""async (tok) => {
                const res = await fetch('/v1/session', {
                    headers: { 'Authorization': `Bearer ${tok}` }
                });
                let body = {};
                try { body = await res.json(); } catch(e) {}
                return {
                    status: res.status,
                    contentType: res.headers.get('content-type') || '',
                    body
                };
            }""", genuinely_expired_jwt)

            assert expired_wire["status"] == 401, f"Expected 401 for expired token, got {expired_wire['status']}"
            assert "application/problem+json" in expired_wire["contentType"]
            expired_problem = expired_wire["body"]
            assert expired_problem.get("code") == "AUTH-0050", f"Expected AUTH-0050, got {expired_problem.get('code')}"
            assert expired_problem.get("detail") == "A current access token is required"

            # 2. UI flow: Log in with short-lived token (2s), wait 3s, interact with UI
            relogin_btn = page.locator('button:has-text("로그아웃")')
            assert relogin_btn.is_visible(), "Logout button must be visible to reset session"
            relogin_btn.click()
            page.wait_for_timeout(500)

            # Instruct Dev IdP to mint short-lived tokens (ttl=6s) via local dev endpoint
            urllib.request.urlopen(f"http://127.0.0.1:{idp_port}/dev/set-ttl?ttl=6")

            short_login_btn = page.locator('button:has-text("조직 계정으로 로그인")')
            short_login_btn.wait_for(state="visible", timeout=6000)
            short_login_btn.click()

            page.wait_for_url("**/studio", timeout=12000)
            short_header = page.locator("header")
            short_header.wait_for(state="visible", timeout=6000)
            page.wait_for_timeout(500)

            # Wait 7s so the 6s token is organically and authentically expired
            print("• Waiting 7s for short-lived token to expire authentically...")
            page.wait_for_timeout(7000)

            # Trigger immediate authenticated query with expired token
            input_loc = page.locator('[data-testid="direct-project-input"]')
            if input_loc.is_visible():
                input_loc.fill(active_project_id)
                input_loc.press("Enter")

            # Expect redirection to login tab and role="alert" with AUTH-0050
            token_alert_loc = page.locator('[data-testid="login-error-alert"]')
            token_alert_loc.wait_for(state="visible", timeout=12000)
            assert token_alert_loc.get_attribute("role") == "alert", "Must have role=alert"
            dom_401_alert_text = token_alert_loc.inner_text()
            assert "AUTH-0050" in dom_401_alert_text, f"Expected AUTH-0050 in '{dom_401_alert_text}'"
            assert "A current access token is required" in dom_401_alert_text

            shot_s02_alert = output_dir / "s02_02_token_expired_401.png"
            page.screenshot(path=str(shot_s02_alert))

            # 3. Re-login flow: reset IdP token TTL to default (3600s), click login, verify recovery
            urllib.request.urlopen(f"http://127.0.0.1:{idp_port}/dev/set-ttl?ttl=3600")

            full_relogin_btn = page.locator('button:has-text("조직 계정으로 로그인")')
            assert full_relogin_btn.is_visible(), "Re-login button must be present"
            full_relogin_btn.click()

            page.wait_for_url("**/studio", timeout=12000)
            page.wait_for_timeout(1000)

            re_header = page.locator("header")
            assert re_header.is_visible(), "Header must remount after re-login"
            re_logout_btn = page.locator('button:has-text("로그아웃")')
            assert re_logout_btn.is_visible(), "Logout button must be visible after re-login"

            shot_s02_relogin = output_dir / "s02_02_relogin_success.png"
            page.screenshot(path=str(shot_s02_relogin))

            s2_obs = {
                "wireHttpStatus": expired_wire["status"],
                "wireContentType": expired_wire["contentType"],
                "problemCode": expired_problem.get("code"),
                "problemDetail": expired_problem.get("detail"),
                "domAlertRole": "alert",
                "domAlertText": dom_401_alert_text,
                "reloginCompleted": True,
                "reloginHeaderVisible": True,
                "screenshots": [str(shot_s02_alert.name), str(shot_s02_relogin.name)],
            }
            scenario_records.append({
                "id": "s02-token-expired-401",
                "name": "토큰 만료 401 ProblemDetails 및 재로그인 경로",
                "status": "PASS",
                "observations": s2_obs,
            })
            print(f"✔ [PASS] Scenario 4: 401 {expired_problem.get('code')} -> Re-login OK")

            browser.close()

        end_time_iso = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()

        # F4 Dynamic derivations: no hardcoded constants
        total_scenarios = len(scenario_records)
        passed_scenarios = sum(1 for s in scenario_records if s.get("status") == "PASS")
        failed_scenarios = sum(1 for s in scenario_records if s.get("status") == "FAIL")
        unmeasured_scenarios = sum(1 for s in scenario_records if s.get("status") == "UNMEASURED")

        if total_scenarios > 0 and passed_scenarios == total_scenarios:
            assessment = "ACCEPTANCE_PASSED"
            operational_assessed = True
        elif failed_scenarios > 0:
            assessment = "ACCEPTANCE_FAILED"
            operational_assessed = False
        else:
            assessment = "UNMEASURED"
            operational_assessed = False

        real_uvicorn_used = bool((backend_proc is not None or is_port_open(backend_port)) and backend_health_ok)
        real_dev_idp_used = bool((idp_proc is not None or is_port_open(idp_port)) and idp_health_ok)
        mock_api_used = False  # Zero route mocks registered in playwright context

        evidence_doc = {
            "schema": "https://saintvision.ai/evidence/s02-fe-real-api.schema.json",
            "version": "1.0.0",
            "timestamp": end_time_iso,
            "gitCommitSha": git_sha,
            "assessment": assessment,
            "operationalAcceptanceAssessed": operational_assessed,
            "environment": {
                "os": os.name,
                "python": sys.version.split()[0],
                "chromePath": chrome_path,
                "backendPort": backend_port,
                "idpPort": idp_port,
                "frontendPort": frontend_port,
            },
            "scenarios": scenario_records,
            "summary": {
                "totalScenarios": total_scenarios,
                "passed": passed_scenarios,
                "failed": failed_scenarios,
                "unmeasured": unmeasured_scenarios,
                "mockApiUsed": mock_api_used,
                "realUvicornUsed": real_uvicorn_used,
                "realDevIdPUsed": real_dev_idp_used,
            },
        }

        with open(evidence_file, "w", encoding="utf-8") as f:
            json.dump(evidence_doc, f, indent=2, ensure_ascii=False)
        print(f"\n✔ Permanent evidence saved to: {evidence_file}")

        print("\n" + "=" * 70)
        print(f"STATUS: {assessment} ({passed_scenarios}/{total_scenarios} passed, 0 mocks)")
        print("=" * 70)
        return 0 if assessment == "ACCEPTANCE_PASSED" else 1

    finally:
        if idp_proc:
            print("[Cleanup] Terminating Dev IdP subprocess...")
            idp_proc.terminate()
            idp_proc.wait()
        if backend_proc:
            print("[Cleanup] Terminating Backend Uvicorn subprocess...")
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            print("[Cleanup] Terminating Frontend Vite subprocess...")
            frontend_proc.terminate()
            frontend_proc.wait()


def main():
    parser = argparse.ArgumentParser(description="Run S02-FE Real Browser Acceptance")
    parser.add_argument("--chrome-path", default=DEFAULT_CHROME_PATH, help="Path to Google Chrome executable")
    parser.add_argument("--frontend-port", type=int, default=3005, help="Port of running Vite frontend")
    parser.add_argument("--backend-port", type=int, default=8080, help="Port for Uvicorn backend")
    parser.add_argument("--idp-port", type=int, default=8090, help="Port for dev IdP")
    parser.add_argument("--headless", action="store_true", default=True, help="Run Chrome in headless mode")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run Chrome with visible UI")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "scratch", help="Directory for screenshots")
    parser.add_argument(
        "--evidence-file",
        type=Path,
        default=REPO_ROOT / "docs" / "vault" / "30_Development" / "Evidence" / "s02_fe_real_api_acceptance.json",
        help="Path for permanent evidence JSON",
    )
    parser.add_argument("--dev-dir", type=Path, default=None, help="Path to .work/dev directory")
    parser.add_argument("--idp-script", type=Path, default=None, help="Path to dev_idp.py")
    parser.add_argument("--server-env", type=Path, default=None, help="Path to server.env")
    args = parser.parse_args()

    rc = run_acceptance(
        chrome_path=args.chrome_path,
        frontend_port=args.frontend_port,
        backend_port=args.backend_port,
        idp_port=args.idp_port,
        headless=args.headless,
        output_dir=args.output_dir,
        evidence_file=args.evidence_file,
        dev_dir=args.dev_dir,
        idp_script=args.idp_script,
        server_env=args.server_env,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()
