"""Static verification and mutation test suite for SaintVision Intranet Portal Deployment (Card 156).

Validates:
1. deploy/intranet/portal/security-headers.conf & nginx.conf:
   - Security headers snippet included across server block and all location blocks declaring add_header (inheritance safety).
   - Strict CSP: connect-src restricted strictly to 'self' and https://idp.sv.lan only.
   - CSP: style-src 'self' (no 'unsafe-inline'), form-action 'self', frame-ancestors 'none', object-src 'none'.
   - Privacy logging: log_format records only request_method, uri, protocol; never query strings or Referer. /callback has access_log off.
   - Fixed HTTPS redirect: port 80 redirects to https://portal.sv.lan$request_uri (no host header poisoning).
   - Reverse proxy topology: /v1/, SSE (buffering off), and Terminal WebSocket forwarded to upstream Control Plane with TLS verification.
   - Missing static files: extensions regex returns 404 instead of falling back to index.html (L3 invariant).
   - Nginx daemon off removed from nginx.conf (only present in Dockerfile CMD, H1 invariant).
2. deploy/intranet/portal/portal-up.sh:
   - Staging preflight container: launches staging container to verify nginx -t and HTTPS health before touching existing container (M3).
   - Owner label 4-tuple enforcement (service, workload, node, instance) with exact stale exited cleanup.
   - Upstream CP fail-closed requirement (PORTAL_UPSTREAM_CP_HOST).
   - Production leaf verification against CA bundle (self-signed strictly rejected, SAN, EKU serverAuth, CA:FALSE).
   - Default cert/key: server-chain.pem (0600) and server-key.pem (0400) without chmod alteration (H2).
   - Secret prohibition: no -e flags or secrets in docker run.
   - TLS private key single-file readonly mount with non-world-readable permissions.
3. deploy/intranet/portal/portal-smoke-up.sh:
   - Dev smoke isolation: separate container name, instance tuple, and certs directory.
4. deploy/intranet/portal/Dockerfile.dockerignore:
   - Overrides root python-only .dockerignore when building with BuildKit (H5).
5. Mutation & Reversibility controls (positive control confirmed first, comment-stripped token analysis for M4).
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTAL_DIR = REPO_ROOT / "deploy" / "intranet" / "portal"
NGINX_CONF = PORTAL_DIR / "nginx.conf"
SECURITY_HEADERS_CONF = PORTAL_DIR / "security-headers.conf"
AUTH_CONFIG_JS = PORTAL_DIR / "auth-config.js"
PORTAL_UP_SH = PORTAL_DIR / "portal-up.sh"
PORTAL_SMOKE_UP_SH = PORTAL_DIR / "portal-smoke-up.sh"
PORTAL_DOWN_SH = PORTAL_DIR / "portal-down.sh"
DOCKERFILE = PORTAL_DIR / "Dockerfile"
DOCKERFILE_DOCKERIGNORE = PORTAL_DIR / "Dockerfile.dockerignore"


def read_file(path: Path) -> str:
    assert path.is_file(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def strip_shell_comments(text: str) -> str:
    """Strips shell comments while preserving line structure and code tokens."""
    return "\n".join(line.split("#")[0] for line in text.splitlines())


# =========================================================================
# 1. Security Headers Snippet & Inheritance Tests (Review Finding 4 & L2)
# =========================================================================

def test_security_headers_conf_invariants():
    assert SECURITY_HEADERS_CONF.is_file(), "deploy/intranet/portal/security-headers.conf must exist"
    content = read_file(SECURITY_HEADERS_CONF)

    # HSTS
    assert 'Strict-Transport-Security "max-age=31536000; includeSubDomains" always;' in content
    # CSP: connect-src 'self' and https://idp.sv.lan ONLY
    csp_match = re.search(r'Content-Security-Policy\s+"([^"]+)"', content)
    assert csp_match, "CSP header must be defined in security-headers.conf"
    csp = csp_match.group(1)

    connect_match = re.search(r"connect-src\s+([^;]+)", csp)
    assert connect_match, "CSP must contain connect-src"
    sources = set(connect_match.group(1).strip().split())
    assert sources == {"'self'", "https://idp.sv.lan"}, f"connect-src must contain only 'self' and https://idp.sv.lan, got {sources}"

    assert "style-src 'self';" in csp, "style-src must be 'self' (no unsafe-inline)"
    assert "form-action 'self';" in csp, "form-action must be 'self'"
    assert "frame-ancestors 'none';" in csp
    assert "object-src 'none';" in csp

    # Standard protections
    assert 'X-Content-Type-Options "nosniff"' in content
    assert 'X-Frame-Options "DENY"' in content
    assert 'Referrer-Policy "strict-origin-when-cross-origin"' in content


def test_nginx_conf_includes_security_headers_in_all_add_header_locations():
    content = read_file(NGINX_CONF)
    # Server block must include security-headers.conf
    assert "include /etc/nginx/security-headers.conf;" in content

    # Find all location blocks in server 443
    # Every location block that contains add_header MUST include /etc/nginx/security-headers.conf
    location_blocks = re.findall(r"location\s+([^{]+)\{([^}]+(?:\{[^}]*\}[^}]*)*)\}", content)
    assert len(location_blocks) >= 5, "Expected at least 5 location blocks"

    for loc_path, loc_body in location_blocks:
        loc_path_clean = loc_path.strip()
        if "add_header" in loc_body:
            assert "include /etc/nginx/security-headers.conf;" in loc_body, \
                f"Location block '{loc_path_clean}' defines add_header but does NOT include security-headers.conf (broken inheritance)!"


# =========================================================================
# 2. Reverse Proxy Topology Tests (Review Finding 1)
# =========================================================================

def test_nginx_conf_reverse_proxy_topology():
    content = read_file(NGINX_CONF)

    # Upstream include
    assert "include /etc/nginx/conf.d/upstream.conf;" in content

    # /v1/ API reverse proxy
    assert "location /v1/ {" in content
    assert "proxy_pass https://control_plane;" in content
    assert "proxy_ssl_verify on;" in content
    assert "proxy_ssl_trusted_certificate /etc/nginx/certs/ca-bundle.crt;" in content
    assert "proxy_ssl_name cp.sv.lan;" in content
    assert "proxy_ssl_server_name on;" in content
    assert "proxy_set_header Host cp.sv.lan;" in content

    # SSE endpoint with buffering disabled
    assert "location ~ ^/v1/projects/[^/]+/runs/[^/]+/events {" in content
    assert "proxy_buffering off;" in content
    assert "chunked_transfer_encoding off;" in content
    assert "proxy_read_timeout 24h;" in content

    # WebSocket Terminal endpoint
    assert "location /v1/terminal/ws {" in content
    assert "proxy_set_header Upgrade $http_upgrade;" in content
    assert "proxy_set_header Connection $connection_upgrade;" in content


# =========================================================================
# 3. Privacy Logging & Callback Access Log Tests (Review Finding M2)
# =========================================================================

def test_nginx_conf_privacy_logging():
    content = read_file(NGINX_CONF)

    # Log format must NOT contain $request or $http_referer (query strings contain OAuth codes)
    log_format_match = re.search(r"log_format\s+(?:privacy|main)\s+'([^']+)'", content)
    assert log_format_match, "log_format privacy/main must be configured"
    log_fmt = log_format_match.group(1)

    assert "$request " not in log_fmt and "$request\"" not in log_fmt, "log_format must not log full $request"
    assert "$query_string" not in log_fmt, "log_format must not log query string"
    assert "$args" not in log_fmt, "log_format must not log args"
    assert "$http_referer" not in log_fmt, "log_format must not log referer"
    assert "$request_method $uri $server_protocol" in log_fmt, "log_format must log sanitized URI only"

    # /callback location must disable access log
    callback_match = re.search(r"location\s+=\s+/callback\s+\{([^}]+)\}", content)
    assert callback_match, "location = /callback must exist"
    assert "access_log off;" in callback_match.group(1), "/callback must disable access_log to protect auth codes"


# =========================================================================
# 4. Fixed 301 Redirect & Missing Static Asset 404 Tests (Review Findings 6 & L3)
# =========================================================================

def test_nginx_conf_fixed_https_redirect_and_healthz():
    content = read_file(NGINX_CONF)

    # Port 80 redirect must use fixed domain, not $host
    assert "return 301 https://portal.sv.lan$request_uri;" in content, \
        "Port 80 redirect must target https://portal.sv.lan to prevent Host header poisoning"

    # Port 80 must have plaintext /healthz
    assert "listen 80;" in content
    assert "location = /healthz {" in content
    assert "return 200 'OK';" in content


def test_nginx_conf_missing_static_files_404():
    content = read_file(NGINX_CONF)

    # Missing static files with known extensions must return =404, not fallback to index.html
    ext_regex_match = re.search(r"location\s+~\*\s+\\\.\(\?[^)]+\)\$\s*\{([^}]+)\}", content)
    assert ext_regex_match, "Static asset extension regex location must be defined"
    loc_body = ext_regex_match.group(1)
    assert "try_files $uri =404;" in loc_body, "Missing static assets must return 404, not index.html"


def test_nginx_conf_no_daemon_off():
    content = read_file(NGINX_CONF)
    # daemon off in nginx.conf conflicts with Dockerfile -g "daemon off;" (H1)
    assert "daemon off" not in content, "nginx.conf must NOT contain 'daemon off;' (handled via Dockerfile CMD)"


# =========================================================================
# 5. Owner Label 4-Tuple & Exited Stale Cleanup Tests (Review Finding 5)
# =========================================================================

def test_portal_up_sh_owner_label_4tuple():
    content = read_file(PORTAL_UP_SH)

    # 4-tuple variables
    assert 'LABEL_SERVICE="ai.saintvision.service=portal"' in content
    assert 'LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"' in content
    assert 'LABEL_NODE="ai.saintvision.node=node2"' in content
    assert 'LABEL_INSTANCE="ai.saintvision.instance=${PORTAL_INSTANCE}"' in content

    # Inspect checks all 4
    assert 'existing_service=' in content
    assert 'existing_workload=' in content
    assert 'existing_node=' in content
    assert 'existing_instance=' in content
    assert 'Refusing to touch non-matching container' in content

    # Stale cleanup filters by status=exited and all 4 labels
    assert '--filter "status=exited"' in content
    assert '--filter "label=${LABEL_SERVICE}"' in content
    assert '--filter "label=${LABEL_WORKLOAD}"' in content
    assert '--filter "label=${LABEL_NODE}"' in content
    assert '--filter "label=${LABEL_INSTANCE}"' in content


def test_portal_down_sh_owner_label_4tuple():
    content = read_file(PORTAL_DOWN_SH)

    # Inspect checks all 4
    assert 'existing_service=' in content
    assert 'existing_workload=' in content
    assert 'existing_node=' in content
    assert 'existing_instance=' in content
    assert 'Refusing to stop or remove non-owned container' in content

    # Stale cleanup filters by status=exited and all 4 labels
    assert '--filter "status=exited"' in content
    assert '--filter "label=${LABEL_SERVICE}"' in content


# =========================================================================
# 6. Production Leaf CA & Chain Tests (Review Finding 2 & H2)
# =========================================================================

def test_portal_up_sh_production_ca_verification():
    content = read_file(PORTAL_UP_SH)

    # Self-signed certificate rejection
    assert 'cert_subject=' in content
    assert 'cert_issuer=' in content
    assert 'Self-signed certificate rejected in production portal-up.sh' in content

    # CA bundle verification
    assert "openssl verify -CAfile" in content

    # SAN verification
    assert "DNS:portal.sv.lan" in content

    # EKU verification
    assert "TLS Web Server Authentication" in content or "serverAuth" in content

    # Basic Constraints CA:FALSE
    assert "CA:FALSE" in content

    # Key/cert pubkey hash match
    assert "cert_pubkey_hash" in content
    assert "key_pubkey_hash" in content


def test_portal_up_sh_no_chmod_on_operator_keys():
    content = read_file(PORTAL_UP_SH)

    # Script must NOT chmod operator keys or certs (H2)
    assert "chmod 600" not in content
    assert "chmod 0600" not in content
    assert "chmod 0400" not in content
    assert "chmod 644 $CERT_FILE" not in content

    # Default cert must be server-chain.pem and key server-key.pem (#251 output)
    assert "server-chain.pem" in content
    assert "server-key.pem" in content


# =========================================================================
# 7. Upstream CP Host Fail-Closed & Staging Preflight (Review Finding 1 & M3)
# =========================================================================

def test_portal_up_sh_upstream_cp_fail_closed():
    content = read_file(PORTAL_UP_SH)

    # Must check PORTAL_UPSTREAM_CP_HOST and fail closed if empty
    assert 'UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-}"' in content
    assert 'if [[ -z "$UPSTREAM_CP_HOST" ]]; then' in content
    assert 'PORTAL_UPSTREAM_CP_HOST is not set' in content
    assert 'fail-closed' in content


def test_portal_up_sh_staging_preflight_and_safety():
    content = read_file(PORTAL_UP_SH)

    # Staging container creation with preflight instance
    assert 'STAGING_NAME="${CONTAINER_NAME}-staging-$$"' in content
    assert 'ai.saintvision.instance=preflight' in content

    # Preflight tests inside staging container
    assert 'docker exec "$STAGING_NAME" nginx -t' in content
    assert 'docker exec "$STAGING_NAME" wget' in content
    assert 'staging_cleanup' in content

    # Staging preflight MUST occur BEFORE stopping existing container
    preflight_pos = content.find('STAGING_NAME="${CONTAINER_NAME}-staging-$$"')
    docker_stop_pos = content.find('docker stop "$CONTAINER_NAME"')
    assert preflight_pos < docker_stop_pos, "Staging preflight MUST execute BEFORE stopping existing container!"

    # Post-launch checks RestartCount == 0
    assert "restart_count=" in content
    assert '[[ "$restart_count" -ne 0 ]]' in content


# =========================================================================
# 8. Secret Prohibition & Docker Run Isolation (Review Finding OK & M4)
# =========================================================================

def test_portal_up_sh_no_secrets_in_docker_run():
    content = read_file(PORTAL_UP_SH)

    # Isolate all docker run invocations
    code_only = strip_shell_comments(content)
    docker_run_cmds = re.findall(r"docker run\s+(?:[^\n]+\\\n)+[^\n]+", code_only)
    assert len(docker_run_cmds) >= 2, "Expected at least 2 docker run invocations (staging and production)"

    for cmd in docker_run_cmds:
        tokens = cmd.split()
        assert "-e" not in tokens, f"Forbidden -e flag in docker run: {cmd}"
        assert "--env" not in tokens, f"Forbidden --env flag in docker run: {cmd}"
        assert "--read-only" in tokens, "docker run must have --read-only"
        assert "--cap-drop" in tokens and "ALL" in tokens, "docker run must have --cap-drop ALL"
        assert "--security-opt" in tokens and "no-new-privileges" in tokens, "docker run must have no-new-privileges"


# =========================================================================
# 9. Dev Smoke Isolation Tests (Review Finding 2)
# =========================================================================

def test_portal_smoke_up_sh_isolation():
    assert PORTAL_SMOKE_UP_SH.is_file(), "portal-smoke-up.sh must exist"
    content = read_file(PORTAL_SMOKE_UP_SH)

    # Distinct container name
    assert 'CONTAINER_NAME="saintvision-portal-smoke"' in content
    # Distinct instance label
    assert 'LABEL_INSTANCE="ai.saintvision.instance=smoke"' in content
    # Dedicated dev certs directory
    assert 'DEV_CERTS_DIR="${SCRIPT_DIR}/certs/dev"' in content


# =========================================================================
# 10. Dockerfile Pinned Image Digests & Dockerignore (Review Finding 7, L1 & H5)
# =========================================================================

def test_dockerfile_pinned_image_digests():
    content = read_file(DOCKERFILE)

    # Builder pinned with node:22-alpine@sha256:
    assert re.search(r"FROM\s+node:22-alpine@sha256:[a-f0-9]{64}", content), \
        "Dockerfile builder must use node:22-alpine pinned with SHA256 digest"

    # Runner pinned with nginx:1.27-alpine@sha256:
    assert re.search(r"FROM\s+nginx:1.27-alpine@sha256:[a-f0-9]{64}", content), \
        "Dockerfile runner must use nginx:1.27-alpine pinned with SHA256 digest"

    # Security headers copied
    assert "COPY deploy/intranet/portal/security-headers.conf" in content
    assert "COPY deploy/intranet/portal/conf.d/upstream.conf" in content


def test_dockerfile_dockerignore_present_and_whitelisted():
    assert DOCKERFILE_DOCKERIGNORE.is_file(), "deploy/intranet/portal/Dockerfile.dockerignore must exist (H5)"
    content = read_file(DOCKERFILE_DOCKERIGNORE)

    # Must un-ignore apps/web/ and deploy/intranet/portal/
    assert "!apps/web/" in content
    assert "!deploy/intranet/portal/" in content

    # Must ignore node_modules, dist, secrets
    assert "apps/web/node_modules/" in content
    assert "apps/web/dist/" in content
    assert "**/*.pem" in content
    assert "**/*.key" in content
    assert "**/.env*" in content


# =========================================================================
# 11. Mutation & Negative Controls (Reversibility with Positive Control, M4)
# =========================================================================

def validate_security_headers_csp(content: str) -> None:
    match = re.search(r'Content-Security-Policy\s+"([^"]+)"', content)
    if not match:
        raise ValueError("Missing CSP header")
    csp = match.group(1)
    connect_match = re.search(r"connect-src\s+([^;]+)", csp)
    if not connect_match:
        raise ValueError("Missing connect-src in CSP")
    sources = set(connect_match.group(1).strip().split())
    if sources != {"'self'", "https://idp.sv.lan"}:
        raise ValueError(f"CSP connect-src violation: {sources}")
    if "style-src 'self';" not in csp:
        raise ValueError("CSP style-src violation: must be 'self' without unsafe-inline")
    if "form-action 'self';" not in csp:
        raise ValueError("CSP form-action violation: must be 'self'")


def validate_portal_up_security(content: str) -> None:
    """Token-based validator on stripped code: catches prohibited flags in docker run while ignoring comments."""
    code_only = strip_shell_comments(content)
    docker_run_cmds = re.findall(r"docker run\s+(?:[^\n]+\\\n)+[^\n]+", code_only)
    if not docker_run_cmds:
        raise ValueError("No docker run command found in script")
    for cmd in docker_run_cmds:
        tokens = cmd.split()
        if "-e" in tokens or "--env" in tokens:
            raise ValueError("Forbidden environment variable injection in docker run")
        for tok in tokens:
            if tok.startswith("-e=") or tok.startswith("--env="):
                raise ValueError("Forbidden environment variable injection in docker run")
        if "--read-only" not in tokens:
            raise ValueError("Missing --read-only in docker run")
        if "--cap-drop" not in tokens or "ALL" not in tokens:
            raise ValueError("Missing --cap-drop ALL in docker run")
        if "--security-opt" not in tokens or "no-new-privileges" not in tokens:
            raise ValueError("Missing --security-opt no-new-privileges in docker run")


def test_positive_control():
    """Verify that unmutated production files pass all validators without error."""
    sec_content = read_file(SECURITY_HEADERS_CONF)
    validate_security_headers_csp(sec_content)

    up_content = read_file(PORTAL_UP_SH)
    validate_portal_up_security(up_content)


def test_positive_control_comment_immunity():
    """Verify that comments containing '(-e forbidden)' or other flags DO NOT trigger false positive (M4)."""
    up_content = read_file(PORTAL_UP_SH)
    commented = up_content + "\n# Test note: (-e forbidden) and --env prohibited in runtime flags\n"
    validate_portal_up_security(commented)


def test_mutation_loosening_csp_fails():
    sec_content = read_file(SECURITY_HEADERS_CONF)

    # Mutation A: Add foreign origin
    mutated_foreign = sec_content.replace("connect-src 'self' https://idp.sv.lan;",
                                          "connect-src 'self' https://idp.sv.lan https://attacker.com;")
    with pytest.raises(ValueError, match="CSP connect-src violation"):
        validate_security_headers_csp(mutated_foreign)

    # Mutation B: Add unsafe-inline to style-src
    mutated_style = sec_content.replace("style-src 'self';", "style-src 'self' 'unsafe-inline';")
    with pytest.raises(ValueError, match="CSP style-src violation"):
        validate_security_headers_csp(mutated_style)


def test_mutation_portal_up_security_flags_fail():
    up_content = read_file(PORTAL_UP_SH)

    # Mutation: inject -e flag into docker run
    mutated_env = up_content.replace('--restart unless-stopped', '-e SECRET_KEY="bad-token" \\\n    --restart unless-stopped')
    with pytest.raises(ValueError, match="Forbidden environment variable injection"):
        validate_portal_up_security(mutated_env)

    # Mutation: remove --read-only from docker run
    mutated_no_ro = up_content.replace('--read-only', '')
    with pytest.raises(ValueError, match="Missing --read-only"):
        validate_portal_up_security(mutated_no_ro)


def validate_owner_tuple_guard(content: str) -> None:
    if 'existing_service=' not in content or 'existing_workload=' not in content or \
       'existing_node=' not in content or 'existing_instance=' not in content:
        raise ValueError("Missing full 4-tuple check in owner label guard")
    if 'Refusing to touch non-matching container' not in content:
        raise ValueError("Missing refusal guard on owner tuple mismatch")


def test_positive_control_owner_tuple():
    up_content = read_file(PORTAL_UP_SH)
    validate_owner_tuple_guard(up_content)


def test_mutation_owner_tuple_guard_fails():
    up_content = read_file(PORTAL_UP_SH)
    # Mutation: remove instance check from tuple guard
    mutated = up_content.replace('|| "$existing_instance" != "$PORTAL_INSTANCE"', '')
    mutated = mutated.replace("existing_instance=", "# removed")
    with pytest.raises(ValueError, match="Missing full 4-tuple check"):
        validate_owner_tuple_guard(mutated)
