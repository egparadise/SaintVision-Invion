"""Tests for SaintVision Intranet Portal Deployment (Card 156).

Verifies security hardening, reverse proxy topology, non-root execution,
production leaf CA validation, owner 4-tuple isolation, and behavioral
PKI / Fake Docker integration tests.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DEPLOY_DIR = REPO_ROOT / "deploy" / "intranet" / "portal"
NGINX_CONF = DEPLOY_DIR / "nginx.conf"
SECURITY_HEADERS_CONF = DEPLOY_DIR / "security-headers.conf"
UPSTREAM_CONF = DEPLOY_DIR / "conf.d" / "upstream.conf"
AUTH_CONFIG_JS = DEPLOY_DIR / "auth-config.js"
PORTAL_UP_SH = DEPLOY_DIR / "portal-up.sh"
PORTAL_DOWN_SH = DEPLOY_DIR / "portal-down.sh"
PORTAL_SMOKE_UP_SH = DEPLOY_DIR / "portal-smoke-up.sh"
PORTAL_LOAD_RELEASE_SH = DEPLOY_DIR / "portal-load-release.sh"
PORTAL_RELEASE_SCHEMA = DEPLOY_DIR / "portal-release-evidence.schema.json"
GENERATE_DEV_CERTS_SH = DEPLOY_DIR / "generate-dev-certs.sh"
DOCKERFILE = DEPLOY_DIR / "Dockerfile"
DOCKERFILE_DOCKERIGNORE = DEPLOY_DIR / "Dockerfile.dockerignore"


def read_file(path: Path) -> str:
    assert path.is_file(), f"Expected file does not exist: {path}"
    return path.read_text(encoding="utf-8")


def strip_shell_comments(script_content: str) -> str:
    """Strip full-line and end-of-line comments from bash script for pure token inspection (M4)."""
    lines = []
    for line in script_content.splitlines():
        line = re.sub(r'(^|\s+)#.*$', '', line)
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def get_git_bash() -> str:
    git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if git_bash.is_file():
        return str(git_bash)
    return shutil.which("bash") or "bash"


def to_posix_path(p: Path) -> str:
    path_str = str(p.resolve())
    if len(path_str) >= 2 and path_str[1] == ':':
        drive = path_str[0].lower()
        rest = path_str[2:].replace('\\', '/')
        return f"/{drive}{rest}"
    return path_str.replace('\\', '/')


# =========================================================================
# 1. Security Headers & CSP Invariants
# =========================================================================

def test_security_headers_conf_invariants():
    content = read_file(SECURITY_HEADERS_CONF)

    # HSTS: 1 year with includeSubDomains
    assert "Strict-Transport-Security" in content
    assert "max-age=31536000" in content
    assert "includeSubDomains" in content

    # Content-Security-Policy
    assert "Content-Security-Policy" in content
    assert "connect-src 'self' https://idp.sv.lan;" in content
    assert "style-src 'self';" in content
    assert "'unsafe-inline'" not in content
    assert "form-action 'self';" in content
    assert "frame-ancestors 'none';" in content
    assert "object-src 'none';" in content
    assert "base-uri 'self';" in content

    # Standard security headers
    assert 'X-Content-Type-Options "nosniff"' in content
    assert 'X-Frame-Options "DENY"' in content
    assert 'X-XSS-Protection "0"' in content
    assert 'Referrer-Policy "strict-origin-when-cross-origin"' in content


def test_nginx_conf_includes_security_headers_in_all_add_header_locations():
    content = read_file(NGINX_CONF)
    locations_with_add_header = re.findall(
        r"location\s+([^{]+)\{[^}]*add_header[^}]*\}", content, re.DOTALL
    )
    assert len(locations_with_add_header) > 0, "Expected locations with add_header"
    for loc_pattern in locations_with_add_header:
        loc_block_match = re.search(
            r"location\s+" + re.escape(loc_pattern.strip()) + r"\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        )
        assert loc_block_match, f"Could not find block for {loc_pattern}"
        block_body = loc_block_match.group(1)
        assert "include /etc/nginx/security-headers.conf;" in block_body, (
            f"Location {loc_pattern.strip()} sets add_header but does NOT include security-headers.conf! "
            "Nginx 1.27 header inheritance bug would drop HSTS/CSP."
        )


# =========================================================================
# 2. Reverse Proxy Topology & Protocol Restrictions
# =========================================================================

def test_nginx_conf_reverse_proxy_topology():
    content = read_file(NGINX_CONF)

    # TLS Protocols: TLSv1.2 TLSv1.3 only
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in content
    assert "SSLv3" not in content
    assert "TLSv1.0" not in content
    assert "TLSv1.1" not in content

    # Upstream Control Plane definition
    assert "upstream control_plane" in read_file(UPSTREAM_CONF)
    assert "include /etc/nginx/conf.d/upstream.conf;" in content

    # Proxy locations: /v1/ REST API with HTTP/1.1 keepalive
    assert "location /v1/ {" in content
    assert "proxy_pass https://control_plane;" in content
    assert "proxy_ssl_verify on;" in content
    assert "proxy_ssl_trusted_certificate /etc/nginx/certs/ca-bundle.crt;" in content
    assert "proxy_ssl_name cp.sv.lan;" in content
    assert "proxy_ssl_server_name on;" in content
    assert "proxy_http_version 1.1;" in content
    assert 'proxy_set_header Connection "";' in content

    # Host header cp.sv.lan propagation (L1)
    assert "proxy_set_header Host cp.sv.lan;" in content

    # SSE Streaming endpoint with proxy_buffering off
    assert "proxy_buffering off;" in content

    # WebSocket Terminal Upgrade endpoints
    assert "location /v1/terminal/ws {" in content
    assert "proxy_set_header Upgrade $http_upgrade;" in content
    assert "proxy_set_header Connection $connection_upgrade;" in content


def test_nginx_conf_assets_caching_immutable():
    content = read_file(NGINX_CONF)
    # ^~ prefix match for /assets/ takes precedence over regex static extensions (M1)
    assert "location ^~ /assets/ {" in content
    match = re.search(r"location\s+\^~\s+/assets/\s+\{([^}]+)\}", content)
    assert match, "location ^~ /assets/ block must exist"
    body = match.group(1)
    assert "expires 1y;" in body
    assert 'add_header Cache-Control "public, immutable" always;' in body
    assert "try_files $uri =404;" in body


def test_nginx_conf_privacy_logging():
    content = read_file(NGINX_CONF)
    # Privacy log format: no query string, no referer
    assert "log_format privacy" in content
    assert '"$request_method $uri $server_protocol"' in content
    assert "$query_string" not in content
    assert "$http_referer" not in content

    # /callback location access_log off
    match = re.search(r"location\s+=\s+/callback\s+\{([^}]+)\}", content)
    assert match, "location = /callback block must exist"
    assert "access_log off;" in match.group(1)


def test_nginx_conf_fixed_https_redirect_and_healthz():
    content = read_file(NGINX_CONF)
    # HTTP port 80 strictly redirects to https://portal.sv.lan$request_uri
    assert "return 301 https://portal.sv.lan$request_uri;" in content
    # Port 80 keeps plaintext /healthz exception
    assert "location = /healthz {" in content


def test_nginx_conf_missing_static_files_404():
    content = read_file(NGINX_CONF)
    # Static files with known extensions must return 404 instead of SPA fallback
    assert "try_files $uri =404;" in content


def test_nginx_conf_no_daemon_off():
    content = read_file(NGINX_CONF)
    assert "daemon off" not in content, "nginx.conf must NOT contain 'daemon off;' (handled via Dockerfile CMD)"


# =========================================================================
# 3. Location-Level Proxy SSL Verification Parser (R3-H2 c)
# =========================================================================

def parse_proxy_locations_and_verify(content: str) -> None:
    """Location-level AST/block validator: every location with proxy_pass MUST have proxy_ssl_verify on;"""
    pattern = re.compile(r"location\s+([^{]+)\{([^}]+(?:\{[^}]*\}[^}]*)*)\}", re.MULTILINE)
    matches = pattern.findall(content)
    proxy_locations_found = 0

    for loc_path, loc_body in matches:
        if "proxy_pass" in loc_body:
            proxy_locations_found += 1
            if "proxy_ssl_verify on;" not in loc_body:
                raise ValueError(
                    f"Location '{loc_path.strip()}' contains proxy_pass but MISSING 'proxy_ssl_verify on;'!"
                )
    if proxy_locations_found == 0:
        raise ValueError("No proxy_pass locations found to verify")


def test_nginx_conf_all_proxy_locations_have_ssl_verify_on():
    content = read_file(NGINX_CONF)
    parse_proxy_locations_and_verify(content)


def test_mutation_proxy_ssl_verify_missing_or_off_fails():
    content = read_file(NGINX_CONF)

    # Mutation 1: Change /v1/ proxy_ssl_verify to off
    mutated1 = content.replace("location /v1/ {\n            proxy_pass https://control_plane;\n            proxy_ssl_verify on;",
                               "location /v1/ {\n            proxy_pass https://control_plane;\n            proxy_ssl_verify off;")
    with pytest.raises(ValueError, match="MISSING 'proxy_ssl_verify on;'"):
        parse_proxy_locations_and_verify(mutated1)

    # Mutation 2: Remove proxy_ssl_verify from WebSocket location
    mutated2 = content.replace("location /v1/terminal/ws {\n            proxy_pass https://control_plane;\n            proxy_ssl_verify on;",
                               "location /v1/terminal/ws {\n            proxy_pass https://control_plane;")
    with pytest.raises(ValueError, match="MISSING 'proxy_ssl_verify on;'"):
        parse_proxy_locations_and_verify(mutated2)


# =========================================================================
# 4. Owner Label 4-Tuple & Lifecycle Isolation (R3-M3)
# =========================================================================

def test_portal_up_sh_owner_label_4tuple():
    content = read_file(PORTAL_UP_SH)
    assert 'LABEL_SERVICE="ai.saintvision.service=portal"' in content
    assert 'LABEL_WORKLOAD="ai.saintvision.workload=intranet-portal"' in content
    assert 'LABEL_NODE="ai.saintvision.node=node2"' in content
    assert 'LABEL_INSTANCE="ai.saintvision.instance=${PORTAL_INSTANCE}"' in content
    assert "validate_owner_tuple" in content
    assert '--filter "status=exited"' in content


def test_portal_down_sh_owner_label_4tuple():
    content = read_file(PORTAL_DOWN_SH)
    assert 'existing_service=' in content
    assert 'existing_workload=' in content
    assert 'existing_node=' in content
    assert 'existing_instance=' in content
    assert 'Refusing to stop or remove non-owned container' in content


def test_portal_smoke_up_sh_owner_label_4tuple():
    content = read_file(PORTAL_SMOKE_UP_SH)
    # Smoke script checks all 4 owner labels (R3-M3)
    assert 'existing_service=' in content
    assert 'existing_workload=' in content
    assert 'existing_node=' in content
    assert 'existing_instance=' in content
    assert 'Refusing to stop or remove non-matching container' in content


def test_portal_smoke_up_sh_host_uid():
    content = read_file(PORTAL_SMOKE_UP_SH)
    # Smoke script uses host UID:GID default matching production (R3-M3)
    assert 'PORTAL_UID="${PORTAL_UID:-$(id -u)}"' in content
    assert 'PORTAL_GID="${PORTAL_GID:-$(id -g)}"' in content
    assert 'UPSTREAM_CP_HOST="${PORTAL_UPSTREAM_CP_HOST:-cp.sv.lan:443}"' in content


# =========================================================================
# 5. Production Root CA & Leaf Validation Requirements (R3-H1, R3-M1, R3-M2, R3-L1)
# =========================================================================

def test_portal_up_sh_mandatory_root_ca_allowlist():
    content = read_file(PORTAL_UP_SH)
    # Mandatory root fingerprint allowlist check (R3-H1)
    assert 'PORTAL_ALLOWED_ROOT_FINGERPRINTS is mandatory in production' in content
    # Multi-cert split check
    assert 'ca-split' in content
    # Single root check: reject 0 roots or >1 roots
    assert 'No root CA (self-signed trust anchor) found' in content
    assert 'Multiple root CAs' in content
    # Intermediate CA verify against root
    assert 'Intermediate CA' in content
    assert 'openssl verify -CAfile "$root_cert" "$inter"' in content


def test_portal_up_sh_mandatory_image_digest():
    content = read_file(PORTAL_UP_SH)
    # Mandatory image ID check (Codex r5 / R3-M1)
    assert 'PORTAL_IMAGE_ID is mandatory in production' in content
    assert 'TARGET_IMAGE="$resolved_id"' in content


def test_portal_up_sh_root_uid_rejected():
    content = read_file(PORTAL_UP_SH)
    # Reject root UID execution (R3-M2)
    assert '[[ "$PORTAL_UID" -eq 0 ]]' in content
    assert 'PORTAL_UID cannot be 0' in content


def test_portal_up_sh_key_owner_and_mode_match():
    content = read_file(PORTAL_UP_SH)
    # Key file owner must match PORTAL_UID (R3-M2)
    assert 'stat -c \'%u\' "$KEY_FILE"' in content
    assert 'owner UID' in content
    assert 'does not match PORTAL_UID' in content
    # Key file mode must strictly be 0400 (R4-H1)
    assert 'stat -c \'%a\' "$KEY_FILE"' in content
    assert 'permission mode must be strictly 0400' in content


def test_portal_up_sh_gid_zero_rejected():
    content = read_file(PORTAL_UP_SH)
    # Reject root GID execution (R4-H1)
    assert '"$PORTAL_GID" -eq 0' in content
    assert 'PORTAL_GID cannot be 0' in content


def test_portal_up_sh_staging_preflight_and_safety():
    content = read_file(PORTAL_UP_SH)
    # Trap cleanup on EXIT INT TERM (R3-M3)
    assert "trap staging_cleanup EXIT INT TERM" in content

    # --no-check-certificate MUST be ABSENT (R3-L1)
    assert "--no-check-certificate" not in content, "--no-check-certificate is strictly forbidden in preflight (R3-L1)"

    # Verified curl HTTPS preflight with hostname resolution and mounted CA
    assert "curl -fsS" in content
    assert "--resolve portal.sv.lan:443:127.0.0.1" in content
    assert "/healthz" in content
    assert "/index.html" in content
    assert "/auth-config.js" in content

    # Automatic rollback function and backup container verification (R4-M1)
    assert "rollback_production()" in content
    assert "Restoring previous production container" in content


def test_dockerfile_default_user_101():
    content = read_file(DOCKERFILE)
    # Dockerfile maintains default non-root USER 101:101 (R3-M2)
    assert "USER 101:101" in content
    assert "RUN apk add --no-cache 'curl>=8' 'openssl>=3'" in content


# =========================================================================
# 6. Real Behavioral OpenSSL PKI Tests (R3-H2 a)
# =========================================================================

@pytest.fixture(scope="module")
def pki_test_env():
    """Generates a complete test PKI suite with OpenSSL via Git Bash."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_portal_pki_test_"))
    posix_temp = to_posix_path(temp_dir)
    posix_portal_up = to_posix_path(PORTAL_UP_SH)

    # Generate Root CA
    gen_root_script = f"""
    set -e
    export MSYS_NO_PATHCONV=1
    cd "{posix_temp}"
    openssl ecparam -name prime256v1 -genkey -noout -out root.key
    openssl req -new -x509 -sha256 -key root.key -out root.crt -subj "/CN=SaintVision Root CA" -days 30
    openssl x509 -in root.crt -noout -fingerprint -sha256 | sed 's/.*=//' | tr -d ': ' | tr '[:upper:]' '[:lower:]'
    """
    res_root = subprocess.run([bash_path, "-c", gen_root_script], capture_output=True, text=True)
    assert res_root.returncode == 0, f"Root CA gen failed: {res_root.stderr}"
    root_fp = res_root.stdout.strip()

    # Generate Intermediate CA
    gen_inter_script = f"""
    set -e
    export MSYS_NO_PATHCONV=1
    cd "{posix_temp}"
    openssl ecparam -name prime256v1 -genkey -noout -out inter.key
    openssl req -new -key inter.key -out inter.csr -subj "/CN=SaintVision Intermediate CA"
    cat > inter.ext <<'EOF'
basicConstraints=critical,CA:TRUE,pathlen:0
keyUsage=critical,digitalSignature,keyCertSign,cRLSign
EOF
    openssl x509 -req -in inter.csr -CA root.crt -CAkey root.key -CAcreateserial -out inter.crt -extfile inter.ext -days 30
    cat inter.crt root.crt > ca-bundle.crt
    """
    res_inter = subprocess.run([bash_path, "-c", gen_inter_script], capture_output=True, text=True)
    assert res_inter.returncode == 0, f"Intermediate CA gen failed: {res_inter.stderr}"

    # Generate Valid Leaf Cert
    gen_leaf_script = f"""
    set -e
    export MSYS_NO_PATHCONV=1
    cd "{posix_temp}"
    openssl ecparam -name prime256v1 -genkey -noout -out server-key.pem
    chmod 0400 server-key.pem
    openssl req -new -key server-key.pem -out leaf.csr -subj "/CN=portal.sv.lan"
    cat > leaf.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:portal.sv.lan
EOF
    openssl x509 -req -in leaf.csr -CA inter.crt -CAkey inter.key -CAcreateserial -out leaf.crt -extfile leaf.ext -days 30
    cat leaf.crt inter.crt > server-chain.pem
    """
    res_leaf = subprocess.run([bash_path, "-c", gen_leaf_script], capture_output=True, text=True)
    assert res_leaf.returncode == 0, f"Leaf cert gen failed: {res_leaf.stderr}"

    # Generate Variations for Negative Controls
    gen_variants_script = f"""
    set -e
    export MSYS_NO_PATHCONV=1
    cd "{posix_temp}"
    # 1. Attacker Root
    openssl ecparam -name prime256v1 -genkey -noout -out attacker_root.key
    openssl req -new -x509 -sha256 -key attacker_root.key -out attacker_root.crt -subj "/CN=Attacker Root CA" -days 30

    # 2. Self-signed leaf
    openssl ecparam -name prime256v1 -genkey -noout -out self_signed.key
    openssl req -new -x509 -sha256 -key self_signed.key -out self_signed.crt -subj "/CN=portal.sv.lan" -days 30

    # 3. Leaf with CA:TRUE
    cat > ca_true.ext <<'EOF'
basicConstraints=critical,CA:TRUE
keyUsage=critical,digitalSignature,keyCertSign
extendedKeyUsage=serverAuth
subjectAltName=DNS:portal.sv.lan
EOF
    openssl x509 -req -in leaf.csr -CA inter.crt -CAkey inter.key -CAcreateserial -out leaf_ca_true.crt -extfile ca_true.ext -days 30

    # 4. Leaf missing CA:FALSE (no basicConstraints)
    cat > no_bc.ext <<'EOF'
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:portal.sv.lan
EOF
    openssl x509 -req -in leaf.csr -CA inter.crt -CAkey inter.key -CAcreateserial -out leaf_no_bc.crt -extfile no_bc.ext -days 30

    # 5. Leaf without serverAuth EKU
    cat > no_serverauth.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=clientAuth
subjectAltName=DNS:portal.sv.lan
EOF
    openssl x509 -req -in leaf.csr -CA inter.crt -CAkey inter.key -CAcreateserial -out leaf_no_serverauth.crt -extfile no_serverauth.ext -days 30

    # 6. Leaf with wrong SAN
    cat > wrong_san.ext <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature
extendedKeyUsage=serverAuth
subjectAltName=DNS:attacker.sv.lan
EOF
    openssl x509 -req -in leaf.csr -CA inter.crt -CAkey inter.key -CAcreateserial -out leaf_wrong_san.crt -extfile wrong_san.ext -days 30

    # 7. Multi-root bundle (root + attacker_root)
    cat root.crt attacker_root.crt > multi_root_bundle.crt

    # 8. No root bundle (only intermediate)
    cp inter.crt no_root_bundle.crt

    # 9. Intermediate signed by attacker root
    openssl x509 -req -in inter.csr -CA attacker_root.crt -CAkey attacker_root.key -CAcreateserial -out attacker_inter.crt -days 30
    cat attacker_inter.crt root.crt > bad_intermediate_bundle.crt

    # 10. Leaf signed by foreign attacker CA with foreign key (mutation d: leaf chain verification failure)
    openssl ecparam -name prime256v1 -genkey -noout -out attacker_ca.key
    openssl req -new -x509 -sha256 -key attacker_ca.key -out attacker_ca.crt -subj "/CN=Attacker Intermediate CA" -days 30
    openssl x509 -req -in leaf.csr -CA attacker_ca.crt -CAkey attacker_ca.key -CAcreateserial -out leaf_attacker_ca.crt -extfile leaf.ext -days 30
    cat leaf_attacker_ca.crt attacker_ca.crt > server_chain_attacker.pem
    """
    res_var = subprocess.run([bash_path, "-c", gen_variants_script], capture_output=True, text=True)
    assert res_var.returncode == 0, f"Variant gen failed: {res_var.stderr}"

    yield {
        "bash_path": bash_path,
        "temp_dir": temp_dir,
        "posix_temp": posix_temp,
        "portal_up": posix_portal_up,
        "root_fp": root_fp,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)


def run_pki_func(env: dict, func_name: str, overrides: dict) -> subprocess.CompletedProcess:
    posix_temp = env["posix_temp"]
    default_ca = f"{posix_temp}/ca-bundle.crt"
    default_cert = f"{posix_temp}/server-chain.pem"
    default_key = f"{posix_temp}/server-key.pem"
    id_default = "sha256:" + "a" * 64
    image_id_val = overrides.get("PORTAL_IMAGE_ID", id_default)
    digest_line = f'PORTAL_IMAGE_DIGEST="{overrides["PORTAL_IMAGE_DIGEST"]}"' if "PORTAL_IMAGE_DIGEST" in overrides else 'unset PORTAL_IMAGE_DIGEST'
    script_lines = [
        f'source "{env["portal_up"]}"',
        f'STATE_DIR="{posix_temp}/state_{func_name}"',
        'mkdir -p "$STATE_DIR"',
        f'PORTAL_ALLOWED_ROOT_FINGERPRINTS="{overrides.get("PORTAL_ALLOWED_ROOT_FINGERPRINTS", env["root_fp"])}"',
        f'CA_BUNDLE_FILE="{overrides.get("CA_BUNDLE_FILE", default_ca)}"',
        f'CERT_FILE="{overrides.get("CERT_FILE", default_cert)}"',
        f'KEY_FILE="{overrides.get("KEY_FILE", default_key)}"',
        f'PORTAL_UID="{overrides.get("PORTAL_UID", "1000")}"',
        f'PORTAL_GID="{overrides.get("PORTAL_GID", "1000")}"',
        f'UPSTREAM_CP_HOST="{overrides.get("UPSTREAM_CP_HOST", "cp.sv.lan:443")}"',
        f'PORTAL_IMAGE_ID="{image_id_val}"',
        digest_line,
        func_name,
    ]
    return subprocess.run(
        [env["bash_path"], "-c", "\n".join(script_lines)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_behavioral_pki_valid_chain_passes(pki_test_env):
    res_ca = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {})
    assert res_ca.returncode == 0, f"CA validate failed: {res_ca.stderr}"

    res_leaf = run_pki_func(pki_test_env, "validate_leaf_certificate", {})
    assert res_leaf.returncode == 0, f"Leaf validate failed: {res_leaf.stderr}"


def test_behavioral_pki_missing_allowlist_fails(pki_test_env):
    res = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {"PORTAL_ALLOWED_ROOT_FINGERPRINTS": ""})
    assert res.returncode == 1
    assert "PORTAL_ALLOWED_ROOT_FINGERPRINTS is mandatory in production" in res.stderr


def test_behavioral_pki_attacker_root_fails(pki_test_env):
    bad_fp = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    res = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {"PORTAL_ALLOWED_ROOT_FINGERPRINTS": bad_fp})
    assert res.returncode == 1
    assert "does NOT match approved allowlist" in res.stderr


def test_behavioral_pki_multi_root_bundle_fails(pki_test_env):
    multi_bundle = f"{pki_test_env['posix_temp']}/multi_root_bundle.crt"
    res = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {"CA_BUNDLE_FILE": multi_bundle})
    assert res.returncode == 1
    assert "Multiple root CAs" in res.stderr


def test_behavioral_pki_no_root_bundle_fails(pki_test_env):
    no_root = f"{pki_test_env['posix_temp']}/no_root_bundle.crt"
    res = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {"CA_BUNDLE_FILE": no_root})
    assert res.returncode == 1
    assert "No root CA" in res.stderr


def test_behavioral_pki_invalid_intermediate_fails(pki_test_env):
    bad_inter = f"{pki_test_env['posix_temp']}/bad_intermediate_bundle.crt"
    res = run_pki_func(pki_test_env, "validate_ca_bundle_and_allowlist", {"CA_BUNDLE_FILE": bad_inter})
    assert res.returncode == 1
    assert "not signed by approved root CA" in res.stderr


def test_behavioral_pki_self_signed_leaf_fails(pki_test_env):
    self_signed = f"{pki_test_env['posix_temp']}/self_signed.crt"
    self_key = f"{pki_test_env['posix_temp']}/self_signed.key"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": self_signed, "KEY_FILE": self_key})
    assert res.returncode == 1
    assert "Self-signed certificate rejected" in res.stderr


def test_behavioral_pki_ca_true_leaf_fails(pki_test_env):
    ca_true = f"{pki_test_env['posix_temp']}/leaf_ca_true.crt"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": ca_true})
    assert res.returncode == 1
    assert "CA:TRUE" in res.stderr


def test_behavioral_pki_missing_ca_false_fails(pki_test_env):
    no_bc = f"{pki_test_env['posix_temp']}/leaf_no_bc.crt"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": no_bc})
    assert res.returncode == 1
    assert "must explicitly contain CA:FALSE" in res.stderr


def test_behavioral_pki_missing_server_auth_fails(pki_test_env):
    no_sa = f"{pki_test_env['posix_temp']}/leaf_no_serverauth.crt"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": no_sa})
    assert res.returncode == 1
    assert "must include TLS Web Server Authentication" in res.stderr


def test_behavioral_pki_wrong_san_fails(pki_test_env):
    wrong_san = f"{pki_test_env['posix_temp']}/leaf_wrong_san.crt"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": wrong_san})
    assert res.returncode == 1
    assert "Certificate SAN does not contain DNS:portal.sv.lan" in res.stderr


def test_behavioral_pki_key_mismatch_fails(pki_test_env):
    wrong_key = f"{pki_test_env['posix_temp']}/root.key"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"KEY_FILE": wrong_key})
    assert res.returncode == 1
    assert "does NOT match certificate public key" in res.stderr


def test_behavioral_environment_root_uid_rejected(pki_test_env):
    res = run_pki_func(pki_test_env, "validate_environment", {"PORTAL_UID": "0"})
    assert res.returncode == 1
    assert "PORTAL_UID cannot be 0" in res.stderr


def test_behavioral_environment_upstream_mismatch_rejected(pki_test_env):
    res = run_pki_func(pki_test_env, "validate_environment", {"UPSTREAM_CP_HOST": "evil.attacker.com:443"})
    assert res.returncode == 1
    assert "PORTAL_UPSTREAM_CP_HOST must be exactly 'cp.sv.lan:443'" in res.stderr


def test_behavioral_environment_root_gid_rejected(pki_test_env):
    res = run_pki_func(pki_test_env, "validate_environment", {"PORTAL_GID": "0"})
    assert res.returncode == 1
    assert "PORTAL_GID cannot be 0" in res.stderr


def test_behavioral_environment_key_mode_fail_closed(pki_test_env):
    """Verify that non-0400 key permission modes (0644, 0440, 0600) are rejected fail-closed."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_stat_stub_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    for mode, expected_ok in [("400", True), ("0400", True), ("644", False), ("440", False), ("600", False)]:
        stat_stub = f"""#!/usr/bin/env bash
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-c" ]]; then
        format="$2"
        shift 2
    else
        file="$1"
        shift
    fi
done
if [[ "$format" == "%u" ]]; then
    echo "1000"
elif [[ "$format" == "%a" ]]; then
    echo "{mode}"
fi
"""
        (bin_dir / "stat").write_text(stat_stub.replace("\r\n", "\n"), encoding="utf-8")
        os.chmod(bin_dir / "stat", 0o755)

        test_sh = f"""
        export PATH="{to_posix_path(bin_dir)}:$PATH"
        source "{to_posix_path(PORTAL_UP_SH)}"
        STATE_DIR="{to_posix_path(temp_dir)}/state"
        mkdir -p "$STATE_DIR"
        PORTAL_UID=1000
        PORTAL_GID=1000
        UPSTREAM_CP_HOST="cp.sv.lan:443"
        KEY_FILE="{to_posix_path(temp_dir)}/key.pem"
        touch "$KEY_FILE"
        validate_environment
        """
        res = subprocess.run(
            [bash_path, "-c", test_sh],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if expected_ok:
            assert res.returncode == 0, f"Expected mode {mode} to pass, got {res.returncode}: {res.stderr}"
        else:
            assert res.returncode == 1, f"Expected mode {mode} to be rejected, got 0"
            assert "permission mode must be strictly 0400" in res.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_image_id_mandatory_rejected(pki_test_env):
    res = run_pki_func(pki_test_env, "validate_image_and_id", {"PORTAL_IMAGE_ID": ""})
    assert res.returncode == 1
    assert "PORTAL_IMAGE_ID is mandatory in production" in res.stderr


def test_behavioral_legacy_portal_image_digest_fails_closed(pki_test_env):
    """(Codex r6 Block 2) Verify that providing legacy PORTAL_IMAGE_DIGEST fails closed with explicit deprecation error."""
    res = run_pki_func(
        pki_test_env,
        "validate_image_and_id",
        {"PORTAL_IMAGE_ID": "", "PORTAL_IMAGE_DIGEST": "sha256:" + "a" * 64},
    )
    assert res.returncode == 1
    assert "PORTAL_IMAGE_DIGEST is deprecated and forbidden" in res.stderr

def test_behavioral_image_id_mismatch_different_image_with_same_tag_rejected():
    """(Codex r5 & Coordinator) Verify that a target image whose config .Id does NOT match approved PORTAL_IMAGE_ID is rejected."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_image_id_mismatch_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    approved_id = "sha256:" + "1" * 64
    actual_id = "sha256:" + "2" * 64

    docker_stub = f"""#!/usr/bin/env bash
if [[ "$1" == "image" && "$2" == "inspect" ]]; then
    if [[ "$*" == *"--format"* ]]; then
        echo "{actual_id}"
    fi
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    IMAGE_NAME="saintvision-portal:latest"
    PORTAL_IMAGE_ID="{approved_id}"
    validate_image_and_id
    """
    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, f"Expected Image ID mismatch to fail, got {res.returncode}: {res.stdout}"
    assert "Image ID mismatch" in res.stderr
    assert f"Expected {approved_id}, got {actual_id}" in res.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)



# =========================================================================
# 7. Fake Docker Behavioral Tests (R3-H2 b)
# =========================================================================

def test_behavioral_fake_docker_non_matching_owner_labels_preserved():
    """Verify that when inspect returns non-matching labels, container is NOT stopped or removed."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "other-service"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    fi
    exit 0
elif [[ "$cmd" == "stop" || "$cmd" == "rm" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    swap_and_launch_production
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, f"Expected swap_and_launch_production to fail, got 0: {res.stdout}"
    assert "Refusing to touch non-matching container on node2" in res.stderr

    # Verify that docker stop and docker rm were NEVER called
    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "stop" not in calls, f"Forbidden docker stop called on non-matching container: {calls}"
    assert "rm" not in calls, f"Forbidden docker rm called on non-matching container: {calls}"

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_staging_trap_cleanup():
    """Verify that staging failure triggers staging_cleanup trap and executes docker rm -f."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_trap_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "run" ]]; then
    echo "staging-container-id"
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "preflight"
    elif [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    # Fail preflight nginx -t to trigger cleanup
    echo "nginx -t simulated syntax error" >&2
    exit 1
elif [[ "$cmd" == "rm" || "$cmd" == "stop" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    run_staging_preflight
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, "Expected run_staging_preflight to fail on nginx -t error"
    assert "Preflight 'nginx -t' failed in staging container" in res.stderr

    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "rm -f saintvision-portal-staging-" in calls, (
        f"staging_cleanup must call docker rm -f on staging container! Found calls: {calls}"
    )

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_staging_preexisting_conflict_no_stop_or_rm():
    """Verify that when staging docker run fails (e.g. name conflict with foreign container), stop or rm is 0 times."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_conflict_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "run" ]]; then
    echo "Conflict: container name already in use" >&2
    exit 125
elif [[ "$cmd" == "rm" || "$cmd" == "stop" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    run_staging_preflight
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, "Expected run_staging_preflight to fail when docker run fails"
    assert "Failed to launch staging preflight container" in res.stderr

    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "stop" not in calls, f"Forbidden docker stop called on failed run: {calls}"
    assert "rm" not in calls, f"Forbidden docker rm called on failed run: {calls}"

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_smoke_non_matching_owner_labels_preserved():
    """Verify that portal-smoke-up.sh preserves containers with non-matching 4-tuple."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_smoke_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "other-instance"
    elif [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    fi
    exit 0
elif [[ "$cmd" == "stop" || "$cmd" == "rm" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    export PORTAL_DEV_CERTS_DIR="{to_posix_path(temp_dir / 'certs')}"
    bash "{to_posix_path(PORTAL_SMOKE_UP_SH)}"
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, "Expected smoke launcher to abort on non-matching instance label"
    assert "Refusing to stop or remove non-matching container" in res.stderr

    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "stop" not in calls, f"Forbidden docker stop called: {calls}"
    assert "rm" not in calls, f"Forbidden docker rm called: {calls}"

    shutil.rmtree(temp_dir, ignore_errors=True)

# =========================================================================
# 8. R4 Surviving Mutations and Rollback Behavioral Tests (R4-H2)
# =========================================================================

def test_behavioral_pki_leaf_signed_by_different_ca_fails(pki_test_env):
    """(Mutation d) Verify that leaf certificate signed by a foreign/attacker CA fails verification against the legitimate CA bundle."""
    attacker_leaf = f"{pki_test_env['posix_temp']}/leaf_attacker_ca.crt"
    res = run_pki_func(pki_test_env, "validate_leaf_certificate", {"CERT_FILE": attacker_leaf})
    assert res.returncode == 1, f"Expected leaf signed by different CA to fail verification, got {res.returncode}"
    assert "Certificate chain verification failed against CA bundle" in res.stderr


def test_behavioral_fake_docker_instance_mismatch_preserved():
    """(Mutation e) Verify that production launcher preserves existing container when ONLY instance label differs."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_instance_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "canary-instance"
    fi
    exit 0
elif [[ "$cmd" == "stop" || "$cmd" == "rm" || "$cmd" == "rename" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    swap_and_launch_production
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, f"Expected swap_and_launch_production to fail on instance mismatch, got 0: {res.stdout}"
    assert "Refusing to touch non-matching container on node2" in res.stderr

    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "stop" not in calls, f"Forbidden docker stop called on instance mismatch: {calls}"
    assert "rm" not in calls, f"Forbidden docker rm called on instance mismatch: {calls}"
    assert "rename" not in calls, f"Forbidden docker rename called on instance mismatch: {calls}"

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_environment_upstream_mismatch_independent_fail():
    """(Mutation h) Verify that UPSTREAM_CP_HOST != cp.sv.lan:443 fails independently even when all other inputs (stat 0400, UID 1000, GID 1000) are valid."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_upstream_stat_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    stat_stub = f"""#!/usr/bin/env bash
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-c" ]]; then
        format="$2"
        shift 2
    else
        file="$1"
        shift
    fi
done
if [[ "$format" == "%u" ]]; then
    echo "1000"
elif [[ "$format" == "%a" ]]; then
    echo "0400"
fi
"""
    (bin_dir / "stat").write_text(stat_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "stat", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    source "{to_posix_path(PORTAL_UP_SH)}"
    STATE_DIR="{to_posix_path(temp_dir)}/state"
    mkdir -p "$STATE_DIR"
    PORTAL_UID=1000
    PORTAL_GID=1000
    UPSTREAM_CP_HOST="cp.sv.lan:8443"
    KEY_FILE="{to_posix_path(temp_dir)}/key.pem"
    touch "$KEY_FILE"
    validate_environment
    """
    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, f"Expected UPSTREAM_CP_HOST mismatch to fail, got {res.returncode}"
    assert "PORTAL_UPSTREAM_CP_HOST must be exactly 'cp.sv.lan:443'" in res.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_staging_index_html_probe_failure():
    """(Mutation o) Verify that staging preflight fails and cleans up if /index.html probe fails."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_index_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "run" ]]; then
    echo "staging-container-id"
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "preflight"
    elif [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    cmdline="$*"
    if [[ "$cmdline" == *index.html* ]]; then
        echo "Simulated 500 Internal Server Error for /index.html" >&2
        exit 1
    fi
    exit 0
elif [[ "$cmd" == "rm" || "$cmd" == "stop" ]]; then
    echo "$cmd $*" >> "{to_posix_path(calls_log)}"
    exit 0
fi
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    run_staging_preflight
    """

    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, "Expected run_staging_preflight to fail on /index.html probe failure"
    assert "Staging preflight verified HTTPS /index.html failed." in res.stderr

    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    assert "rm -f saintvision-portal-staging-" in calls, (
        f"staging_cleanup must remove staging container on probe failure! Found calls: {calls}"
    )

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_environment_key_owner_mismatch_rejected():
    """(Mutation t) Verify that key file owner UID mismatch (stat %u != PORTAL_UID) fails closed."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_owner_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    stat_stub = f"""#!/usr/bin/env bash
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-c" ]]; then
        format="$2"
        shift 2
    else
        file="$1"
        shift
    fi
done
if [[ "$format" == "%u" ]]; then
    echo "2000"
elif [[ "$format" == "%a" ]]; then
    echo "0400"
fi
"""
    (bin_dir / "stat").write_text(stat_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "stat", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    source "{to_posix_path(PORTAL_UP_SH)}"
    STATE_DIR="{to_posix_path(temp_dir)}/state"
    mkdir -p "$STATE_DIR"
    PORTAL_UID=1000
    PORTAL_GID=1000
    UPSTREAM_CP_HOST="cp.sv.lan:443"
    KEY_FILE="{to_posix_path(temp_dir)}/key.pem"
    touch "$KEY_FILE"
    validate_environment
    """
    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert res.returncode == 1, f"Expected key owner mismatch to fail, got {res.returncode}"
    assert "owner UID (2000) does not match PORTAL_UID (1000)" in res.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)


def _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir):
    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    swap_and_launch_production
    """
    res = subprocess.run(
        [bash_path, "-c", test_sh],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    calls = calls_log.read_text(encoding="utf-8") if calls_log.exists() else ""
    return res, calls


def _assert_exact_rollback_sequence(calls):
    m = re.search(r"docker rename saintvision-portal (saintvision-portal-backup-\S+)", calls)
    assert m, f"Initial backup rename missing in calls: {calls}"
    backup_name = m.group(1)

    assert f"docker stop {backup_name}" in calls
    assert "docker stop saintvision-portal" in calls
    assert "docker rm -f saintvision-portal" in calls
    assert f"docker start {backup_name}" in calls
    assert f"docker rename {backup_name} saintvision-portal" in calls

    stop_broken_idx = calls.find("docker stop saintvision-portal")
    rm_broken_idx = calls.find("docker rm -f saintvision-portal")
    start_backup_idx = calls.find(f"docker start {backup_name}")
    rename_backup_idx = calls.find(f"docker rename {backup_name} saintvision-portal")

    assert 0 <= stop_broken_idx < rm_broken_idx < start_backup_idx < rename_backup_idx, (
        f"Invalid rollback sequence ordering in calls: {calls}"
    )


def test_behavioral_fake_docker_swap_docker_run_failure_triggers_rollback():
    """(R5-H1) Verify that when production docker run fails (exit 125, port conflict), backup is restored and running."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_run_fail_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "run" ]]; then
    echo "docker: Error response from daemon: driver failed programming external connectivity on endpoint: Bind for 0.0.0.0:8443 failed: port is already allocated." >&2
    exit 125
elif [[ "$cmd" == "rename" || "$cmd" == "stop" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    res, calls = _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir)
    assert res.returncode == 1, f"Expected swap failure on docker run exit 125, got {res.returncode}: {res.stdout}"
    assert "Failed to run production container. Initiating automatic rollback..." in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr

    _assert_exact_rollback_sequence(calls)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_swap_not_running_triggers_rollback():
    """(Mutation R6) Verify that when production container fails to enter running state, rollback is triggered and backup restored."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_not_running_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        # Return false for the newly launched container to trigger not-running rollback
        if [[ -f "{to_posix_path(temp_dir)}/restored" ]]; then
            echo "true"
        else
            echo "false"
        fi
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "rename" ]]; then
    if [[ "$*" == *" saintvision-portal" ]]; then
        touch "{to_posix_path(temp_dir)}/restored"
    fi
    exit 0
elif [[ "$cmd" == "stop" || "$cmd" == "run" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    res, calls = _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir)
    assert res.returncode == 1, f"Expected swap failure on not-running state, got {res.returncode}: {res.stdout}"
    assert "failed to enter running state" in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr

    _assert_exact_rollback_sequence(calls)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_swap_healthz_probe_failure_triggers_rollback():
    """(Mutation u) Verify that when /healthz HTTPS probe fails in production, rollback is triggered and backup restored."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_healthz_fail_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    cmdline="$*"
    if [[ "$cmdline" == *healthz* ]]; then
        echo "Simulated 503 Service Unavailable on /healthz" >&2
        exit 1
    fi
    exit 0
elif [[ "$cmd" == "rename" || "$cmd" == "stop" || "$cmd" == "run" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    res, calls = _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir)
    assert res.returncode == 1, f"Expected swap failure on healthz probe failure, got {res.returncode}: {res.stdout}"
    assert "Production verified HTTPS /healthz failed." in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr

    _assert_exact_rollback_sequence(calls)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_swap_index_probe_failure_triggers_rollback():
    """(Mutation R4) Verify that when /index.html HTTPS probe fails in production (/healthz passing), rollback is triggered and backup restored."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_index_fail_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    cmdline="$*"
    if [[ "$cmdline" == *index.html* ]]; then
        echo "Simulated 500 Internal Server Error on /index.html" >&2
        exit 1
    fi
    exit 0
elif [[ "$cmd" == "rename" || "$cmd" == "stop" || "$cmd" == "run" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    res, calls = _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir)
    assert res.returncode == 1, f"Expected swap failure on index.html probe failure, got {res.returncode}: {res.stdout}"
    assert "Production verified HTTPS /index.html failed." in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr

    _assert_exact_rollback_sequence(calls)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_fake_docker_swap_auth_config_probe_failure_triggers_rollback():
    """(Mutation R5) Verify that when /auth-config.js HTTPS probe fails in production (/healthz & /index.html passing), rollback is triggered and backup restored."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_fake_docker_auth_fail_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    cmdline="$*"
    if [[ "$cmdline" == *auth-config.js* ]]; then
        echo "Simulated 502 Bad Gateway on /auth-config.js" >&2
        exit 1
    fi
    exit 0
elif [[ "$cmd" == "rename" || "$cmd" == "stop" || "$cmd" == "run" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    res, calls = _run_swap_rollback_harness(bin_dir, calls_log, bash_path, temp_dir)
    assert res.returncode == 1, f"Expected swap failure on auth-config.js probe failure, got {res.returncode}: {res.stdout}"
    assert "Production verified HTTPS /auth-config.js failed." in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr

    _assert_exact_rollback_sequence(calls)
    shutil.rmtree(temp_dir, ignore_errors=True)
# =========================================================================
# 10. Release Evidence & Loader Behavioral Tests (Codex r6 Block 1)
# =========================================================================

def test_portal_release_evidence_schema_structure():
    """Verify that portal-release-evidence.schema.json exists, is valid JSON schema, and forbids unknown fields."""
    import json
    assert PORTAL_RELEASE_SCHEMA.is_file()
    schema = json.loads(PORTAL_RELEASE_SCHEMA.read_text(encoding="utf-8"))
    assert schema.get("additionalProperties") is False
    assert "codeSha" in schema["required"]
    assert "imageId" in schema["required"]
    assert "tarSha256" in schema["required"]
    assert "buildRunId" in schema["required"]
    assert "buildTimestamp" in schema["required"]


def test_portal_load_release_sh_syntax_and_structure():
    """Verify that portal-load-release.sh exists, passes bash -n syntax check, and enforces fail-closed checks."""
    assert PORTAL_LOAD_RELEASE_SH.is_file()
    bash_path = get_git_bash()
    res = subprocess.run([bash_path, "-n", str(PORTAL_LOAD_RELEASE_SH)], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"bash -n failed: {res.stderr}"

    content = PORTAL_LOAD_RELEASE_SH.read_text(encoding="utf-8")
    assert "set -euo pipefail" in content
    assert "Unknown field(s) in Evidence JSON (fail-closed)" in content
    assert "Release tarball SHA-256 mismatch (fail-closed)" in content
    assert "Loaded image config .Id mismatch (fail-closed)" in content
    assert 'export PORTAL_IMAGE_ID="$EXP_IMAGE_ID"' in content


def test_behavioral_load_release_missing_files_rejected():
    """Verify that portal-load-release.sh fails closed when files are missing or unspecified."""
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)

    # 1. No arguments
    res = subprocess.run([bash_path, script_posix], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Missing release evidence file" in res.stderr

    # 2. Non-existent evidence file
    res = subprocess.run([bash_path, script_posix, "--evidence", "/non/existent/evidence.json", "--tar", "/dummy/tar.tar"],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Release evidence file not found" in res.stderr

    # 3. Non-existent tar file
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_test_"))
    ev_file = temp_dir / "evidence.json"
    ev_file.write_text("{}", encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", "/non/existent/tar.tar"],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Release tarball file not found" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_unknown_field_in_evidence_rejected():
    """Verify that Evidence JSON containing unknown fields is rejected fail-closed (Codex r6 Block 1)."""
    import json
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_unknown_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"dummy tar content")

    payload = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": "sha256:" + "b" * 64,
        "tarSha256": "c" * 64,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
        "unauthorizedKey": "malicious_payload",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Unknown field(s) in Evidence JSON (fail-closed)" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_missing_required_field_rejected():
    """Verify that Evidence JSON missing a required field (e.g. tarSha256) is rejected fail-closed."""
    import json
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_req_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"dummy tar content")

    # Missing tarSha256
    payload = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": "sha256:" + "b" * 64,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Missing required field in Evidence JSON: tarSha256" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_invalid_schema_version_rejected():
    """Verify that Evidence JSON with unsupported schemaVersion is rejected fail-closed."""
    import json
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_ver_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"dummy tar content")

    payload = {
        "schemaVersion": "2.0.0",
        "codeSha": "a" * 40,
        "imageId": "sha256:" + "b" * 64,
        "tarSha256": "c" * 64,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Unsupported schemaVersion: 2.0.0" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_tar_sha256_mismatch_rejected():
    """Verify that a tarball whose actual sha256 does NOT match Evidence tarSha256 is rejected fail-closed."""
    import json
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_tarmismatch_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"actual tar content")

    payload = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": "sha256:" + "b" * 64,
        "tarSha256": "0" * 64,  # wrong sha256
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Release tarball SHA-256 mismatch (fail-closed)" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_loaded_id_mismatch_rejected():
    """Verify that if loaded image inspect .Id does NOT match Evidence imageId, load script fails closed."""
    import json, hashlib
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_idmismatch_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"

    tar_bytes = b"sample tar payload"
    tar_file.write_bytes(tar_bytes)
    actual_tar_sha256 = hashlib.sha256(tar_bytes).hexdigest()

    expected_image_id = "sha256:" + "e" * 64
    actual_loaded_id = "sha256:" + "f" * 64

    docker_stub = f"""#!/usr/bin/env bash
if [[ "$1" == "load" ]]; then
    echo "Loaded image ID: {actual_loaded_id}"
    exit 0
elif [[ "$1" == "image" && "$2" == "inspect" ]]; then
    echo "{actual_loaded_id}"
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    payload = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": expected_image_id,
        "tarSha256": actual_tar_sha256,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    bash "{script_posix}" --evidence "{to_posix_path(ev_file)}" --tar "{to_posix_path(tar_file)}"
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Loaded image config .Id mismatch (fail-closed)" in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_verify_only_success():
    """Verify that when evidence, tar sha256, and inspect .Id match, --verify-only succeeds without invoking portal-up.sh."""
    import json, hashlib
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_load_rel_verifyonly_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"

    tar_bytes = b"valid tar payload"
    tar_file.write_bytes(tar_bytes)
    actual_tar_sha256 = hashlib.sha256(tar_bytes).hexdigest()

    expected_image_id = "sha256:" + "c" * 64

    docker_stub = f"""#!/usr/bin/env bash
if [[ "$1" == "load" ]]; then
    echo "Loaded image ID: {expected_image_id}"
    exit 0
elif [[ "$1" == "image" && "$2" == "inspect" ]]; then
    echo "{expected_image_id}"
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    payload = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": expected_image_id,
        "tarSha256": actual_tar_sha256,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }
    ev_file.write_text(json.dumps(payload), encoding="utf-8")

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    bash "{script_posix}" --evidence "{to_posix_path(ev_file)}" --tar "{to_posix_path(tar_file)}" --verify-only
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"Expected verify-only success, got {res.returncode}: {res.stderr}"
    assert "Release verification and image load succeeded" in res.stdout
    assert "Loaded image config .Id verified successfully" in res.stdout
    shutil.rmtree(temp_dir, ignore_errors=True)
# =========================================================================
# 11. Claude r6 & Codex r6 Comprehensive Behavioral Tests
# =========================================================================

def test_behavioral_image_id_invalid_format_rejected(pki_test_env):
    """(Claude r6 L1) Verify that an invalid PORTAL_IMAGE_ID format is rejected fail-closed, killing regex relaxations."""
    # 1. Missing prefix sha256:
    res1 = run_pki_func(pki_test_env, "validate_image_and_id", {"PORTAL_IMAGE_ID": "a" * 64})
    assert res1.returncode == 1
    assert "PORTAL_IMAGE_ID must be a valid 64-hex sha256 Docker config image ID" in res1.stderr

    # 2. Too short
    res2 = run_pki_func(pki_test_env, "validate_image_and_id", {"PORTAL_IMAGE_ID": "sha256:1234"})
    assert res2.returncode == 1
    assert "PORTAL_IMAGE_ID must be a valid 64-hex sha256 Docker config image ID" in res2.stderr

    # 3. Non-hex characters
    res3 = run_pki_func(pki_test_env, "validate_image_and_id", {"PORTAL_IMAGE_ID": "sha256:" + "z" * 64})
    assert res3.returncode == 1
    assert "PORTAL_IMAGE_ID must be a valid 64-hex sha256 Docker config image ID" in res3.stderr


def test_behavioral_preflight_port_check_self_excluded():
    """(Claude r6 M1) Verify that 12-char docker ps ID matching inspect ID excludes self from port conflict."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_port_self_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    state_dir = temp_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    short_id = "123456789012"
    full_id = short_id + "abcdef0123456789" * 3

    # Fake docker: inspect returns full_id, docker ps returns short_id
    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *Id* ]]; then
        echo "{full_id}"
    else
        echo "saintvision-portal"
    fi
    exit 0
elif [[ "$cmd" == "ps" && "$*" == *"--filter publish=80"* ]]; then
    echo "{short_id}"
    exit 0
elif [[ "$cmd" == "ps" && "$*" == *"--filter publish=443"* ]]; then
    echo "{short_id}"
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    export PORTAL_UPSTREAM_CP_HOST="cp.sv.lan:443"
    export PORTAL_UID=1000
    export PORTAL_GID=1000
    export PORTAL_KEY_FILE="/nonexistent/key.pem"
    export PORTAL_STATE_DIR="{to_posix_path(state_dir)}"
    source "{to_posix_path(PORTAL_UP_SH)}"
    HTTP_PORT=80
    HTTPS_PORT=443
    PORTAL_INSTANCE="main"
    CONTAINER_NAME="saintvision-portal"
    validate_environment
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, f"Expected self to be excluded from port conflict, got {res.returncode}: {res.stderr}"
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_preflight_port_check_foreign_occupant_rejected():
    """(Claude r6 M1) Verify that an external container occupying HTTP or HTTPS port is rejected fail-closed."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_port_foreign_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    state_dir = temp_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    self_full_id = "111111111111" + "a" * 52
    foreign_short_id = "999999999999"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *Id* ]]; then
        echo "{self_full_id}"
    elif [[ "$fmt" == *Name* ]]; then
        echo "/foreign-proxy-container"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "ps" && "$*" == *"--filter publish=80"* ]]; then
    echo "{foreign_short_id}"
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    export PORTAL_UPSTREAM_CP_HOST="cp.sv.lan:443"
    export PORTAL_UID=1000
    export PORTAL_GID=1000
    export PORTAL_KEY_FILE="/nonexistent/key.pem"
    export PORTAL_STATE_DIR="{to_posix_path(state_dir)}"
    source "{to_posix_path(PORTAL_UP_SH)}"
    HTTP_PORT=80
    HTTPS_PORT=443
    PORTAL_INSTANCE="main"
    CONTAINER_NAME="saintvision-portal"
    validate_environment
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1, f"Expected foreign occupant to fail closed, got {res.returncode}: {res.stdout}"
    assert "ERROR: HTTP port 80 is already occupied by container 'foreign-proxy-container'." in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_stale_cleanup_retains_recent_backup_and_prunes_older():
    """(Claude r6 M2 & r7 M1) Verify that production stale cleanup retains at most 1 recent backup and prunes older backups/unrelated containers."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_stale_cleanup_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            target="$1"
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    elif [[ "$fmt" == *Name* ]]; then
        if [[ "$target" == "id_older" ]]; then
            echo "/saintvision-portal-backup-abcdef"
        elif [[ "$target" == "id_unrelated" ]]; then
            echo "/saintvision-portal-unrelated"
        else
            echo "/saintvision-portal-backup-123456"
        fi
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "ps" && "$*" == *"-aq"* ]]; then
    # Return 3 exited containers: active backup (id_active), older backup (id_older), unrelated (id_unrelated)
    echo -e "id_active\\nid_older\\nid_unrelated"
    exit 0
elif [[ "$cmd" == "exec" ]]; then
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    swap_and_launch_production
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0
    assert "Preserving recent backup container 'saintvision-portal-backup-" in res.stderr
    assert "Pruning stale container 'saintvision-portal-backup-abcdef' (id_older)..." in res.stderr
    assert "Pruning stale container 'saintvision-portal-unrelated' (id_unrelated)..." in res.stderr

    calls = calls_log.read_text(encoding="utf-8").splitlines()
    assert any("rm id_older" in c for c in calls)
    assert any("rm id_unrelated" in c for c in calls)
    # Active backup must NEVER be pruned (Claude r7 M1)
    assert not any("rm id_active" in c for c in calls)
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_swap_trap_handler_triggers_rollback_and_exits():
    """(Claude r6 M3) Verify that trap_swap_handler calls rollback_production and terminates with exit 1."""
    bash_path = get_git_bash()
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_trap_test_"))
    bin_dir = temp_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    calls_log = temp_dir / "calls.log"

    docker_stub = f"""#!/usr/bin/env bash
cmd="$1"
shift
echo "docker $cmd $*" >> "{to_posix_path(calls_log)}"
if [[ "$cmd" == "container" && "$1" == "inspect" ]]; then
    exit 0
elif [[ "$cmd" == "inspect" ]]; then
    while [[ $# -gt 0 ]]; do
        if [[ "$1" == "--format" ]]; then
            fmt="$2"
            shift 2
        else
            shift
        fi
    done
    if [[ "$fmt" == *ai.saintvision.service* ]]; then
        echo "portal"
    elif [[ "$fmt" == *ai.saintvision.workload* ]]; then
        echo "intranet-portal"
    elif [[ "$fmt" == *ai.saintvision.node* ]]; then
        echo "node2"
    elif [[ "$fmt" == *ai.saintvision.instance* ]]; then
        echo "main"
    elif [[ "$fmt" == *State.Running* ]]; then
        echo "true"
    elif [[ "$fmt" == *RestartCount* ]]; then
        echo "0"
    else
        echo "true"
    fi
    exit 0
elif [[ "$cmd" == "rename" || "$cmd" == "stop" || "$cmd" == "rm" || "$cmd" == "start" ]]; then
    exit 0
elif [[ "$cmd" == "run" ]]; then
    # Send SIGTERM to the parent bash process running swap_and_launch_production
    kill -TERM $PPID
    sleep 1
    exit 0
fi
exit 0
"""
    (bin_dir / "docker").write_text(docker_stub.replace("\r\n", "\n"), encoding="utf-8")
    os.chmod(bin_dir / "docker", 0o755)

    test_sh = f"""
    export PATH="{to_posix_path(bin_dir)}:$PATH"
    if [[ "$(command -v docker)" != "{to_posix_path(bin_dir)}/docker" ]]; then
        echo "ERROR: docker resolved to $(command -v docker) instead of stub" >&2
        exit 99
    fi
    source "{to_posix_path(PORTAL_UP_SH)}"
    TARGET_IMAGE="sha256:0000000000000000000000000000000000000000000000000000000000000000"
    CERT_FILE_ABS="/tmp/cert"
    KEY_FILE_ABS="/tmp/key"
    CA_BUNDLE_ABS="/tmp/ca"
    UPSTREAM_CONF_ABS="/tmp/up"
    swap_and_launch_production
    """
    res = subprocess.run([bash_path, "-c", test_sh], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1, f"Expected trap to exit 1, got {res.returncode}"
    assert "Received signal during production swap/launch. Initiating rollback..." in res.stderr
    assert "Restoring previous production container from" in res.stderr
    assert "Rollback complete: previous production container restored and running." in res.stderr
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_rejects_shell_injection_payloads():
    """(Codex r7 F1) Verify that quote, newline, command substitution, and semicolon payloads fail-closed with 0 side effects."""
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_rel_inject_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"dummy tar content")
    marker_file = temp_dir / "injected_marker.txt"

    payloads = [
        "'; touch " + to_posix_path(marker_file) + "; #",
        "run123; touch " + to_posix_path(marker_file),
        "run$(touch " + to_posix_path(marker_file) + ")",
        "run123\ntouch " + to_posix_path(marker_file),
    ]

    for p in payloads:
        if marker_file.exists():
            marker_file.unlink()

        # 1. Inject into buildRunId
        ev_data = {
            "schemaVersion": "1.0.0",
            "codeSha": "a" * 40,
            "imageId": "sha256:" + "b" * 64,
            "tarSha256": "c" * 64,
            "buildRunId": p,
            "buildTimestamp": "2026-09-30T04:00:00Z",
        }
        ev_file.write_text(json.dumps(ev_data), encoding="utf-8")
        res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                             capture_output=True, text=True, encoding="utf-8")
        assert res.returncode == 1, f"Expected injection payload '{p}' to fail closed, got rc {res.returncode}"
        assert not marker_file.exists(), f"Security vulnerability: marker file created by injection payload: {p}"

        # 2. Inject into unknown field (such as removed imageTag)
        ev_data2 = {
            "schemaVersion": "1.0.0",
            "codeSha": "a" * 40,
            "imageId": "sha256:" + "b" * 64,
            "tarSha256": "c" * 64,
            "buildRunId": "run123",
            "buildTimestamp": "2026-09-30T04:00:00Z",
            "imageTag": p,
        }
        ev_file.write_text(json.dumps(ev_data2), encoding="utf-8")
        res2 = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                              capture_output=True, text=True, encoding="utf-8")
        assert res2.returncode == 1, f"Expected imageTag payload '{p}' to fail closed, got rc {res2.returncode}"
        assert not marker_file.exists(), f"Security vulnerability: marker file created by imageTag payload: {p}"
        assert "Unknown field(s) in Evidence JSON" in res2.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_behavioral_load_release_rejects_schema_invalid_types():
    """(Codex r7 F2) Verify that non-string types, malformed timestamps, and schema violations are rejected fail-closed."""
    bash_path = get_git_bash()
    script_posix = to_posix_path(PORTAL_LOAD_RELEASE_SH)
    temp_dir = Path(tempfile.mkdtemp(prefix="sv_rel_schema_types_"))
    ev_file = temp_dir / "evidence.json"
    tar_file = temp_dir / "image.tar"
    tar_file.write_bytes(b"dummy tar content")

    valid_base = {
        "schemaVersion": "1.0.0",
        "codeSha": "a" * 40,
        "imageId": "sha256:" + "b" * 64,
        "tarSha256": "c" * 64,
        "buildRunId": "12345",
        "buildTimestamp": "2026-09-30T04:00:00Z",
    }

    # 1. Integer buildRunId
    bad_data = dict(valid_base)
    bad_data["buildRunId"] = 12345
    ev_file.write_text(json.dumps(bad_data), encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Field 'buildRunId' must be of type string, got int" in res.stderr

    # 2. Object buildTimestamp
    bad_data = dict(valid_base)
    bad_data["buildTimestamp"] = {"not": "a string"}
    ev_file.write_text(json.dumps(bad_data), encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Field 'buildTimestamp' must be of type string, got dict" in res.stderr

    # 3. Invalid date-time format for buildTimestamp
    bad_data = dict(valid_base)
    bad_data["buildTimestamp"] = "invalid-date-format"
    ev_file.write_text(json.dumps(bad_data), encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Invalid date-time format for buildTimestamp" in res.stderr

    # 4. Integer codeSha
    bad_data = dict(valid_base)
    bad_data["codeSha"] = 1234567890
    ev_file.write_text(json.dumps(bad_data), encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Field 'codeSha' must be of type string, got int" in res.stderr

    # 5. Unknown field imageTag rejected
    bad_data = dict(valid_base)
    bad_data["imageTag"] = "saintvision-portal:test"
    ev_file.write_text(json.dumps(bad_data), encoding="utf-8")
    res = subprocess.run([bash_path, script_posix, "--evidence", to_posix_path(ev_file), "--tar", to_posix_path(tar_file)],
                         capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 1
    assert "Unknown field(s) in Evidence JSON (fail-closed)" in res.stderr

    shutil.rmtree(temp_dir, ignore_errors=True)
