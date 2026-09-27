"""Collect redacted, read-only S01-BE/S01-ST readiness evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import socket
import ssl
import sys
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, HTTPSHandler

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, padding, rsa

ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_SRC = ROOT / "services" / "control-plane" / "src"
if str(CONTROL_PLANE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_SRC))

from inv.node_channels import certificate_identity
from inv.tooling import NodePrincipal


SCHEMA_VERSION = "s01-readiness-preflight:1"
INVENTORY_SCHEMA_VERSION = "s01-readiness-inventory:1"
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_NODE_ID = re.compile(r"^nod_[A-Za-z0-9][A-Za-z0-9_-]{0,126}$")
_FORBIDDEN_REPORT_KEYS = {
    "token",
    "dsn",
    "baseurl",
    "url",
    "hostname",
    "ip",
    "nodeid",
    "tenantid",
    "fingerprint",
    "path",
    "certificate",
    "subjectid",
}


def _check(check_id: str, status: str, code: str, **facts: Any) -> dict[str, Any]:
    return {"id": check_id, "status": status, "code": code, "facts": facts}


def _mapping_counts(value: Any, expected: set[str]) -> tuple[int, int]:
    if not isinstance(value, dict):
        return len(expected), 1 if value is not None else 0
    missing = {key for key in expected if key not in value or value[key] is None}
    return len(missing), len(set(value) - expected)


def _positive_integer(value: Any, *, allow_zero: bool = False) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and (value >= 0 if allow_zero else value > 0)
    )


def lint_inventory(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Validate the protected S01 inventory without returning any input value."""

    if payload is None:
        return _check(
            "inventory-lint",
            "BLOCKED",
            "inventory-input-missing",
            nodeCount=0,
            missingFieldCount=1,
            invalidFieldCount=0,
        )
    missing, invalid = _mapping_counts(
        payload, {"schemaVersion", "topology", "hostnames", "nodes"}
    )
    if not isinstance(payload, dict):
        return _check(
            "inventory-lint",
            "FAIL",
            "inventory-invalid",
            nodeCount=0,
            missingFieldCount=missing,
            invalidFieldCount=max(invalid, 1),
        )
    if payload.get("schemaVersion") != INVENTORY_SCHEMA_VERSION:
        if payload.get("schemaVersion") is not None:
            invalid += 1
    topology = payload.get("topology")
    if topology not in {"five-workers-dedicated-cp", "cp-colocated-plus-four-workers"}:
        if topology is not None:
            invalid += 1

    hostnames = payload.get("hostnames")
    add_missing, add_invalid = _mapping_counts(
        hostnames, {"controlPlane", "portal", "idp"}
    )
    missing += add_missing
    invalid += add_invalid
    hostname_values: list[str] = []
    if isinstance(hostnames, dict):
        for field in ("controlPlane", "portal", "idp"):
            values = hostnames.get(field)
            if values is None:
                continue
            if not isinstance(values, list) or not values:
                invalid += 1
                continue
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    invalid += 1
                else:
                    hostname_values.append(value)
    if len(hostname_values) != len(set(hostname_values)):
        invalid += 1

    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        if nodes is not None:
            invalid += 1
        node_count = 0
    else:
        node_count = len(nodes)
        if node_count < 5:
            missing += 5 - node_count
        elif node_count > 5:
            invalid += node_count - 5

    node_keys = {
        "nodeId",
        "hostname",
        "dnsName",
        "ip",
        "installationId",
        "os",
        "role",
        "certificateSHA256",
        "profile",
        "hardware",
        "capacity",
        "allowedResources",
        "allowedFolders",
        "ntp",
        "storageRole",
    }
    os_keys = {"family", "version", "containerRuntime"}
    hardware_keys = {
        "cpuModel",
        "physicalCoreCount",
        "logicalThreadCount",
        "gpus",
        "storageDevice",
        "networkInterface",
    }
    gpu_keys = {"model", "vramBytes", "driver"}
    capacity_keys = {
        "cpuMillis",
        "memoryBytes",
        "gpuDevices",
        "storageBytes",
        "networkBitsPerSecond",
    }
    allowed_keys = {"cpuMillis", "memoryBytes", "gpuDevices", "storageBytes"}
    ntp_keys = {"configured", "source", "maxSkewSeconds"}
    unique_fields = {
        "nodeId": set(),
        "hostname": set(),
        "dnsName": set(),
        "ip": set(),
        "installationId": set(),
        "certificateSHA256": set(),
    }
    colocated_count = 0
    if isinstance(nodes, list):
        for node in nodes:
            add_missing, add_invalid = _mapping_counts(node, node_keys)
            missing += add_missing
            invalid += add_invalid
            if not isinstance(node, dict):
                continue
            for field in ("nodeId", "hostname", "dnsName", "ip", "installationId"):
                value = node.get(field)
                if value is None:
                    continue
                if not isinstance(value, str) or not value.strip():
                    invalid += 1
                    continue
                if value in unique_fields[field]:
                    invalid += 1
                unique_fields[field].add(value)
            node_id = node.get("nodeId")
            if isinstance(node_id, str) and not _NODE_ID.fullmatch(node_id):
                invalid += 1
            address = node.get("ip")
            if isinstance(address, str) and address:
                try:
                    parsed = ipaddress.ip_address(address)
                    if parsed.version != 4 or not parsed.is_private or parsed.is_loopback:
                        invalid += 1
                except ValueError:
                    invalid += 1
            fingerprint = node.get("certificateSHA256")
            if fingerprint is not None:
                if not isinstance(fingerprint, str) or not _HEX_64.fullmatch(fingerprint):
                    invalid += 1
                elif fingerprint in unique_fields["certificateSHA256"]:
                    invalid += 1
                else:
                    unique_fields["certificateSHA256"].add(fingerprint)
            if node.get("profile") not in {"lan-workspace-v1", "lan-observe-v1"}:
                if node.get("profile") is not None:
                    invalid += 1
            role = node.get("role")
            if role == "cp-colocated":
                colocated_count += 1
            elif role != "worker" and role is not None:
                invalid += 1
            if node.get("storageRole") not in {"provider", "archive", "none"}:
                if node.get("storageRole") is not None:
                    invalid += 1

            os_value = node.get("os")
            add_missing, add_invalid = _mapping_counts(os_value, os_keys)
            missing += add_missing
            invalid += add_invalid
            if isinstance(os_value, dict):
                for field in os_keys:
                    value = os_value.get(field)
                    if value is not None and (not isinstance(value, str) or not value.strip()):
                        invalid += 1

            hardware = node.get("hardware")
            add_missing, add_invalid = _mapping_counts(hardware, hardware_keys)
            missing += add_missing
            invalid += add_invalid
            if isinstance(hardware, dict):
                for field in ("cpuModel", "storageDevice", "networkInterface"):
                    value = hardware.get(field)
                    if value is not None and (not isinstance(value, str) or not value.strip()):
                        invalid += 1
                physical = hardware.get("physicalCoreCount")
                logical = hardware.get("logicalThreadCount")
                if physical is not None and not _positive_integer(physical):
                    invalid += 1
                if logical is not None and not _positive_integer(logical):
                    invalid += 1
                if isinstance(physical, int) and isinstance(logical, int) and logical < physical:
                    invalid += 1
                gpus = hardware.get("gpus")
                if gpus is not None and not isinstance(gpus, list):
                    invalid += 1
                elif isinstance(gpus, list):
                    for gpu in gpus:
                        gpu_missing, gpu_invalid = _mapping_counts(gpu, gpu_keys)
                        missing += gpu_missing
                        invalid += gpu_invalid
                        if not isinstance(gpu, dict):
                            continue
                        for field in ("model", "driver"):
                            value = gpu.get(field)
                            if value is not None and (
                                not isinstance(value, str) or not value.strip()
                            ):
                                invalid += 1
                        if gpu.get("vramBytes") is not None and not _positive_integer(
                            gpu.get("vramBytes")
                        ):
                            invalid += 1

            capacity = node.get("capacity")
            add_missing, add_invalid = _mapping_counts(capacity, capacity_keys)
            missing += add_missing
            invalid += add_invalid
            if isinstance(capacity, dict):
                for field in capacity_keys:
                    value = capacity.get(field)
                    if value is not None and not _positive_integer(
                        value, allow_zero=field == "gpuDevices"
                    ):
                        invalid += 1
                if (
                    isinstance(hardware, dict)
                    and isinstance(hardware.get("gpus"), list)
                    and capacity.get("gpuDevices") is not None
                ):
                    if len(hardware["gpus"]) != capacity.get("gpuDevices"):
                        invalid += 1

            allowed = node.get("allowedResources")
            add_missing, add_invalid = _mapping_counts(allowed, allowed_keys)
            missing += add_missing
            invalid += add_invalid
            if isinstance(allowed, dict):
                for field in allowed_keys:
                    value = allowed.get(field)
                    if value is not None and not _positive_integer(value, allow_zero=True):
                        invalid += 1
                    cap_value = capacity.get(field) if isinstance(capacity, dict) else None
                    if isinstance(value, int) and isinstance(cap_value, int) and value > cap_value:
                        invalid += 1

            folders = node.get("allowedFolders")
            if folders is not None and (
                not isinstance(folders, list)
                or (node.get("storageRole") != "none" and not folders)
                or any(not isinstance(value, str) or not value.strip() for value in folders)
            ):
                invalid += 1
            elif isinstance(folders, list):
                for folder in folders:
                    if isinstance(folder, str) and not (
                        PurePosixPath(folder).is_absolute()
                        or PureWindowsPath(folder).is_absolute()
                    ):
                        invalid += 1

            ntp = node.get("ntp")
            add_missing, add_invalid = _mapping_counts(ntp, ntp_keys)
            missing += add_missing
            invalid += add_invalid
            if isinstance(ntp, dict):
                if ntp.get("configured") is not None and ntp["configured"] is not True:
                    invalid += 1
                source = ntp.get("source")
                if source is not None and (
                    not isinstance(source, str) or not source.strip()
                ):
                    invalid += 1
                skew = ntp.get("maxSkewSeconds")
                if skew is not None and (
                    not isinstance(skew, (int, float))
                    or isinstance(skew, bool)
                    or skew < 0
                    or skew > 5
                ):
                    invalid += 1

    roles_complete = isinstance(nodes, list) and all(
        isinstance(node, dict) and node.get("role") is not None for node in nodes
    )
    if roles_complete:
        if topology == "cp-colocated-plus-four-workers" and colocated_count != 1:
            invalid += 1
        if topology == "five-workers-dedicated-cp" and colocated_count != 0:
            invalid += 1

    if invalid:
        status, code = "FAIL", "inventory-invalid"
    elif missing:
        status, code = "BLOCKED", "inventory-values-missing"
    else:
        status, code = "PASS", "inventory-valid"
    return _check(
        "inventory-lint",
        status,
        code,
        nodeCount=node_count,
        missingFieldCount=missing,
        invalidFieldCount=invalid,
    )


def probe_control_plane(
    *,
    base_url: str | None,
    health_url: str | None,
    token: str | None,
    fetch: Callable[..., tuple[int, Any, dict[str, str]]],
    health_fetch: Callable[..., tuple[int, Any, dict[str, str]]],
) -> list[dict[str, Any]]:
    """Probe HTTP signals while returning no response or endpoint value."""

    if not health_url:
        health = _check(
            "health-unresolved-settings",
            "BLOCKED",
            "health-url-missing",
            unresolvedSettingCount=0,
        )
    else:
        try:
            health_status, health_body, _ = health_fetch("", authenticated=False)
            unresolved = health_body.get("unresolvedSettings") if isinstance(health_body, dict) else None
            unresolved_count = len(unresolved) if isinstance(unresolved, list) else 0
            health_valid = health_status == 200 and isinstance(unresolved, list) and not unresolved
            health = _check(
                "health-unresolved-settings",
                "PASS" if health_valid else "FAIL",
                "health-resolved" if health_valid else "health-not-resolved",
                unresolvedSettingCount=unresolved_count,
            )
        except Exception:
            health = _check(
                "health-unresolved-settings",
                "FAIL",
                "health-probe-failed",
                unresolvedSettingCount=0,
            )

    if not base_url:
        ready = _check("readyz", "BLOCKED", "base-url-missing", readySignalValid=False)
        session = _check(
            "session-boundary",
            "BLOCKED",
            "base-url-missing",
            authenticatedSessionValid=False,
            anonymousBoundaryValid=False,
        )
        return [health, ready, session]

    try:
        ready_status, ready_body, _ = fetch("/readyz", authenticated=False)
        ready_valid = (
            ready_status == 200
            and isinstance(ready_body, dict)
            and ready_body.get("status") == "ready"
        )
        ready = _check(
            "readyz",
            "PASS" if ready_valid else "FAIL",
            "ready-signal-valid" if ready_valid else "ready-signal-invalid",
            readySignalValid=ready_valid,
        )
    except Exception:
        ready = _check("readyz", "FAIL", "ready-probe-failed", readySignalValid=False)

    anonymous_valid = False
    anonymous_failed = False
    try:
        anonymous_status, _, anonymous_headers = fetch("/v1/session", authenticated=False)
        anonymous_valid = (
            anonymous_status == 401
            and anonymous_headers.get("www-authenticate", "").lower() == "bearer"
        )
    except Exception:
        anonymous_failed = True
    if token is None or not token.strip():
        session = _check(
            "session-boundary",
            "BLOCKED" if anonymous_valid else "FAIL",
            "access-token-missing" if anonymous_valid else "anonymous-session-boundary-invalid",
            authenticatedSessionValid=False,
            anonymousBoundaryValid=anonymous_valid,
        )
    elif urlsplit(base_url).scheme.lower() != "https":
        session = _check(
            "session-boundary",
            "FAIL",
            "plaintext-token-transport-rejected",
            authenticatedSessionValid=False,
            anonymousBoundaryValid=anonymous_valid,
        )
    else:
        authenticated_valid = False
        try:
            authenticated_status, authenticated_body, _ = fetch(
                "/v1/session", authenticated=True
            )
            authenticated_valid = authenticated_status == 200 and isinstance(
                authenticated_body, dict
            )
        except Exception:
            authenticated_valid = False
        boundary_valid = anonymous_valid and authenticated_valid and not anonymous_failed
        session = _check(
            "session-boundary",
            "PASS" if boundary_valid else "FAIL",
            "session-boundary-valid" if boundary_valid else "session-boundary-invalid",
            authenticatedSessionValid=authenticated_valid,
            anonymousBoundaryValid=anonymous_valid,
        )
    return [health, ready, session]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def http_fetcher(
    base_url: str,
    token: str | None,
    ca_bundle: Path | None,
    timeout_seconds: float,
    *,
    exact_url: bool = False,
) -> Callable[..., tuple[int, Any, dict[str, str]]]:
    context = ssl.create_default_context(cafile=str(ca_bundle)) if ca_bundle else None
    handlers: list[Any] = [_NoRedirect()]
    if context is not None:
        handlers.append(HTTPSHandler(context=context))
    opener = build_opener(*handlers)

    def fetch(path: str, *, authenticated: bool) -> tuple[int, Any, dict[str, str]]:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + (token or "")
        request_url = base_url if exact_url else base_url.rstrip("/") + path
        request = Request(request_url, headers=headers, method="GET")
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except HTTPError as error:
            response = error
        raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError("response too large")
        try:
            body = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeError, json.JSONDecodeError):
            body = None
        response_headers = {key.lower(): value for key, value in response.headers.items()}
        return int(response.status), body, response_headers

    return fetch


def _load_inventory(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"schemaVersion": "invalid-root"}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"schemaVersion": "unreadable-input"}


def probe_dns(
    inventory: dict[str, Any] | None,
    *,
    resolver: Callable[..., Any] = socket.getaddrinfo,
) -> dict[str, Any]:
    lint = lint_inventory(inventory)
    if inventory is None:
        return _check("dns-resolution", "BLOCKED", "inventory-input-missing", hostnameCount=0, resolvedCount=0)
    if lint["status"] != "PASS":
        return _check("dns-resolution", "BLOCKED", "inventory-not-ready", hostnameCount=0, resolvedCount=0)
    hostnames: list[str] = []
    groups = inventory.get("hostnames") if isinstance(inventory, dict) else None
    if isinstance(groups, dict):
        for field in ("controlPlane", "portal", "idp"):
            values = groups.get(field)
            if isinstance(values, list):
                hostnames.extend(value for value in values if isinstance(value, str) and value)
    nodes = inventory.get("nodes") if isinstance(inventory, dict) else None
    if isinstance(nodes, list):
        hostnames.extend(
            node.get("dnsName")
            for node in nodes
            if isinstance(node, dict) and isinstance(node.get("dnsName"), str) and node.get("dnsName")
        )
    hostnames = list(dict.fromkeys(hostnames))
    if not hostnames:
        return _check("dns-resolution", "BLOCKED", "dns-input-missing", hostnameCount=0, resolvedCount=0)
    resolved = 0
    for hostname in hostnames:
        try:
            if resolver(hostname, None):
                resolved += 1
        except Exception:
            pass
    valid = resolved == len(hostnames)
    return _check(
        "dns-resolution",
        "PASS" if valid else "FAIL",
        "dns-resolved" if valid else "dns-resolution-failed",
        hostnameCount=len(hostnames),
        resolvedCount=resolved,
    )


def _pem_certificates(path: Path) -> list[x509.Certificate]:
    raw = path.read_bytes()
    blocks = re.findall(
        b"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
        raw,
        flags=re.DOTALL,
    )
    return [x509.load_pem_x509_certificate(block) for block in blocks]


def _signed_by(leaf: x509.Certificate, authority: x509.Certificate) -> bool:
    if leaf.issuer != authority.subject:
        return False
    key = authority.public_key()
    try:
        if isinstance(key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
            key.verify(leaf.signature, leaf.tbs_certificate_bytes)
        elif isinstance(key, rsa.RSAPublicKey):
            key.verify(
                leaf.signature,
                leaf.tbs_certificate_bytes,
                padding.PKCS1v15(),
                leaf.signature_hash_algorithm,
            )
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(
                leaf.signature,
                leaf.tbs_certificate_bytes,
                ec.ECDSA(leaf.signature_hash_algorithm),
            )
        else:
            return False
    except Exception:
        return False
    return True


def _state_nodes(state: Any) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    nodes = state.get("nodes")
    if nodes is None and state.get("nodeId") and state.get("nodeIP"):
        nodes = [
            {
                "nodeId": state["nodeId"],
                "nodeIP": state["nodeIP"],
                "provisioned": bool(state.get("initialized")),
            }
        ]
    if not isinstance(nodes, list):
        return []
    return [node for node in nodes if isinstance(node, dict) and not node.get("disabled", False)]


def _node_certificate_file(state_path: Path, state: dict[str, Any], node: dict[str, Any]) -> Path:
    specific = state_path / "public" / "nodes" / str(node.get("nodeId")) / "node-cert.pem"
    if specific.is_file():
        return specific
    nodes = _state_nodes(state)
    if nodes and node.get("nodeId") == nodes[0].get("nodeId"):
        return state_path / "public" / "node-cert.pem"
    return specific


def probe_certificate_chain(
    state_path: Path | None,
    inventory: dict[str, Any] | None,
    ca_bundle: Path | None,
) -> dict[str, Any]:
    if state_path is None or inventory is None:
        return _check("node-certificate-chain", "BLOCKED", "certificate-input-missing", registeredLeafCount=0, verifiedLeafCount=0)
    if lint_inventory(inventory)["status"] != "PASS":
        return _check("node-certificate-chain", "BLOCKED", "inventory-not-ready", registeredLeafCount=0, verifiedLeafCount=0)
    state_file = state_path / "private-state.json"
    if not state_file.is_file():
        return _check("node-certificate-chain", "FAIL", "pilot-state-invalid", registeredLeafCount=0, verifiedLeafCount=0)
    ca_path = ca_bundle or (state_path / "ca.pem")
    if not ca_path.is_file():
        return _check("node-certificate-chain", "BLOCKED", "ca-bundle-missing", registeredLeafCount=0, verifiedLeafCount=0)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        authorities = _pem_certificates(ca_path)
    except Exception:
        return _check("node-certificate-chain", "FAIL", "certificate-input-invalid", registeredLeafCount=0, verifiedLeafCount=0)
    now = datetime.now(timezone.utc)
    valid_authorities = []
    for authority in authorities:
        try:
            if (
                authority.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
                and authority.not_valid_before_utc <= now < authority.not_valid_after_utc
            ):
                valid_authorities.append(authority)
        except x509.ExtensionNotFound:
            pass
    if not valid_authorities:
        return _check("node-certificate-chain", "FAIL", "certificate-authority-invalid", registeredLeafCount=0, verifiedLeafCount=0)
    if not isinstance(state, dict):
        return _check("node-certificate-chain", "FAIL", "pilot-state-invalid", registeredLeafCount=0, verifiedLeafCount=0)
    tenant_id = state.get("tenantId")
    epoch = state.get("epoch")
    if not isinstance(tenant_id, str) or not tenant_id or not isinstance(epoch, str) or not epoch:
        return _check("node-certificate-chain", "BLOCKED", "certificate-identity-input-missing", registeredLeafCount=0, verifiedLeafCount=0)
    raw_inventory_nodes = inventory.get("nodes")
    if not isinstance(raw_inventory_nodes, list):
        return _check("node-certificate-chain", "BLOCKED", "inventory-not-ready", registeredLeafCount=0, verifiedLeafCount=0)
    inventory_nodes = {
        node.get("nodeId"): node
        for node in raw_inventory_nodes
        if isinstance(node, dict)
    }
    candidates = [node for node in _state_nodes(state) if node.get("provisioned")]
    candidate_ids = {node.get("nodeId") for node in candidates}
    if len(candidates) != 5 or candidate_ids != set(inventory_nodes):
        return _check("node-certificate-chain", "BLOCKED", "registered-node-certificates-incomplete", registeredLeafCount=len(candidates), verifiedLeafCount=0)
    verified = 0
    for node in candidates:
        cert_path = _node_certificate_file(state_path, state, node)
        inventory_node = inventory_nodes.get(node.get("nodeId"))
        try:
            if cert_path.is_symlink() or not cert_path.is_file() or inventory_node is None:
                continue
            leaf = x509.load_pem_x509_certificate(cert_path.read_bytes())
            fingerprint = hashlib.sha256(
                leaf.public_bytes(serialization.Encoding.DER)
            ).hexdigest()
            identity_fingerprint, _ = certificate_identity(
                leaf.public_bytes(serialization.Encoding.DER),
                NodePrincipal(tenant_id, str(node.get("nodeId"))),
                epoch,
                now=now,
            )
            valid = (
                inventory_node.get("certificateSHA256") == fingerprint
                and identity_fingerprint == fingerprint
                and any(_signed_by(leaf, authority) for authority in valid_authorities)
            )
            if valid:
                verified += 1
        except Exception:
            continue
    passed = verified == len(candidates)
    return _check(
        "node-certificate-chain",
        "PASS" if passed else "FAIL",
        "certificate-chain-valid" if passed else "certificate-chain-invalid",
        registeredLeafCount=len(candidates),
        verifiedLeafCount=verified,
    )


def evaluate_capability_rows(
    inventory: dict[str, Any], rows: list[dict[str, Any]], *, database_read_only: bool
) -> dict[str, Any]:
    expected = {
        node.get("nodeId"): node
        for node in inventory.get("nodes", [])
        if isinstance(node, dict) and node.get("nodeId")
    }
    matched = 0
    seen: set[str] = set()
    duplicate = False
    for row in rows:
        node_id = str(row.get("node_id", ""))
        if node_id in seen:
            duplicate = True
            continue
        seen.add(node_id)
        node = expected.get(node_id)
        snapshot = row.get("snapshot")
        if not node or not isinstance(snapshot, dict):
            continue
        capacity = node.get("capacity")
        if not isinstance(capacity, dict):
            continue
        if (
            row.get("certificate_sha256") == node.get("certificateSHA256")
            and snapshot.get("profileVersion") == node.get("profile")
            and snapshot.get("cpuCapacityMillis") == capacity.get("cpuMillis")
            and snapshot.get("memoryCapacityBytes") == capacity.get("memoryBytes")
        ):
            matched += 1
    passed = (
        database_read_only
        and not duplicate
        and len(expected) == 5
        and len(rows) == 5
        and seen == set(expected)
        and matched == 5
    )
    return _check(
        "pilot-capability-match",
        "PASS" if passed else "FAIL",
        "pilot-capabilities-match" if passed else "pilot-capabilities-differ",
        inventoryNodeCount=len(expected),
        registeredNodeCount=len(rows),
        matchedNodeCount=matched,
        databaseReadOnly=database_read_only,
    )


def probe_pilot_capabilities(
    state_path: Path | None,
    inventory: dict[str, Any] | None,
    *,
    connect: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    if state_path is None or inventory is None:
        return _check("pilot-capability-match", "BLOCKED", "pilot-input-missing", inventoryNodeCount=0, registeredNodeCount=0, matchedNodeCount=0, databaseReadOnly=False)
    if lint_inventory(inventory)["status"] != "PASS":
        return _check("pilot-capability-match", "BLOCKED", "inventory-not-ready", inventoryNodeCount=0, registeredNodeCount=0, matchedNodeCount=0, databaseReadOnly=False)
    state_file = state_path / "private-state.json"
    if not state_file.is_file():
        return _check("pilot-capability-match", "FAIL", "pilot-state-invalid", inventoryNodeCount=5, registeredNodeCount=0, matchedNodeCount=0, databaseReadOnly=False)
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        dsn = state.get("runtimeDSN")
        tenant_id = state.get("tenantId")
        if not isinstance(dsn, str) or not dsn or not isinstance(tenant_id, str) or not tenant_id:
            return _check("pilot-capability-match", "BLOCKED", "pilot-database-input-missing", inventoryNodeCount=5, registeredNodeCount=0, matchedNodeCount=0, databaseReadOnly=False)
        if connect is None:
            import psycopg
            from psycopg.rows import dict_row

            connect = lambda value: psycopg.connect(value, row_factory=dict_row)
        with connect(dsn) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '2s'")
            read_only_row = connection.execute("SHOW transaction_read_only").fetchone()
            read_only = str(
                next(iter(read_only_row.values()))
                if isinstance(read_only_row, dict)
                else read_only_row[0]
            ).lower() == "on"
            connection.execute("SELECT set_config('inv.tenant_id', %s, true)", (tenant_id,))
            rows = connection.execute(
                """SELECT n.node_id,c.certificate_sha256,s.snapshot
                FROM inv.nodes n
                LEFT JOIN inv.node_channels c
                  ON c.tenant_id=n.tenant_id AND c.node_id=n.node_id
                LEFT JOIN inv.node_resource_snapshots s
                  ON s.tenant_id=n.tenant_id AND s.node_id=n.node_id
                WHERE n.tenant_id=%s ORDER BY n.node_id""",
                (tenant_id,),
            ).fetchall()
            normalized = [dict(row) if not isinstance(row, dict) else row for row in rows]
        return evaluate_capability_rows(inventory, normalized, database_read_only=read_only)
    except Exception:
        return _check("pilot-capability-match", "FAIL", "pilot-database-probe-failed", inventoryNodeCount=5, registeredNodeCount=0, matchedNodeCount=0, databaseReadOnly=False)


_INPUT_CHECKS = {
    "U1": ("inventory-lint",),
    "U2": ("health-unresolved-settings", "readyz", "session-boundary"),
    "U3": ("health-unresolved-settings", "readyz", "node-certificate-chain"),
    "U4": ("dns-resolution",),
    "U5": ("inventory-lint", "node-certificate-chain", "pilot-capability-match"),
    "U6": ("health-unresolved-settings", "inventory-lint"),
}


def aggregate_inputs(checks: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    by_id = {check["id"]: check for check in checks}
    result: dict[str, dict[str, str]] = {}
    for input_id, check_ids in _INPUT_CHECKS.items():
        statuses = [by_id.get(check_id, {"status": "BLOCKED"})["status"] for check_id in check_ids]
        if "FAIL" in statuses:
            status = "FAIL"
        elif "BLOCKED" in statuses:
            status = "BLOCKED"
        else:
            status = "PASS"
        result[input_id] = {"status": status, "code": f"input-{status.lower()}"}
    return result


def report_exit_code(checks: list[dict[str, Any]]) -> int:
    if not checks:
        return 2
    statuses = {check["status"] for check in checks}
    if "FAIL" in statuses:
        return 1
    if "BLOCKED" in statuses:
        return 2
    return 0


def _assert_redacted(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in _FORBIDDEN_REPORT_KEYS:
                raise ValueError("forbidden report field")
            _assert_redacted(item)
    elif isinstance(value, list):
        for item in value:
            _assert_redacted(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if (
            "-----begin " in lowered
            or "postgresql://" in lowered
            or "postgresql+psycopg://" in lowered
            or "http://" in lowered
            or "https://" in lowered
        ):
            raise ValueError("forbidden report value")


def write_redacted_report(path: Path, report: dict[str, Any]) -> None:
    path.unlink(missing_ok=True)
    _assert_redacted(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _overall_status(checks: list[dict[str, Any]]) -> str:
    code = report_exit_code(checks)
    return {0: "PASS", 1: "FAIL", 2: "BLOCKED"}[code]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("INV_S01_BASE_URL"))
    parser.add_argument("--health-url", default=os.environ.get("INV_S01_HEALTH_URL"))
    parser.add_argument("--token-env", default="INV_S01_ACCESS_TOKEN")
    parser.add_argument("--inventory", type=Path, default=os.environ.get("INV_S01_INVENTORY"))
    parser.add_argument("--state", type=Path, default=os.environ.get("INV_LAN_PILOT_STATE"))
    parser.add_argument("--ca-bundle", type=Path, default=os.environ.get("INV_NODE_MTLS_CA_BUNDLE"))
    parser.add_argument("--http-ca-bundle", type=Path, default=os.environ.get("INV_S01_HTTP_CA_BUNDLE"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0 or args.timeout_seconds > 30:
        parser.error("--timeout-seconds must be in (0, 30]")
    output_path = args.output.resolve()
    protected_inputs = [
        path.resolve()
        for path in (args.inventory, args.ca_bundle, args.http_ca_bundle)
        if path is not None
    ]
    state_path = args.state.resolve() if args.state is not None else None
    if output_path in protected_inputs or (
        state_path is not None and (output_path == state_path or state_path in output_path.parents)
    ):
        parser.error("--output must not replace an input")
    args.output.unlink(missing_ok=True)

    token = os.environ.get(args.token_env)
    inventory = _load_inventory(args.inventory)
    inventory_check = lint_inventory(inventory)
    if args.base_url:
        fetch = http_fetcher(args.base_url, token, args.http_ca_bundle, args.timeout_seconds)
    else:
        fetch = lambda path, authenticated: (_ for _ in ()).throw(RuntimeError())
    if args.health_url:
        health_fetch = http_fetcher(
            args.health_url,
            None,
            args.http_ca_bundle,
            args.timeout_seconds,
            exact_url=True,
        )
    else:
        health_fetch = lambda path, authenticated: (_ for _ in ()).throw(RuntimeError())
    checks = probe_control_plane(
        base_url=args.base_url,
        health_url=args.health_url,
        token=token,
        fetch=fetch,
        health_fetch=health_fetch,
    )
    checks.extend(
        [
            probe_certificate_chain(args.state, inventory, args.ca_bundle),
            probe_dns(inventory),
            inventory_check,
            probe_pilot_capabilities(args.state, inventory),
        ]
    )
    report = {
        "schemaVersion": SCHEMA_VERSION,
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "readOnly": True,
        "redacted": True,
        "overallStatus": _overall_status(checks),
        "checks": checks,
        "inputs": aggregate_inputs(checks),
        "acceptanceAssessed": False,
    }
    write_redacted_report(args.output, report)
    counts = {status: sum(check["status"] == status for check in checks) for status in ("PASS", "FAIL", "BLOCKED")}
    print(json.dumps({"overallStatus": report["overallStatus"], "counts": counts}, separators=(",", ":")))
    return report_exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
