"""Static verification and mutation test suite for SaintVision Intranet Portal Deployment (Card 156).

Validates:
1. deploy/intranet/portal/nginx.conf:
   - Non-root user execution (pid /tmp/nginx.pid, temp paths in /tmp).
   - Read-only rootfs compatibility.
   - HTTPS only: Port 80 returns 301 redirect to https://$host$request_uri; Port 443 has ssl enabled.
   - TLS 1.2+ only: ssl_protocols includes TLSv1.2 and TLSv1.3; excludes TLSv1.0, TLSv1.1, SSLv3.
   - HSTS: Strict-Transport-Security present with max-age >= 31536000 and includeSubDomains.
   - CSP: connect-src strictly restricted to https://idp.sv.lan and https://cp.sv.lan only.
   - SPA fallback: try_files $uri $uri/ /index.html.
   - Cache control: no-cache on /auth-config.js and /index.html, immutable on /assets/.
2. deploy/intranet/portal/auth-config.js:
   - Contains issuer https://idp.sv.lan/realms/saintvision and clientId sv-portal.
3. deploy/intranet/portal/portal-up.sh:
   - Owner label enforcement: only replaces containers with ai.saintvision.service=portal.
   - Secret prohibition: rejects secrets and -e/--env in argv; no -e flags in docker run.
   - Single-file read-only bind mount for TLS key and cert.
   - Container hardening: --read-only, --cap-drop ALL, --security-opt no-new-privileges, non-root user.
4. Mutation & Negative Controls (reversibility):
   - Modifying/removing any of the above invariants causes tests to fail immediately.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PORTAL_DIR = REPO_ROOT / "deploy" / "intranet" / "portal"
NGINX_CONF = PORTAL_DIR / "nginx.conf"
AUTH_CONFIG_JS = PORTAL_DIR / "auth-config.js"
PORTAL_UP_SH = PORTAL_DIR / "portal-up.sh"
PORTAL_DOWN_SH = PORTAL_DIR / "portal-down.sh"
DOCKERFILE = PORTAL_DIR / "Dockerfile"


def read_file(path: Path) -> str:
    assert path.is_file(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


# =========================================================================
# 1. Nginx Configuration Static Invariant Tests
# =========================================================================

def test_nginx_conf_exists_and_non_empty():
    assert NGINX_CONF.is_file(), "deploy/intranet/portal/nginx.conf must exist"
    content = read_file(NGINX_CONF)
    assert len(content.strip()) > 100, "nginx.conf is too short"


def test_nginx_conf_non_root_and_readonly_rootfs():
    content = read_file(NGINX_CONF)
    # PID must be in /tmp for non-root read-only rootfs
    assert re.search(r"pid\s+/tmp/nginx\.pid;", content), "PID must point to /tmp/nginx.pid"
    # Temp paths must all be inside /tmp
    assert "client_body_temp_path /tmp/" in content
    assert "proxy_temp_path       /tmp/" in content
    assert "fastcgi_temp_path     /tmp/" in content
    assert "uwsgi_temp_path       /tmp/" in content
    assert "scgi_temp_path        /tmp/" in content


def test_nginx_conf_https_only_and_redirect():
    content = read_file(NGINX_CONF)
    # Port 80 server block
    assert re.search(r"listen\s+80;", content), "Must listen on port 80"
    assert re.search(r"server_name\s+portal\.sv\.lan;", content), "Must set server_name portal.sv.lan"
    assert re.search(r"return\s+301\s+https://\$host\$request_uri;", content), "Port 80 must 301-redirect to HTTPS"

    # Port 443 server block with ssl
    assert re.search(r"listen\s+443\s+ssl;", content), "Must listen on port 443 ssl"
    assert "ssl_certificate /etc/nginx/certs/portal.crt;" in content
    assert "ssl_certificate_key /etc/nginx/certs/portal.key;" in content


def test_nginx_conf_tls_protocols_and_ciphers():
    content = read_file(NGINX_CONF)
    # Protocols must allow TLSv1.2 and TLSv1.3
    match = re.search(r"ssl_protocols\s+([^;]+);", content)
    assert match, "ssl_protocols must be defined"
    protocols = match.group(1).split()
    assert "TLSv1.2" in protocols, "TLSv1.2 must be supported"
    assert "TLSv1.3" in protocols, "TLSv1.3 must be supported"
    # Old protocols must strictly NOT be present
    for bad in ["SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1"]:
        assert bad not in protocols, f"Insecure protocol {bad} must not be present"

    assert "ssl_prefer_server_ciphers on;" in content
    assert "ssl_ciphers" in content
    assert "ECDHE" in content


def test_nginx_conf_hsts_header():
    content = read_file(NGINX_CONF)
    # Strict-Transport-Security
    match = re.search(r'add_header\s+Strict-Transport-Security\s+"([^"]+)"\s+always;', content)
    assert match, "Strict-Transport-Security header must be present with always flag"
    hsts = match.group(1)
    # Validate max-age is at least 1 year (31536000)
    age_match = re.search(r"max-age=(\d+)", hsts)
    assert age_match, "HSTS must specify max-age"
    assert int(age_match.group(1)) >= 31536000, "HSTS max-age must be at least 1 year (31536000 seconds)"
    assert "includeSubDomains" in hsts, "HSTS must specify includeSubDomains"


def test_nginx_conf_csp_connect_src_strict():
    content = read_file(NGINX_CONF)
    match = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]+)"\s+always;', content)
    assert match, "Content-Security-Policy header must be present with always flag"
    csp = match.group(1)

    # Extract connect-src directive
    connect_match = re.search(r"connect-src\s+([^;]+)", csp)
    assert connect_match, "CSP must contain connect-src directive"
    connect_src = connect_match.group(1).strip()
    sources = connect_src.split()

    # Must contain https://idp.sv.lan and https://cp.sv.lan
    assert "https://idp.sv.lan" in sources, "CSP connect-src must contain https://idp.sv.lan"
    assert "https://cp.sv.lan" in sources, "CSP connect-src must contain https://cp.sv.lan"

    # connect-src must NOT contain unencrypted HTTP or wildcards
    for src in sources:
        assert not src.startswith("http://"), f"Insecure unencrypted HTTP forbidden in connect-src: {src}"
        assert src != "*", "Wildcard forbidden in connect-src"

    # connect-src must contain ONLY the approved intranet origins
    allowed_sources = {"https://idp.sv.lan", "https://cp.sv.lan"}
    assert set(sources) == allowed_sources, f"CSP connect-src must contain only {allowed_sources}, found: {sources}"


def test_nginx_conf_spa_fallback_and_cache_control():
    content = read_file(NGINX_CONF)
    # SPA Fallback
    assert "try_files $uri $uri/ /index.html;" in content, "SPA fallback try_files must be present"

    # /auth-config.js no-cache
    assert re.search(r"location\s*=\s*/auth-config\.js\s*\{[^}]*Cache-Control\s*\"no-cache", content), \
        "/auth-config.js must have no-cache header"

    # /index.html no-cache
    assert re.search(r"location\s*=\s*/index\.html\s*\{[^}]*Cache-Control\s*\"no-cache", content), \
        "/index.html must have no-cache header"

    # /assets/ immutable
    assert re.search(r"location\s*/assets/\s*\{[^}]*immutable", content), \
        "/assets/ must have immutable cache header"


# =========================================================================
# 2. auth-config.js Contract Tests
# =========================================================================

def test_portal_auth_config_js_contract():
    assert AUTH_CONFIG_JS.is_file(), "deploy/intranet/portal/auth-config.js must exist"
    content = read_file(AUTH_CONFIG_JS)

    assert "https://idp.sv.lan/realms/saintvision" in content, \
        "auth-config.js must configure issuer https://idp.sv.lan/realms/saintvision"
    assert "'sv-portal'" in content or '"sv-portal"' in content, \
        "auth-config.js must configure clientId sv-portal"
    assert "https://portal.sv.lan/callback" in content, \
        "auth-config.js must configure redirectUri https://portal.sv.lan/callback"


# =========================================================================
# 3. Dockerfile Invariant Tests
# =========================================================================

def test_dockerfile_hardened_profile():
    assert DOCKERFILE.is_file(), "deploy/intranet/portal/Dockerfile must exist"
    content = read_file(DOCKERFILE)

    # Multi-stage build
    assert "FROM node:" in content
    assert "FROM nginx:" in content
    # Non-root user
    assert re.search(r"USER\s+101:101", content), "Dockerfile must switch to non-root USER 101:101"
    # Labels
    assert 'LABEL ai.saintvision.service="portal"' in content
    assert 'LABEL ai.saintvision.role="web-portal"' in content
    assert 'LABEL ai.saintvision.node="node2"' in content
    # Static files copied
    assert "nginx.conf" in content
    assert "auth-config.js" in content


# =========================================================================
# 4. portal-up.sh Static Invariant Tests
# =========================================================================

def test_portal_up_sh_exists_and_executable():
    assert PORTAL_UP_SH.is_file(), "portal-up.sh must exist"
    content = read_file(PORTAL_UP_SH)
    assert content.startswith("#!/usr/bin/env bash"), "portal-up.sh must have bash shebang"
    assert "set -euo pipefail" in content


def test_portal_up_owner_label_filter_only():
    content = read_file(PORTAL_UP_SH)
    # Must declare owner label
    assert 'OWNER_LABEL_KEY="ai.saintvision.service"' in content
    assert 'OWNER_LABEL_VAL="portal"' in content

    # Must verify existing container's label before replacing
    assert '{{index .Config.Labels "ai.saintvision.service"}}' in content
    assert 'Refusing to modify or delete non-owned container' in content or 'Refusing' in content

    # Cleanup must use label filter
    assert '--filter "label=${OWNER_LABEL}"' in content


def test_portal_up_no_secrets_in_argv_or_env():
    content = read_file(PORTAL_UP_SH)
    # Check argv secret guard
    assert "*password*|*secret*|*private_key*|*-e*|*--env*" in content, \
        "portal-up.sh must actively prohibit secrets and -e flags in argv"

    # Verify docker run command has NO -e or --env flags
    # Split docker run command
    docker_run_part = content[content.find("docker run"):]
    docker_run_cmd = docker_run_part[:docker_run_part.find("\n\n")]
    assert " -e " not in docker_run_cmd, "docker run in portal-up.sh must NOT contain -e flag"
    assert " --env " not in docker_run_cmd, "docker run in portal-up.sh must NOT contain --env flag"


def test_portal_up_tls_key_single_file_readonly_mount():
    content = read_file(PORTAL_UP_SH)
    # Key integrity verification
    assert "openssl pkey -in" in content
    assert "openssl x509 -in" in content
    assert "cert_pubkey_hash" in content
    assert "key_pubkey_hash" in content

    # Readonly bind mount
    assert re.search(r'--mount\s+"type=bind,source=\$\{CERT_FILE_ABS\},target=/etc/nginx/certs/portal\.crt,readonly"', content), \
        "Certificate must be mounted as single-file readonly bind"
    assert re.search(r'--mount\s+"type=bind,source=\$\{KEY_FILE_ABS\},target=/etc/nginx/certs/portal\.key,readonly"', content), \
        "Private key must be mounted as single-file readonly bind"


def test_portal_up_read_only_rootfs_and_capabilities():
    content = read_file(PORTAL_UP_SH)
    assert "--read-only" in content, "docker run must specify --read-only rootfs"
    assert "--cap-drop ALL" in content, "docker run must drop all Linux capabilities"
    assert "--security-opt no-new-privileges" in content, "docker run must forbid privilege escalation"
    assert "--user 101:101" in content, "docker run must run as UID 101"
    assert "--tmpfs /tmp" in content, "docker run must mount /tmp on tmpfs"
    assert "--tmpfs /var/cache/nginx" in content, "docker run must mount /var/cache/nginx on tmpfs"
    assert "--tmpfs /var/run" in content, "docker run must mount /var/run on tmpfs"


def test_portal_down_sh_owner_label():
    assert PORTAL_DOWN_SH.is_file(), "portal-down.sh must exist"
    content = read_file(PORTAL_DOWN_SH)
    assert '{{index .Config.Labels "ai.saintvision.service"}}' in content
    assert "portal" in content


# =========================================================================
# 5. Mutation & Negative Controls (Reversibility: 되돌리면 실패)
# =========================================================================

def validate_nginx_csp(content: str) -> None:
    match = re.search(r'add_header\s+Content-Security-Policy\s+"([^"]+)"\s+always;', content)
    if not match:
        raise ValueError("Missing CSP header")
    csp = match.group(1)
    connect_match = re.search(r"connect-src\s+([^;]+)", csp)
    if not connect_match:
        raise ValueError("Missing connect-src in CSP")
    sources = set(connect_match.group(1).strip().split())
    if sources != {"https://idp.sv.lan", "https://cp.sv.lan"}:
        raise ValueError(f"CSP connect-src violation: {sources}")


def validate_nginx_hsts(content: str) -> None:
    match = re.search(r'add_header\s+Strict-Transport-Security\s+"([^"]+)"\s+always;', content)
    if not match:
        raise ValueError("Missing HSTS header")
    hsts = match.group(1)
    if "max-age=" not in hsts or int(re.search(r"max-age=(\d+)", hsts).group(1)) < 31536000:
        raise ValueError("HSTS max-age too short")
    if "includeSubDomains" not in hsts:
        raise ValueError("HSTS missing includeSubDomains")


def validate_nginx_tls(content: str) -> None:
    match = re.search(r"ssl_protocols\s+([^;]+);", content)
    if not match:
        raise ValueError("Missing ssl_protocols")
    protocols = match.group(1).split()
    if "TLSv1.2" not in protocols or "TLSv1.3" not in protocols:
        raise ValueError("Missing required TLS protocols")
    for bad in ["SSLv2", "SSLv3", "TLSv1", "TLSv1.0", "TLSv1.1"]:
        if bad in protocols:
            raise ValueError(f"Insecure protocol allowed: {bad}")


def validate_portal_up_security(content: str) -> None:
    if "--read-only" not in content:
        raise ValueError("Missing --read-only")
    if "--cap-drop ALL" not in content:
        raise ValueError("Missing --cap-drop ALL")
    if "readonly" not in content:
        raise ValueError("Missing readonly mount")
    if "ai.saintvision.service" not in content:
        raise ValueError("Missing owner label check")
    if "-e " in content or "--env " in content:
        raise ValueError("Forbidden environment variable injection in docker run")


def test_mutation_loosening_csp_fails():
    content = read_file(NGINX_CONF)

    # Mutation A: Add foreign untrusted origin
    mutated_foreign = content.replace("connect-src https://idp.sv.lan https://cp.sv.lan;",
                                      "connect-src https://idp.sv.lan https://cp.sv.lan https://evil.com;")
    with pytest.raises(ValueError, match="CSP connect-src violation"):
        validate_nginx_csp(mutated_foreign)

    # Mutation B: Add insecure HTTP origin
    mutated_http = content.replace("connect-src https://idp.sv.lan https://cp.sv.lan;",
                                   "connect-src https://idp.sv.lan https://cp.sv.lan http://cp.sv.lan;")
    with pytest.raises(ValueError, match="CSP connect-src violation"):
        validate_nginx_csp(mutated_http)

    # Mutation C: Remove https://idp.sv.lan
    mutated_missing_idp = content.replace("connect-src https://idp.sv.lan https://cp.sv.lan;",
                                          "connect-src https://cp.sv.lan;")
    with pytest.raises(ValueError, match="CSP connect-src violation"):
        validate_nginx_csp(mutated_missing_idp)

    # Mutation D: Remove https://cp.sv.lan
    mutated_missing_cp = content.replace("connect-src https://idp.sv.lan https://cp.sv.lan;",
                                         "connect-src https://idp.sv.lan;")
    with pytest.raises(ValueError, match="CSP connect-src violation"):
        validate_nginx_csp(mutated_missing_cp)


def test_mutation_removing_hsts_fails():
    content = read_file(NGINX_CONF)

    # Mutation: Strip HSTS header
    mutated = re.sub(r'add_header\s+Strict-Transport-Security[^\n]+;\n', '', content)
    with pytest.raises(ValueError, match="Missing HSTS header"):
        validate_nginx_hsts(mutated)

    # Mutation: max-age too short
    mutated_short = content.replace("max-age=31536000", "max-age=300")
    with pytest.raises(ValueError, match="HSTS max-age too short"):
        validate_nginx_hsts(mutated_short)


def test_mutation_enabling_legacy_tls_fails():
    content = read_file(NGINX_CONF)

    # Mutation: Add TLSv1.0
    mutated_tls10 = content.replace("ssl_protocols TLSv1.2 TLSv1.3;", "ssl_protocols TLSv1.0 TLSv1.2 TLSv1.3;")
    with pytest.raises(ValueError, match="Insecure protocol allowed"):
        validate_nginx_tls(mutated_tls10)

    # Mutation: Add TLSv1.1
    mutated_tls11 = content.replace("ssl_protocols TLSv1.2 TLSv1.3;", "ssl_protocols TLSv1.1 TLSv1.2 TLSv1.3;")
    with pytest.raises(ValueError, match="Insecure protocol allowed"):
        validate_nginx_tls(mutated_tls11)


def test_mutation_portal_up_security_flags_fail():
    content = read_file(PORTAL_UP_SH)

    # Mutation: Remove --read-only
    mutated_no_ro = content.replace("--read-only", "")
    with pytest.raises(ValueError, match="Missing --read-only"):
        validate_portal_up_security(mutated_no_ro)

    # Mutation: Remove --cap-drop ALL
    mutated_no_cap = content.replace("--cap-drop ALL", "")
    with pytest.raises(ValueError, match="Missing --cap-drop ALL"):
        validate_portal_up_security(mutated_no_cap)

    # Mutation: Remove readonly from bind mount
    mutated_rw_mount = content.replace(",readonly", "")
    with pytest.raises(ValueError, match="Missing readonly mount"):
        validate_portal_up_security(mutated_rw_mount)

    # Mutation: Inject environment variable flag in docker run
    mutated_env = content.replace('--restart unless-stopped', '-e SECRET_KEY="bad-token" \\\n    --restart unless-stopped')
    with pytest.raises(ValueError, match="Forbidden environment variable injection"):
        validate_portal_up_security(mutated_env)
