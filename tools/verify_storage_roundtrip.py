#!/usr/bin/env python3
"""Verify one redacted S3-compatible candidate byte roundtrip.

The verifier owns one random object only. It never lists a bucket, changes a
lifecycle policy, logs provider errors, or treats this preflight as a product adapter.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import uuid4
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_SRC = ROOT / "services" / "control-plane" / "src"
if str(CONTROL_PLANE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_SRC))

from inv.s3_client import (  # noqa: E402
    HttpResponse,
    S3Client,
    S3Config as Config,
    UrlLibTransport,
)


EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
_FLAT_CREDENTIAL_PATH = re.compile(
    r"/run/saintvision/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}"
)
_BUCKET = re.compile(r"[a-z0-9](?:[a-z0-9.-]{1,61}[a-z0-9])?")
_REGION = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_SHA = re.compile(r"[0-9a-f]{40}")


class Blocked(Exception):
    """Required trusted inputs are absent or ambiguous."""


def _trusted_credential_file(path):
    target = Path(path)
    info = target.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_size > 65536
        or (os.name != "nt" and info.st_mode & 0o077)
    ):
        raise Blocked()
    return target.read_bytes()


def _strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise Blocked()
            result[key] = value
        return result

    try:
        value = json.loads(
            raw,
            object_pairs_hook=pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(Blocked()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise Blocked() from None
    if not isinstance(value, dict):
        raise Blocked()
    return value


def _credentials(environment):
    access = environment.get("INV_OBJECT_STORE_ACCESS_KEY_ID")
    secret = environment.get("INV_OBJECT_STORE_SECRET_ACCESS_KEY")
    reference = environment.get("INV_OBJECT_STORE_CREDENTIAL_FILE")
    if reference and (access or secret):
        raise Blocked()
    region = environment.get("INV_OBJECT_STORE_REGION", "us-east-1")
    if reference:
        if not _FLAT_CREDENTIAL_PATH.fullmatch(reference):
            raise Blocked()
        value = _strict_json(_trusted_credential_file(reference))
        if set(value) - {"accessKeyId", "secretAccessKey", "region"}:
            raise Blocked()
        access = value.get("accessKeyId")
        secret = value.get("secretAccessKey")
        region = value.get("region", region)
    if (
        not isinstance(access, str)
        or not 1 <= len(access) <= 128
        or not access.isascii()
        or not isinstance(secret, str)
        or not 8 <= len(secret) <= 256
        or not secret.isascii()
        or not isinstance(region, str)
        or not _REGION.fullmatch(region)
    ):
        raise Blocked()
    return access, secret, region


def load_config(environment):
    endpoint = environment.get("INV_OBJECT_STORE_ENDPOINT")
    bucket = environment.get("INV_OBJECT_STORE_BUCKET")
    if not isinstance(endpoint, str) or endpoint != endpoint.strip():
        raise Blocked()
    try:
        parsed = urlsplit(endpoint)
        _ = parsed.port
    except ValueError:
        raise Blocked() from None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise Blocked()
    if (
        not isinstance(bucket, str)
        or not _BUCKET.fullmatch(bucket)
        or ".." in bucket
        or re.fullmatch(r"\d+\.\d+\.\d+\.\d+", bucket)
    ):
        raise Blocked()
    access, secret, region = _credentials(environment)
    target_kind = environment.get("INV_OBJECT_STORE_TARGET_KIND")
    if target_kind not in {"ci-candidate", "operational"}:
        raise Blocked()
    config = Config(endpoint.rstrip("/"), bucket, access, secret, region)
    config.target_kind = target_kind
    return config


def _code_sha(environment):
    value = (
        environment.get("INV_EVIDENCE_CODE_SHA")
        or environment.get("GITHUB_HEAD_SHA")
        or environment.get("GITHUB_SHA")
    )
    if isinstance(value, str) and _SHA.fullmatch(value.lower()):
        return value.lower()
    try:
        value = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip().lower()
    except Exception:
        return "UNMEASURED"
    return value if _SHA.fullmatch(value) else "UNMEASURED"


def _evidence(environment, status, checks, payload_bytes, target_kind=None):
    return {
        "schemaVersion": "1.1",
        "status": status,
        "targetKind": target_kind,
        "checks": checks,
        "payloadBytes": payload_bytes,
        "cleanupVerified": checks["cleanupVerified"],
        "codeSha": _code_sha(environment),
        "observedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def execute(environment, *, transport=None, payload=None):
    target_kind = environment.get("INV_OBJECT_STORE_TARGET_KIND")
    if target_kind not in {"ci-candidate", "operational"}:
        raise Blocked()
    checks = {
        "put": False,
        "get": False,
        "bodySha256": False,
        "metadataSha256": False,
        "delete": False,
        "cleanupVerified": False,
    }
    payload = payload if isinstance(payload, bytes) else os.urandom(32)
    try:
        config = load_config(environment)
    except (Blocked, OSError):
        return _evidence(environment, "BLOCKED", checks, 0, target_kind), 3

    client = S3Client(config, transport)
    key = "saintvision-u6/roundtrip-" + uuid4().hex
    digest = hashlib.sha256(payload).hexdigest()
    try:
        response = client.put(key, payload, digest)
        checks["put"] = response.status in {200, 201, 204}
        if checks["put"]:
            response = client.get(key)
            checks["get"] = response.status == 200
            if checks["get"]:
                checks["bodySha256"] = hashlib.sha256(response.body).hexdigest() == digest
                checks["metadataSha256"] = (
                    response.headers.get("x-amz-meta-content-sha256") == digest
                )
    except Exception:
        # Provider and framework exception strings are deliberately suppressed.
        pass
    finally:
        try:
            deleted = client.delete(key)
            checks["delete"] = deleted.status in {200, 202, 204}
            if checks["delete"]:
                checks["cleanupVerified"] = client.get(key).status == 404
        except Exception:
            pass

    status = "PASS" if all(checks.values()) else "FAIL"
    return _evidence(
        environment, status, checks, len(payload), config.target_kind
    ), (0 if status == "PASS" else 1)


def write_outputs(evidence, output_path, junit_path):
    output_path, junit_path = Path(output_path), Path(junit_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    failures = "1" if evidence["status"] == "FAIL" else "0"
    skipped = "1" if evidence["status"] == "BLOCKED" else "0"
    suite = ET.Element(
        "testsuite", name="s01-storage-roundtrip", tests="1", failures=failures, errors="0", skipped=skipped
    )
    case = ET.SubElement(suite, "testcase", classname="s01.storage", name="storage_sha256_roundtrip")
    if evidence["status"] == "FAIL":
        ET.SubElement(case, "failure", message="redacted storage verification failure")
    elif evidence["status"] == "BLOCKED":
        ET.SubElement(case, "skipped", message="required object-store inputs unavailable")
    ET.ElementTree(suite).write(junit_path, encoding="unicode", xml_declaration=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist/s01-storage-roundtrip.json")
    parser.add_argument("--junit", default="dist/s01-storage-roundtrip.xml")
    parser.add_argument(
        "--target-kind", choices=("ci-candidate", "operational"), required=True
    )
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    environment["INV_OBJECT_STORE_TARGET_KIND"] = args.target_kind
    evidence, exit_code = execute(environment)
    write_outputs(evidence, args.output, args.junit)
    print(json.dumps(evidence, sort_keys=True, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
