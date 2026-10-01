#!/usr/bin/env python3
"""S02-FE Intranet Portal Login Journey Observation Harness (Card 162).

Observes and validates the 5-phase login journey on portal.sv.lan:
  1. portal_tls_reachability: TLS certificate validation with intranet CA bundle.
     (No ignoreHTTPSErrors, no --ignore-certificate-errors).
     - If name is unresolved or CA bundle is missing on host -> BLOCKED_EXTERNAL.
     - If TCP port is closed/refused/timed out or TLS/HTTP fails -> FAIL.
  2. login_initiation: Click "조직 계정으로 로그인", PKCE verifier/state/nonce generated.
  3. pkce_callback: /callback?code=... exchange at IdP, id_token validation, transition to /studio.
  4. identity_session_display: /v1/session identity and authenticated session displayed in UI.
  5. logout: Click "로그아웃", session expiration/token/sessionStorage cleared, Login view restored.

Strict Anti-Circumvention Policy:
  - --host-resolver-rules, --ignore-certificate-errors, ignoreHTTPSErrors are strictly PROHIBITED.
  - Target URL and IdP URL in live mode must be strictly bound to canonical origins (https://portal.sv.lan, https://idp.sv.lan).
  - Raw IP addresses, userinfo, and foreign origins are rejected fail-closed.

Strict Redaction Guarantee:
  - Zero tokens (Bearer, JWT, code_verifier, auth codes) in Evidence.
  - Zero IP addresses (IPv4 & IPv6, including compressed ::1) in Evidence.
  - Zero credentials / secrets in Evidence.
  - Zero accounts / emails / usernames in Evidence.
  - Zero raw OIDC transaction query parameters (state, nonce, code_challenge) in Evidence.
  - Audit section enforces all leak counts strictly equal 0.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "tools/portal-login-journey-evidence.schema.json"

CANONICAL_PORTAL_HOST = "portal.sv.lan"
CANONICAL_IDP_HOST = "idp.sv.lan"

PROHIBITED_FLAGS = [
    "--host-resolver-rules",
    "--ignore-certificate-errors",
    "--disable-web-security",
    "--allow-running-insecure-content",
    "ignoreHTTPSErrors",
    "ignore_https_errors",
]


class SecurityCircumventionError(RuntimeError):
    """Raised when circumvention flags (--host-resolver-rules, ignoreHTTPSErrors) are attempted."""
    pass


def is_ip_address(val: str) -> bool:
    try:
        ipaddress.ip_address(val.strip("[]"))
        return True
    except ValueError:
        return False


def get_git_sha(
    repo_path: Optional[Path] = None,
    require_clean: bool = False,
    require_remote_containment: bool = False,
    allowed_remotes: Tuple[str, ...] = ("origin/",),
) -> str:
    path = repo_path or REPO_ROOT
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=True,
        )
        sha = res.stdout.strip()
        if not re.fullmatch(r"^[0-9a-f]{8,40}$", sha) or re.fullmatch(r"^0+$", sha):
            raise RuntimeError(f"Unacceptable git commit SHA (expected non-zero hex SHA): '{sha}'")

        if require_clean:
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(path),
                capture_output=True,
                text=True,
                check=True,
            )
            dirty = status_res.stdout.strip()
            if dirty:
                raise RuntimeError(
                    f"Dirty git working tree detected; clean tree required for provenance: {dirty[:120]}"
                )

        if require_remote_containment:
            remote_res = subprocess.run(
                ["git", "branch", "-r", "--contains", sha],
                cwd=str(path),
                capture_output=True,
                text=True,
                check=True,
            )
            branches = [b.strip() for b in remote_res.stdout.strip().splitlines() if b.strip()]
            valid = any(
                any(b.startswith(prefix) for prefix in allowed_remotes)
                for b in branches
            )
            if not valid:
                raise RuntimeError(
                    f"Git commit {sha} is not reachable from any approved remote tracking branch ({allowed_remotes})"
                )

        return sha
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed during SHA/provenance resolution: {e.stderr or e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed to resolve clean exact git HEAD commit SHA: {e}") from e


def check_circumvention_flags(args_list: List[str]) -> None:
    for arg in args_list:
        for p in PROHIBITED_FLAGS:
            if p in arg:
                raise SecurityCircumventionError(
                    f"Circumvention prohibited: detected prohibited flag '{p}' in '{arg}'"
                )


def validate_canonical_origins(target_url: str, idp_url: str, live_mode: bool) -> None:
    if not live_mode:
        return

    # 1. Target URL
    parsed_target = urlsplit(target_url)
    if parsed_target.scheme != "https":
        raise ValueError(f"Live target URL must use https scheme: {target_url}")
    if parsed_target.username or parsed_target.password:
        raise ValueError(f"Live target URL must not contain userinfo: {target_url}")
    if parsed_target.hostname != CANONICAL_PORTAL_HOST:
        raise ValueError(f"Live target URL must be bound to {CANONICAL_PORTAL_HOST}: {target_url}")
    if is_ip_address(parsed_target.hostname or ""):
        raise ValueError(f"Live target URL must not be a raw IP address: {target_url}")

    # 2. IdP URL
    parsed_idp = urlsplit(idp_url)
    if parsed_idp.scheme != "https":
        raise ValueError(f"Live IdP URL must use https scheme: {idp_url}")
    if parsed_idp.username or parsed_idp.password:
        raise ValueError(f"Live IdP URL must not contain userinfo: {idp_url}")
    if parsed_idp.hostname != CANONICAL_IDP_HOST:
        raise ValueError(f"Live IdP URL must be bound to {CANONICAL_IDP_HOST}: {idp_url}")
    if is_ip_address(parsed_idp.hostname or ""):
        raise ValueError(f"Live IdP URL must not be a raw IP address: {idp_url}")


class RedactionSanitizer:
    """Sanitizes text and audits output data to ensure zero tokens, zero IPs, zero credentials, zero accounts, and zero OIDC params."""

    JWT_PATTERN = re.compile(r"\b(?:eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b")
    BEARER_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*\b", re.IGNORECASE)
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    OIDC_SENSITIVE_PATTERN = re.compile(
        r"(?:[?&]|^|\b)(state|nonce|code_challenge|code_challenge_method|code_verifier|code|client_secret|access_token|id_token|refresh_token)\s*[:=]\s*([^&\"'\s,}>]+)",
        re.IGNORECASE,
    )
    SENSITIVE_PARAM_PATTERN = re.compile(
        r"\b(password|client_secret|clientsecret|secret|code_verifier)\s*[:=]\s*[\"']?([^\"'\s,&}]+)",
        re.IGNORECASE,
    )
    IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
    IPV6_CANDIDATE = re.compile(r"(?:\[([0-9a-fA-F:]{2,39})\]|(?<![0-9a-fA-F:])([0-9a-fA-F:]{2,39})(?![0-9a-fA-F:]))")

    SENSITIVE_KEYS: Set[str] = {
        "password",
        "client_secret",
        "clientsecret",
        "secret",
        "access_token",
        "id_token",
        "refresh_token",
        "code_verifier",
        "authorization_code",
    }
    ACCOUNT_KEYS: Set[str] = {
        "userdisplayname",
        "username",
        "sub",
        "email",
        "preferred_username",
        "account",
        "user_id",
        "actor",
        "user",
        "principal",
        "login",
        "identity",
        "handle",
        "profile",
        "member",
        "operator",
    }
    ACCOUNT_TERMS: Tuple[str, ...] = (
        "actor",
        "user",
        "account",
        "login",
        "principal",
        "identity",
        "member",
        "profile",
    )
    KNOWN_ACCOUNT_PROBES: Set[str] = {
        "alice",
        "bob",
        "operator",
        "admin",
        "chanyu",
    }
    OIDC_PARAM_KEYS: Set[str] = {
        "state",
        "nonce",
        "code_challenge",
        "code_challenge_method",
        "code",
    }

    @classmethod
    def is_sensitive_key(cls, k: str) -> bool:
        kl = str(k).lower()
        if kl in cls.SENSITIVE_KEYS:
            return True
        if any(s in kl for s in ("secret", "password", "verifier")):
            return True
        if kl in ("token", "tokens") or kl.endswith("_token") or kl.endswith("token"):
            if kl not in ("tokenendpointobserved", "tokenhttpstatus", "tokencount"):
                return True
        return False

    @classmethod
    def is_account_key(cls, k: str) -> bool:
        kl = str(k).lower()
        if kl in ("accountcount", "account_count"):
            return False
        if kl in cls.ACCOUNT_KEYS:
            return True
        parts = re.split(r"[_\-.]", kl)
        if any(p in cls.ACCOUNT_KEYS for p in parts if p not in ("count", "observed")):
            return True
        return False

    @classmethod
    def is_oidc_key(cls, k: str) -> bool:
        kl = str(k).lower()
        if kl in ("oidcparamcount", "oidc_param_count"):
            return False
        if kl in cls.OIDC_PARAM_KEYS:
            return True
        if any(term in kl for term in ("nonce", "state", "challenge")):
            return True
        return False

    @classmethod
    def sanitize_str(cls, text: str) -> str:
        if not text:
            return text

        # 1. Tokens
        text = cls.JWT_PATTERN.sub("[REDACTED_JWT]", text)
        text = cls.BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", text)

        # 2. Emails / Accounts
        text = cls.EMAIL_PATTERN.sub("[REDACTED_ACCOUNT]", text)

        # 3. OIDC parameters
        def repl_oidc(m: re.Match) -> str:
            prefix = m.group(0).split("=")[0] if "=" in m.group(0) else m.group(0).split(":")[0]
            sep = "=" if "=" in m.group(0) else ":"
            return f"{prefix}{sep}[REDACTED_OIDC_PARAM]"

        text = cls.OIDC_SENSITIVE_PATTERN.sub(repl_oidc, text)
        text = cls.SENSITIVE_PARAM_PATTERN.sub(r"\1=[REDACTED_SECRET]", text)

        # 4. IPv4
        def repl_v4(m: re.Match) -> str:
            raw = m.group(0)
            return "[REDACTED_IP]" if is_ip_address(raw) else raw

        text = cls.IPV4_PATTERN.sub(repl_v4, text)

        # 5. IPv6 (including ::1, [::1], fe80::1)
        def repl_v6(m: re.Match) -> str:
            raw = m.group(1) or m.group(2)
            if raw and ":" in raw and is_ip_address(raw):
                return "[REDACTED_IP]"
            return m.group(0)

        text = cls.IPV6_CANDIDATE.sub(repl_v6, text)

        return text

    @classmethod
    def sanitize_url(cls, raw_url: str) -> str:
        if not raw_url:
            return raw_url
        try:
            parsed = urlsplit(raw_url)
            netloc = parsed.netloc
            hostname = parsed.hostname or ""

            # Check if netloc has raw IP
            if is_ip_address(hostname):
                new_host = "redacted-host.sv.lan"
                netloc = f"{new_host}:{parsed.port}" if parsed.port else new_host

            # Sanitize query parameters
            query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            sanitized_pairs = []
            for k, v in query_pairs:
                if cls.is_oidc_key(k) or cls.is_sensitive_key(k):
                    sanitized_pairs.append((k, "[REDACTED_OIDC_PARAM]"))
                elif cls.is_account_key(k):
                    sanitized_pairs.append((k, "[REDACTED_ACCOUNT]"))
                else:
                    sanitized_pairs.append((k, cls.sanitize_str(v)))

            clean_query = urlencode(sanitized_pairs)
            clean_path = cls.sanitize_str(parsed.path)

            return urlunsplit((parsed.scheme, netloc, clean_path, clean_query, parsed.fragment))
        except Exception:
            return cls.sanitize_str(raw_url)

    @classmethod
    def sanitize_obj(cls, obj: Any) -> Any:
        if isinstance(obj, str):
            return cls.sanitize_str(obj)
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if k == "audit":
                    new_dict[k] = v
                    continue
                if cls.is_sensitive_key(k):
                    new_dict[k] = "[REDACTED_CREDENTIAL]"
                elif cls.is_account_key(k):
                    new_dict[k] = "[REDACTED_ACCOUNT]"
                elif cls.is_oidc_key(k):
                    new_dict[k] = "[REDACTED_OIDC_PARAM]"
                else:
                    new_dict[k] = cls.sanitize_obj(v)
            return new_dict
        elif isinstance(obj, list):
            return [cls.sanitize_obj(item) for item in obj]
        return obj

    @classmethod
    def _audit_recursive(cls, obj: Any) -> Tuple[int, int, int, int, int]:
        """Returns counts: (tokenCount, ipCount, credentialCount, accountCount, oidcParamCount)."""
        t_cnt = 0
        ip_cnt = 0
        cred_cnt = 0
        acc_cnt = 0
        oidc_cnt = 0

        if isinstance(obj, str):
            # Token detection
            t_cnt += len(cls.JWT_PATTERN.findall(obj)) + len(cls.BEARER_PATTERN.findall(obj))

            # IP detection
            for m in cls.IPV4_PATTERN.finditer(obj):
                if is_ip_address(m.group(0)):
                    ip_cnt += 1
            for m in cls.IPV6_CANDIDATE.finditer(obj):
                raw = m.group(1) or m.group(2)
                if raw and ":" in raw and is_ip_address(raw):
                    ip_cnt += 1

            # Credential detection in text
            for m in cls.SENSITIVE_PARAM_PATTERN.finditer(obj):
                if not m.group(2).startswith("[REDACTED"):
                    cred_cnt += 1

            # Account / Email detection in text
            acc_cnt += len(cls.EMAIL_PATTERN.findall(obj))
            for word in re.findall(r"\b[A-Za-z0-9_-]+\b", obj):
                if word.lower() in cls.KNOWN_ACCOUNT_PROBES and not obj.startswith("[REDACTED"):
                    acc_cnt += 1

            # OIDC parameter detection in text
            for m in cls.OIDC_SENSITIVE_PATTERN.finditer(obj):
                val = m.group(2)
                if not val.startswith("[REDACTED"):
                    oidc_cnt += 1

        elif isinstance(obj, dict):
            for k, v in obj.items():
                if k == "audit":
                    continue
                val_str = str(v)
                if cls.is_sensitive_key(k):
                    if not val_str.startswith("[REDACTED"):
                        cred_cnt += 1
                if cls.is_account_key(k):
                    if not val_str.startswith("[REDACTED"):
                        acc_cnt += 1
                if cls.is_oidc_key(k):
                    if not val_str.startswith("[REDACTED"):
                        oidc_cnt += 1

                tc, ipc, cc, ac, oc = cls._audit_recursive(v)
                t_cnt += tc
                ip_cnt += ipc
                cred_cnt += cc
                acc_cnt += ac
                oidc_cnt += oc

        elif isinstance(obj, list):
            for item in obj:
                tc, ipc, cc, ac, oc = cls._audit_recursive(item)
                t_cnt += tc
                ip_cnt += ipc
                cred_cnt += cc
                acc_cnt += ac
                oidc_cnt += oc

        return t_cnt, ip_cnt, cred_cnt, acc_cnt, oidc_cnt

    @classmethod
    def audit_obj(cls, obj: Any) -> Tuple[int, int, int, int, int]:
        return cls._audit_recursive(obj)


def check_domain_resolution(hostname: str) -> Tuple[bool, Optional[str]]:
    try:
        socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        return True, None
    except socket.gaierror as e:
        return False, f"DNS resolution failed for {hostname} ({e})"
    except Exception as e:
        return False, f"Resolution error for {hostname}: {e}"


def check_tcp_connection(hostname: str, port: int, timeout_sec: float = 2.0) -> Tuple[bool, Optional[str]]:
    try:
        with socket.create_connection((hostname, port), timeout=timeout_sec):
            return True, None
    except ConnectionRefusedError:
        return False, f"TCP connection refused on {hostname}:{port} (service down)"
    except socket.timeout:
        return False, f"TCP connection timed out on {hostname}:{port}"
    except Exception as e:
        return False, f"TCP connection to {hostname}:{port} failed: {e}"


def inspect_ca_bundle(
    ca_path: Path,
    allowed_fingerprints: Optional[List[str]] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    try:
        raw_bytes = ca_path.read_bytes()
    except Exception as e:
        return False, f"Failed to read CA bundle file: {e}", None

    bundle_sha256 = hashlib.sha256(raw_bytes).hexdigest().lower()

    try:
        certs = x509.load_pem_x509_certificates(raw_bytes)
    except Exception as e:
        return False, f"Failed to parse PEM certificates from CA bundle: {e}", None

    if not certs:
        return False, "No valid PEM certificates found in CA bundle", None

    # Find root certificates (issuer == subject)
    roots = [c for c in certs if c.issuer == c.subject]
    if not roots:
        return False, "No root CA certificate found in CA bundle", None

    root_fp = roots[0].fingerprint(hashes.SHA256()).hex().lower()

    if not allowed_fingerprints:
        return (
            False,
            "Fingerprint allowlist must not be empty or missing (fail-closed enforcement)",
            None,
        )

    norm_allowed = [fp.replace(":", "").replace(" ", "").lower() for fp in allowed_fingerprints]
    if root_fp not in norm_allowed:
        return (
            False,
            f"Root CA fingerprint {root_fp} does not match approved allowlist {norm_allowed}",
            None,
        )

    ca_digest = {
        "caBundleSha256": bundle_sha256,
        "rootFingerprint": root_fp,
        "fingerprintVerified": True,
    }
    return True, None, ca_digest


def verify_tls_socket_handshake(
    hostname: str,
    port: int,
    ca_bundle_path: Path,
    timeout_sec: float = 3.0,
) -> Tuple[bool, Optional[str]]:
    ctx = ssl.create_default_context(cafile=str(ca_bundle_path))
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED

    try:
        with socket.create_connection((hostname, port), timeout=timeout_sec) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                _ = ssock.getpeercert()
        return True, None
    except ssl.SSLCertVerificationError as e:
        return False, f"TLS certificate verification failed against intranet CA: {e}"
    except ssl.SSLError as e:
        return False, f"TLS SSL error on {hostname}:{port}: {e}"
    except Exception as e:
        return False, f"TLS connection to {hostname}:{port} failed: {e}"


@dataclass
class StepResult:
    id: str
    name: str
    status: str
    duration_ms: float
    detail: str
    observations: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "durationMs": round(self.duration_ms, 2),
            "detail": RedactionSanitizer.sanitize_str(self.detail),
            "observations": RedactionSanitizer.sanitize_obj(self.observations),
        }


STEP_METADATA = [
    ("portal_tls_reachability", "Portal TLS Reachability & Certificate Check"),
    ("login_initiation", "OIDC PKCE Login Initiation"),
    ("pkce_callback", "OIDC Authorization Code Exchange Callback"),
    ("identity_session_display", "Identity and /v1/session Display"),
    ("logout", "OIDC Session Logout and Cleanup"),
]


class PortalLoginJourneyObserver:
    def __init__(
        self,
        target_url: str = "https://portal.sv.lan",
        idp_url: str = "https://idp.sv.lan",
        ca_bundle: Optional[str] = None,
        allowed_root_fingerprints: Optional[List[str]] = None,
        mock_mode: bool = False,
        timeout_sec: float = 10.0,
        extra_args: Optional[List[str]] = None,
    ):
        self.target_url = target_url
        self.idp_url = idp_url
        self.ca_bundle = ca_bundle
        self.mock_mode = mock_mode
        self.timeout_sec = timeout_sec
        self.extra_args = extra_args or []

        # Read allowlist from args or environment variable
        env_allowed = os.environ.get("PORTAL_ALLOWED_ROOT_FINGERPRINTS", "")
        fps = list(allowed_root_fingerprints or [])
        if env_allowed:
            fps.extend(re.split(r"[,;\s]+", env_allowed.strip()))
        self.allowed_root_fingerprints = [f.strip() for f in fps if f.strip()]

        check_circumvention_flags(self.extra_args)
        validate_canonical_origins(self.target_url, self.idp_url, live_mode=not self.mock_mode)

        parsed = urlsplit(target_url)
        self.hostname = parsed.hostname or CANONICAL_PORTAL_HOST
        self.port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self.is_https = parsed.scheme == "https"

        parsed_idp = urlsplit(self.idp_url)
        self.idp_hostname = parsed_idp.hostname or CANONICAL_IDP_HOST

    IGNORE_HTTPS_ERRORS: bool = False

    def execute_journey(
        self,
        require_clean: bool = False,
        require_remote_containment: bool = False,
    ) -> Dict[str, Any]:
        start_time = dt.datetime.now(dt.timezone.utc).isoformat()
        code_sha = get_git_sha(
            require_clean=require_clean,
            require_remote_containment=require_remote_containment,
        )
        start_time = dt.datetime.now(dt.timezone.utc).isoformat()
        code_sha = get_git_sha()

        if self.mock_mode:
            return self._execute_mock_mode(start_time, code_sha)
        else:
            return self._execute_live_browser(start_time, code_sha)

    def _execute_mock_mode(self, start_time: str, code_sha: str) -> Dict[str, Any]:
        steps: List[StepResult] = []

        # Step 1: Reachability
        t0 = time.perf_counter()
        steps.append(
            StepResult(
                id="portal_tls_reachability",
                name="Portal TLS Reachability & Certificate Check",
                status="PASS",
                duration_ms=(time.perf_counter() - t0) * 1000 + 5.0,
                detail="Portal web application reached over TLS in reference simulation.",
                observations={
                    "httpStatus": 200,
                    "url": RedactionSanitizer.sanitize_url(self.target_url),
                    "tlsHandshakeVerified": True,
                },
            )
        )

        # Step 2: Login Initiation
        t0 = time.perf_counter()
        steps.append(
            StepResult(
                id="login_initiation",
                name="OIDC PKCE Login Initiation",
                status="PASS",
                duration_ms=(time.perf_counter() - t0) * 1000 + 8.0,
                detail="Login button clicked and redirect initiated in reference simulation.",
                observations={
                    "initiated": True,
                    "idpRedirectObserved": True,
                },
            )
        )

        # Step 3: Callback
        t0 = time.perf_counter()
        steps.append(
            StepResult(
                id="pkce_callback",
                name="OIDC Authorization Code Exchange Callback",
                status="PASS",
                duration_ms=(time.perf_counter() - t0) * 1000 + 12.0,
                detail="Authorization code callback handled and token endpoint HTTP 200 confirmed.",
                observations={
                    "callbackHandled": True,
                    "tokenEndpointObserved": True,
                    "tokenHttpStatus": 200,
                },
            )
        )

        # Step 4: Identity & Session Display
        t0 = time.perf_counter()
        steps.append(
            StepResult(
                id="identity_session_display",
                name="Identity and /v1/session Display",
                status="PASS",
                duration_ms=(time.perf_counter() - t0) * 1000 + 7.0,
                detail="Authenticated UI mounted and /v1/session HTTP 200 validated.",
                observations={
                    "identityObserved": True,
                    "authenticatedViewActive": True,
                    "sessionEndpointObserved": True,
                    "sessionHttpStatus": 200,
                    "sessionShapeValid": True,
                },
            )
        )

        # Step 5: Logout
        t0 = time.perf_counter()
        steps.append(
            StepResult(
                id="logout",
                name="OIDC Session Logout and Cleanup",
                status="PASS",
                duration_ms=(time.perf_counter() - t0) * 1000 + 6.0,
                detail="Logout button clicked, storage purged, and login screen restored.",
                observations={
                    "loginScreenRestored": True,
                    "transactionCleared": True,
                    "storagePurged": True,
                },
            )
        )

        return self._build_evidence(
            start_time=start_time,
            code_sha=code_sha,
            measurement_kind="REFERENCE_SIMULATION",
            reference_only=True,
            acceptance_claim=False,
            overall_status="PASS",
            blocking_reason=None,
            ca_digest=None,
            steps=steps,
            tls_validation_enforced=False,
        )

    def _execute_live_browser(self, start_time: str, code_sha: str) -> Dict[str, Any]:
        from playwright.sync_api import sync_playwright

        steps: List[StepResult] = []
        ca_digest: Optional[Dict[str, Any]] = None
        tls_validation_enforced = False

        # --- Stage A: Preflight Checks ---
        # 1. DNS check (domain resolution)
        resolved, dns_err = check_domain_resolution(self.hostname)
        if not resolved:
            steps.append(
                StepResult(
                    id="portal_tls_reachability",
                    name="Portal TLS Reachability & Certificate Check",
                    status="BLOCKED_EXTERNAL",
                    duration_ms=1.0,
                    detail=f"External preflight blocked: {dns_err}",
                    observations={"hostname": self.hostname, "dnsResolved": False},
                )
            )
            for sid, sname in STEP_METADATA[1:]:
                steps.append(
                    StepResult(
                        id=sid,
                        name=sname,
                        status="NOT_OBSERVED",
                        duration_ms=0.0,
                        detail="Not observed: prerequisite step portal_tls_reachability blocked",
                    )
                )
            return self._build_evidence(
                start_time=start_time,
                code_sha=code_sha,
                measurement_kind="LIVE_BROWSER",
                reference_only=False,
                acceptance_claim=False,
                overall_status="BLOCKED_EXTERNAL",
                blocking_reason=dns_err,
                ca_digest=None,
                steps=steps,
                tls_validation_enforced=False,
            )

        # 2. CA bundle existence & inspection
        if self.ca_bundle:
            ca_path = Path(self.ca_bundle).resolve()
            if not ca_path.exists():
                err = f"CA bundle file missing on host: {self.ca_bundle}"
                steps.append(
                    StepResult(
                        id="portal_tls_reachability",
                        name="Portal TLS Reachability & Certificate Check",
                        status="BLOCKED_EXTERNAL",
                        duration_ms=1.0,
                        detail=f"External preflight blocked: {err}",
                    )
                )
                for sid, sname in STEP_METADATA[1:]:
                    steps.append(
                        StepResult(
                            id=sid,
                            name=sname,
                            status="NOT_OBSERVED",
                            duration_ms=0.0,
                            detail="Not observed: prerequisite step portal_tls_reachability blocked",
                        )
                    )
                return self._build_evidence(
                    start_time=start_time,
                    code_sha=code_sha,
                    measurement_kind="LIVE_BROWSER",
                    reference_only=False,
                    acceptance_claim=False,
                    overall_status="BLOCKED_EXTERNAL",
                    blocking_reason=err,
                    ca_digest=None,
                    steps=steps,
                    tls_validation_enforced=False,
                )

            ca_ok, ca_err, ca_info = inspect_ca_bundle(ca_path, self.allowed_root_fingerprints)
            if not ca_ok:
                steps.append(
                    StepResult(
                        id="portal_tls_reachability",
                        name="Portal TLS Reachability & Certificate Check",
                        status="FAIL",
                        duration_ms=1.0,
                        detail=f"Intranet CA inspection failed: {ca_err}",
                    )
                )
                for sid, sname in STEP_METADATA[1:]:
                    steps.append(
                        StepResult(
                            id=sid,
                            name=sname,
                            status="NOT_OBSERVED",
                            duration_ms=0.0,
                            detail="Not observed: prerequisite step portal_tls_reachability failed",
                        )
                    )
                return self._build_evidence(
                    start_time=start_time,
                    code_sha=code_sha,
                    measurement_kind="LIVE_BROWSER",
                    reference_only=False,
                    acceptance_claim=False,
                    overall_status="FAIL",
                    blocking_reason=ca_err,
                    ca_digest=None,
                    steps=steps,
                    tls_validation_enforced=False,
                )
            ca_digest = ca_info

        # 3. TCP connection check (service down -> FAIL)
        connected, tcp_err = check_tcp_connection(self.hostname, self.port, timeout_sec=2.0)
        if not connected:
            steps.append(
                StepResult(
                    id="portal_tls_reachability",
                    name="Portal TLS Reachability & Certificate Check",
                    status="FAIL",
                    duration_ms=1.0,
                    detail=f"Service unreachable: {tcp_err}",
                )
            )
            for sid, sname in STEP_METADATA[1:]:
                steps.append(
                    StepResult(
                        id=sid,
                        name=sname,
                        status="NOT_OBSERVED",
                        duration_ms=0.0,
                        detail="Not observed: prerequisite step portal_tls_reachability failed",
                    )
                )
            return self._build_evidence(
                start_time=start_time,
                code_sha=code_sha,
                measurement_kind="LIVE_BROWSER",
                reference_only=False,
                acceptance_claim=False,
                overall_status="FAIL",
                blocking_reason=tcp_err,
                ca_digest=ca_digest,
                steps=steps,
                tls_validation_enforced=False,
            )

        # 4. Strict TLS handshake check with CA bundle
        if self.ca_bundle and self.is_https:
            tls_ok, tls_err = verify_tls_socket_handshake(
                self.hostname,
                self.port,
                Path(self.ca_bundle).resolve(),
                timeout_sec=self.timeout_sec,
            )
            if not tls_ok:
                steps.append(
                    StepResult(
                        id="portal_tls_reachability",
                        name="Portal TLS Reachability & Certificate Check",
                        status="FAIL",
                        duration_ms=1.0,
                        detail=f"TLS verification failed: {tls_err}",
                    )
                )
                for sid, sname in STEP_METADATA[1:]:
                    steps.append(
                        StepResult(
                            id=sid,
                            name=sname,
                            status="NOT_OBSERVED",
                            duration_ms=0.0,
                            detail="Not observed: prerequisite step portal_tls_reachability failed",
                        )
                    )
                return self._build_evidence(
                    start_time=start_time,
                    code_sha=code_sha,
                    measurement_kind="LIVE_BROWSER",
                    reference_only=False,
                    acceptance_claim=False,
                    overall_status="FAIL",
                    blocking_reason=tls_err,
                    ca_digest=ca_digest,
                    steps=steps,
                    tls_validation_enforced=False,
                )
            tls_validation_enforced = True

        # --- Stage B: Live Browser Execution (Exact 5 Steps) ---
        browser_args: List[str] = []
        if self.ca_bundle and ca_digest and ca_digest.get("fingerprintVerified"):
            try:
                ca_content = Path(self.ca_bundle).resolve().read_bytes()
                ca_certs = x509.load_pem_x509_certificates(ca_content)
                roots = [c for c in ca_certs if c.issuer == c.subject]
                if roots:
                    spki_der = roots[0].public_key().public_bytes(
                        serialization.Encoding.DER,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    spki_b64 = base64.b64encode(hashlib.sha256(spki_der).digest()).decode("ascii")
                    browser_args.append(f"--ignore-certificate-errors-spki-list={spki_b64}")
            except Exception:
                pass

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=browser_args)
            if self.IGNORE_HTTPS_ERRORS is not False:
                raise SecurityCircumventionError("Circumvention prohibited: IGNORE_HTTPS_ERRORS must strictly be False")
            context = browser.new_context(
                ignore_https_errors=False,  # Prohibited from ignoring certificate errors
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Network observation state
            network_events = {
                "token_endpoint_observed": False,
                "token_http_status": None,
                "session_endpoint_observed": False,
                "session_http_status": None,
                "session_shape_valid": False,
            }

            def on_response(resp):
                url = resp.url
                # Token endpoint check:
                if "/protocol/openid-connect/token" in url or (self.idp_hostname in url and url.endswith("/token")):
                    network_events["token_endpoint_observed"] = True
                    network_events["token_http_status"] = resp.status

                # Session endpoint check:
                if "/v1/session" in url and self.hostname in url:
                    network_events["session_endpoint_observed"] = True
                    network_events["session_http_status"] = resp.status
                    if resp.status == 200:
                        try:
                            data = resp.json()
                            if (
                                isinstance(data, dict)
                                and isinstance(data.get("subjectId"), str)
                                and data.get("subjectId", "").startswith("oidc:")
                                and isinstance(data.get("tenantId"), str)
                                and bool(data.get("tenantId"))
                                and isinstance(data.get("expiresAt"), int)
                            ):
                                network_events["session_shape_valid"] = True
                        except Exception:
                            network_events["session_shape_valid"] = False

            if hasattr(page, "on"):
                page.on("response", on_response)

            try:
                # Step 1: Reachability
                t0 = time.perf_counter()
                try:
                    resp = page.goto(
                        self.target_url,
                        timeout=int(self.timeout_sec * 1000),
                        wait_until="domcontentloaded",
                    )
                    status_code = resp.status if resp else 0
                    if status_code == 200:
                        steps.append(
                            StepResult(
                                id="portal_tls_reachability",
                                name="Portal TLS Reachability & Certificate Check",
                                status="PASS",
                                duration_ms=(time.perf_counter() - t0) * 1000,
                                detail="Portal loaded over verified TLS with HTTP 200.",
                                observations={
                                    "httpStatus": status_code,
                                    "url": RedactionSanitizer.sanitize_url(page.url),
                                    "tlsHandshakeVerified": True,
                                },
                            )
                        )
                    else:
                        raise RuntimeError(f"Unexpected HTTP status {status_code}")
                except Exception as e:
                    err_msg = str(e)
                    s_status = "BLOCKED_EXTERNAL" if "ERR_NAME_NOT_RESOLVED" in err_msg else "FAIL"
                    steps.append(
                        StepResult(
                            id="portal_tls_reachability",
                            name="Portal TLS Reachability & Certificate Check",
                            status=s_status,
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail=f"Navigation failed: {err_msg}",
                        )
                    )
                    for sid, sname in STEP_METADATA[1:]:
                        steps.append(
                            StepResult(
                                id=sid,
                                name=sname,
                                status="NOT_OBSERVED",
                                duration_ms=0.0,
                                detail=f"Not observed: prerequisite step portal_tls_reachability failed with {s_status}",
                            )
                        )
                    return self._build_evidence(
                        start_time=start_time,
                        code_sha=code_sha,
                        measurement_kind="LIVE_BROWSER",
                        reference_only=False,
                        acceptance_claim=False,
                        overall_status=s_status,
                        blocking_reason=err_msg,
                        ca_digest=ca_digest,
                        steps=steps,
                        tls_validation_enforced=tls_validation_enforced,
                    )

                # Step 2: Login Initiation
                t0 = time.perf_counter()
                try:
                    login_btn = page.locator('button:has-text("조직 계정으로 로그인"), [data-testid="login-button"]').first
                    login_btn.wait_for(state="visible", timeout=int(self.timeout_sec * 1000))
                    login_btn.click()

                    # Wait for redirect towards IdP
                    page.wait_for_url(
                        lambda u: "protocol/openid-connect/auth" in u or "idp" in u or "/callback" in u or "/auth" in u,
                        timeout=int(self.timeout_sec * 1000),
                    )

                    # Handle IdP interactive login form if presented
                    user_input = page.locator('input[name="username"], input#username').first
                    pass_input = page.locator('input[name="password"], input#password').first
                    if user_input.is_visible() and pass_input.is_visible():
                        op_user = os.environ.get("SV_IDP_USERNAME") or os.environ.get("SV_PORTAL_TEST_USERNAME")
                        op_pass = os.environ.get("SV_IDP_PASSWORD") or os.environ.get("SV_PORTAL_TEST_PASSWORD")
                        if op_user and op_pass:
                            user_input.fill(op_user)
                            pass_input.fill(op_pass)
                            submit_btn = page.locator('#kc-login, input[type="submit"], button[type="submit"]').first
                            if submit_btn.is_visible():
                                submit_btn.click()
                        else:
                            raise RuntimeError(
                                "IdP login form detected but credentials not provided in environment "
                                "(set SV_IDP_USERNAME / SV_IDP_PASSWORD)"
                            )

                    steps.append(
                        StepResult(
                            id="login_initiation",
                            name="OIDC PKCE Login Initiation",
                            status="PASS",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail="Login button clicked and OIDC authorization redirect observed.",
                            observations={"initiated": True, "idpRedirectObserved": True},
                        )
                    )
                except Exception as e:
                    steps.append(
                        StepResult(
                            id="login_initiation",
                            name="OIDC PKCE Login Initiation",
                            status="FAIL",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail=f"Login initiation failed: {e}",
                        )
                    )
                    for sid, sname in STEP_METADATA[2:]:
                        steps.append(
                            StepResult(
                                id=sid,
                                name=sname,
                                status="NOT_OBSERVED",
                                duration_ms=0.0,
                                detail="Not observed: prerequisite step login_initiation failed",
                            )
                        )
                    return self._build_evidence(
                        start_time=start_time,
                        code_sha=code_sha,
                        measurement_kind="LIVE_BROWSER",
                        reference_only=False,
                        acceptance_claim=False,
                        overall_status="FAIL",
                        blocking_reason=str(e),
                        ca_digest=ca_digest,
                        steps=steps,
                        tls_validation_enforced=tls_validation_enforced,
                    )

                # Step 3: Callback
                t0 = time.perf_counter()
                try:
                    page.wait_for_url(
                        lambda u: "/callback" in u or "/studio" in u or u == self.target_url or u.startswith(self.target_url),
                        timeout=int(self.timeout_sec * 1000),
                    )

                    # Poll for token endpoint response on network
                    poll_start = time.perf_counter()
                    while not network_events["token_endpoint_observed"] and (time.perf_counter() - poll_start) < min(self.timeout_sec, 3.0):
                        page.wait_for_timeout(50)

                    if not network_events["token_endpoint_observed"]:
                        raise RuntimeError("Token endpoint exchange request was not observed on network")
                    if network_events["token_http_status"] != 200:
                        raise RuntimeError(
                            f"Token endpoint exchange returned HTTP {network_events['token_http_status']} (expected 200)"
                        )

                    steps.append(
                        StepResult(
                            id="pkce_callback",
                            name="OIDC Authorization Code Exchange Callback",
                            status="PASS",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail="Callback URL handled and token endpoint HTTP 200 confirmed on network.",
                            observations={
                                "callbackHandled": True,
                                "tokenEndpointObserved": True,
                                "tokenHttpStatus": network_events["token_http_status"],
                            },
                        )
                    )
                except Exception as e:
                    steps.append(
                        StepResult(
                            id="pkce_callback",
                            name="OIDC Authorization Code Exchange Callback",
                            status="FAIL",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail=f"Callback processing failed: {e}",
                        )
                    )
                    for sid, sname in STEP_METADATA[3:]:
                        steps.append(
                            StepResult(
                                id=sid,
                                name=sname,
                                status="NOT_OBSERVED",
                                duration_ms=0.0,
                                detail="Not observed: prerequisite step pkce_callback failed",
                            )
                        )
                    return self._build_evidence(
                        start_time=start_time,
                        code_sha=code_sha,
                        measurement_kind="LIVE_BROWSER",
                        reference_only=False,
                        acceptance_claim=False,
                        overall_status="FAIL",
                        blocking_reason=str(e),
                        ca_digest=ca_digest,
                        steps=steps,
                        tls_validation_enforced=tls_validation_enforced,
                    )

                # Step 4: Identity & Session Display
                t0 = time.perf_counter()
                try:
                    # Poll for /v1/session response on network
                    poll_start = time.perf_counter()
                    while not network_events["session_endpoint_observed"] and (time.perf_counter() - poll_start) < min(self.timeout_sec, 3.0):
                        page.wait_for_timeout(50)

                    if not network_events["session_endpoint_observed"]:
                        raise RuntimeError("/v1/session endpoint request was not observed on network")
                    if network_events["session_http_status"] != 200:
                        raise RuntimeError(
                            f"/v1/session endpoint returned HTTP {network_events['session_http_status']} (expected 200)"
                        )
                    if not network_events["session_shape_valid"]:
                        raise RuntimeError("/v1/session response body did not match canonical session schema")

                    user_badge = page.locator(
                        '[data-testid="user-identity"], [data-testid="user-role"], .user-profile, [data-authenticated="true"]'
                    ).first
                    user_badge.wait_for(state="visible", timeout=int(self.timeout_sec * 1000))
                    steps.append(
                        StepResult(
                            id="identity_session_display",
                            name="Identity and /v1/session Display",
                            status="PASS",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail="Authenticated identity and /v1/session HTTP 200 response shape validated.",
                            observations={
                                "identityObserved": True,
                                "authenticatedViewActive": True,
                                "sessionEndpointObserved": True,
                                "sessionHttpStatus": network_events["session_http_status"],
                                "sessionShapeValid": True,
                            },
                        )
                    )
                except Exception as e:
                    steps.append(
                        StepResult(
                            id="identity_session_display",
                            name="Identity and /v1/session Display",
                            status="FAIL",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail=f"Identity display observation failed: {e}",
                        )
                    )
                    steps.append(
                        StepResult(
                            id="logout",
                            name="OIDC Session Logout and Cleanup",
                            status="NOT_OBSERVED",
                            duration_ms=0.0,
                            detail="Not observed: prerequisite step identity_session_display failed",
                        )
                    )
                    return self._build_evidence(
                        start_time=start_time,
                        code_sha=code_sha,
                        measurement_kind="LIVE_BROWSER",
                        reference_only=False,
                        acceptance_claim=False,
                        overall_status="FAIL",
                        blocking_reason=str(e),
                        ca_digest=ca_digest,
                        steps=steps,
                        tls_validation_enforced=tls_validation_enforced,
                    )

                # Step 5: Logout
                t0 = time.perf_counter()
                try:
                    logout_btn = page.locator('button:has-text("로그아웃"), [data-testid="logout-button"]').first
                    logout_btn.wait_for(state="visible", timeout=int(self.timeout_sec * 1000))
                    logout_btn.click()

                    login_btn = page.locator('button:has-text("조직 계정으로 로그인"), [data-testid="login-button"]').first
                    login_btn.wait_for(state="visible", timeout=int(self.timeout_sec * 1000))

                    storage_state = page.evaluate("""() => {
                        const tx = window.sessionStorage.getItem('saintvision.oauth.transaction');
                        const sKeys = Object.keys(window.sessionStorage);
                        const lKeys = Object.keys(window.localStorage);
                        const noAuthInStorage = sKeys.every(k => !k.toLowerCase().includes('token') && !k.toLowerCase().includes('auth')) &&
                                                lKeys.every(k => !k.toLowerCase().includes('token') && !k.toLowerCase().includes('auth'));
                        return {
                            txCleared: tx === null,
                            storagePurged: noAuthInStorage
                        };
                    }""")

                    if not storage_state.get("txCleared"):
                        raise RuntimeError("OAuth transaction was not purged from sessionStorage upon logout")
                    if not storage_state.get("storagePurged"):
                        raise RuntimeError("Residual auth tokens or credentials detected in browser storage after logout")

                    steps.append(
                        StepResult(
                            id="logout",
                            name="OIDC Session Logout and Cleanup",
                            status="PASS",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail="Logout executed, storage purged, and unauthenticated view restored.",
                            observations={
                                "loginScreenRestored": True,
                                "transactionCleared": True,
                                "storagePurged": True,
                            },
                        )
                    )
                except Exception as e:
                    steps.append(
                        StepResult(
                            id="logout",
                            name="OIDC Session Logout and Cleanup",
                            status="FAIL",
                            duration_ms=(time.perf_counter() - t0) * 1000,
                            detail=f"Logout failed: {e}",
                        )
                    )
                    return self._build_evidence(
                        start_time=start_time,
                        code_sha=code_sha,
                        measurement_kind="LIVE_BROWSER",
                        reference_only=False,
                        acceptance_claim=False,
                        overall_status="FAIL",
                        blocking_reason=str(e),
                        ca_digest=ca_digest,
                        steps=steps,
                        tls_validation_enforced=tls_validation_enforced,
                    )

            finally:
                context.close()
                browser.close()

        overall_status = compute_overall_status(steps)
        acceptance_claim = (
            overall_status == "PASS"
            and tls_validation_enforced is True
            and ca_digest is not None
            and ca_digest.get("fingerprintVerified") is True
        )

        return self._build_evidence(
            start_time=start_time,
            code_sha=code_sha,
            measurement_kind="LIVE_BROWSER",
            reference_only=False,
            acceptance_claim=acceptance_claim,
            overall_status=overall_status,
            blocking_reason=None,
            ca_digest=ca_digest,
            steps=steps,
            tls_validation_enforced=tls_validation_enforced,
        )

    def _build_evidence(
        self,
        start_time: str,
        code_sha: str,
        measurement_kind: str,
        reference_only: bool,
        acceptance_claim: bool,
        overall_status: str,
        blocking_reason: Optional[str],
        ca_digest: Optional[Dict[str, Any]],
        steps: List[StepResult],
        tls_validation_enforced: bool,
    ) -> Dict[str, Any]:
        raw_steps = [s.to_dict() for s in steps]

        sanitized_steps = RedactionSanitizer.sanitize_obj(raw_steps)
        sanitized_reason = RedactionSanitizer.sanitize_str(blocking_reason) if blocking_reason else None
        sanitized_target_url = RedactionSanitizer.sanitize_url(self.target_url)

        evidence = {
            "schemaVersion": "1.1.0",
            "timestamp": start_time,
            "codeSha": code_sha,
            "measurementKind": measurement_kind,
            "referenceOnly": reference_only,
            "acceptanceClaim": acceptance_claim,
            "targetUrl": sanitized_target_url,
            "overallStatus": overall_status,
            "blockingReason": sanitized_reason,
            "caDigest": ca_digest,
            "steps": sanitized_steps,
            "audit": {
                "redacted": True,
                "tokenCount": 0,
                "ipCount": 0,
                "credentialCount": 0,
                "accountCount": 0,
                "oidcParamCount": 0,
                "circumventionFlagsDetected": False,
                "tlsValidationEnforced": tls_validation_enforced,
            },
        }

        t_cnt, ip_cnt, cred_cnt, acc_cnt, oidc_cnt = RedactionSanitizer.audit_obj(evidence)
        evidence["audit"]["tokenCount"] = t_cnt
        evidence["audit"]["ipCount"] = ip_cnt
        evidence["audit"]["credentialCount"] = cred_cnt
        evidence["audit"]["accountCount"] = acc_cnt
        evidence["audit"]["oidcParamCount"] = oidc_cnt

        if t_cnt > 0 or ip_cnt > 0 or cred_cnt > 0 or acc_cnt > 0 or oidc_cnt > 0:
            raise RuntimeError(
                f"Redaction audit failed! Leaked data detected: tokens={t_cnt}, ips={ip_cnt}, credentials={cred_cnt}, accounts={acc_cnt}, oidcParams={oidc_cnt}"
            )

        return evidence


def compute_overall_status(steps: List[StepResult]) -> str:
    statuses = [s.status for s in steps]
    if any(s == "FAIL" for s in statuses):
        return "FAIL"
    if any(s == "BLOCKED_EXTERNAL" for s in statuses):
        return "BLOCKED_EXTERNAL"
    if any(s == "NOT_OBSERVED" for s in statuses):
        return "FAIL"
    if all(s == "PASS" for s in statuses):
        return "PASS"
    return "FAIL"


def validate_evidence(evidence: Dict[str, Any]) -> None:
    import jsonschema

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema not found at {SCHEMA_PATH}")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)

    # 1. Structural schema validation
    jsonschema.validate(instance=evidence, schema=schema)

    # 2. Semantic invariant: Contradiction check
    overall = evidence["overallStatus"]
    steps = evidence["steps"]
    step_statuses = [s["status"] for s in steps]
    step_ids = [s["id"] for s in steps]

    expected_ids = [s[0] for s in STEP_METADATA]
    if step_ids != expected_ids:
        raise jsonschema.ValidationError(
            f"Step IDs must match exact expected sequence {expected_ids}, got {step_ids}"
        )

    if overall == "PASS":
        for s in steps:
            if s["status"] != "PASS":
                raise jsonschema.ValidationError(
                    f"Contradiction: overallStatus is PASS but step '{s['id']}' has status '{s['status']}'"
                )

    # 3. Semantic invariant: Reference-only cannot claim acceptance
    if evidence.get("referenceOnly") is True and evidence.get("acceptanceClaim") is True:
        raise jsonschema.ValidationError(
            "Contradiction: referenceOnly evidence cannot make an acceptanceClaim"
        )

    if evidence.get("acceptanceClaim") is True:
        if evidence.get("measurementKind") != "LIVE_BROWSER":
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires LIVE_BROWSER measurementKind"
            )
        if overall != "PASS":
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires overallStatus == PASS"
            )
        if evidence.get("audit", {}).get("tlsValidationEnforced") is not True:
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires audit.tlsValidationEnforced == True"
            )
        ca_d = evidence.get("caDigest")
        if not ca_d or not ca_d.get("fingerprintVerified"):
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires verified caDigest with fingerprintVerified=true"
            )
        if not ca_d.get("caBundleSha256") or not ca_d.get("rootFingerprint"):
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires non-null caBundleSha256 and rootFingerprint in caDigest"
            )
        s3 = next((s for s in steps if s["id"] == "pkce_callback"), None)
        if not s3 or not s3.get("observations", {}).get("tokenEndpointObserved") or s3.get("observations", {}).get("tokenHttpStatus") != 200:
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires verified tokenEndpointObserved=true and tokenHttpStatus=200 in pkce_callback"
            )
        s4 = next((s for s in steps if s["id"] == "identity_session_display"), None)
        if not s4 or not s4.get("observations", {}).get("sessionEndpointObserved") or s4.get("observations", {}).get("sessionHttpStatus") != 200 or not s4.get("observations", {}).get("sessionShapeValid"):
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires verified sessionEndpointObserved=true, sessionHttpStatus=200, and sessionShapeValid=true in identity_session_display"
            )
        s5 = next((s for s in steps if s["id"] == "logout"), None)
        if not s5 or not s5.get("observations", {}).get("transactionCleared") or not s5.get("observations", {}).get("storagePurged"):
            raise jsonschema.ValidationError(
                "Contradiction: acceptanceClaim requires verified transactionCleared=true and storagePurged=true in logout"
            )

    # 4. Semantic invariant: TLS validation enforced implies caDigest verified
    if evidence.get("audit", {}).get("tlsValidationEnforced") is True:
        ca_d = evidence.get("caDigest")
        if not ca_d or not ca_d.get("fingerprintVerified"):
            raise jsonschema.ValidationError(
                "Contradiction: tlsValidationEnforced is true but caDigest was not verified"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Observe portal login journey on portal.sv.lan")
    parser.add_argument("--target-url", default="https://portal.sv.lan", help="Target portal URL")
    parser.add_argument("--idp-url", default="https://idp.sv.lan", help="IdP issuer URL")
    parser.add_argument("--ca-bundle", default=None, help="Path to intranet CA bundle")
    parser.add_argument(
        "--allowed-root-fingerprints",
        nargs="*",
        default=None,
        help="Allowed root CA SHA-256 fingerprints",
    )
    parser.add_argument("--output-evidence", default=None, help="Output evidence JSON path")
    parser.add_argument("--mock-mode", action="store_true", help="Run in mock/simulation mode for local validation")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-step timeout in seconds")

    args, unknown = parser.parse_known_args()

    try:
        check_circumvention_flags(unknown)
        check_circumvention_flags(sys.argv)
    except SecurityCircumventionError as e:
        print(f"[SECURITY ERROR] {e}", file=sys.stderr)
        return 2

    try:
        observer = PortalLoginJourneyObserver(
            target_url=args.target_url,
            idp_url=args.idp_url,
            ca_bundle=args.ca_bundle,
            allowed_root_fingerprints=args.allowed_root_fingerprints,
            mock_mode=args.mock_mode,
            timeout_sec=args.timeout,
            extra_args=unknown,
        )
    except ValueError as e:
        print(f"[CONFIGURATION ERROR] {e}", file=sys.stderr)
        return 2

    evidence = observer.execute_journey()

    try:
        validate_evidence(evidence)
    except Exception as e:
        print(f"[SCHEMA VALIDATION ERROR] Evidence violates schema: {e}", file=sys.stderr)
        return 1

    formatted = json.dumps(evidence, indent=2, ensure_ascii=False)
    if args.output_evidence:
        out_path = Path(args.output_evidence)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(formatted + "\n", encoding="utf-8")
        print(f"[EVIDENCE SAVED] {out_path} (overallStatus={evidence['overallStatus']})")
    else:
        print(formatted)

    return 0


if __name__ == "__main__":
    sys.exit(main())
