#!/usr/bin/env python3
"""Render the strict six-key ObjectStore block into a protected API config."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_SRC = ROOT / "services" / "control-plane" / "src"
if str(CONTROL_PLANE_SRC) not in sys.path:
    sys.path.insert(0, str(CONTROL_PLANE_SRC))

from inv.object_store_config import (  # noqa: E402
    parse_object_store_configuration,
)


_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_CREDENTIAL_FILE = re.compile(r"/run/saintvision/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")


def _validate_external_fields(value: dict) -> None:
    endpoint = value.get("endpoint")
    try:
        parsed = urlsplit(endpoint)
        _ = parsed.port
    except (TypeError, ValueError):
        raise ValueError("invalid ObjectStore endpoint") from None
    if (
        not isinstance(endpoint, str)
        or endpoint != endpoint.strip()
        or parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not isinstance(value.get("bucket"), str)
        or not _BUCKET.fullmatch(value["bucket"])
        or not isinstance(value.get("credentialFile"), str)
        or not _CREDENTIAL_FILE.fullmatch(value["credentialFile"])
    ):
        raise ValueError("invalid ObjectStore external field")


def render(source: dict, object_store: dict, *, node_ca_bundle: str | None) -> dict:
    if not isinstance(source, dict) or "objectStoreEndpoint" in source:
        raise ValueError("legacy or invalid API configuration")
    parse_object_store_configuration(object_store)
    _validate_external_fields(object_store)
    readiness = source.get("configurationReadiness", {})
    if not isinstance(readiness, dict) or "objectStoreEndpoint" in readiness:
        raise ValueError("legacy or invalid readiness configuration")
    readiness = dict(readiness)
    readiness["objectStore"] = object_store
    if node_ca_bundle is not None:
        if not node_ca_bundle.startswith("/run/saintvision/"):
            raise ValueError("node CA must use the protected config volume")
        readiness["nodeMtlsCaBundle"] = node_ca_bundle
    result = dict(source)
    result["configurationReadiness"] = readiness
    return result


def _write_exclusive(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)
    if os.name != "nt":
        os.chmod(path, 0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--provider-id", default="s3-compatible-intranet-v1")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--bucket", default="saintvision-objects")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--credential-file", default="/run/saintvision/object-store.json"
    )
    parser.add_argument("--prefix", default="saintvision/product")
    parser.add_argument("--node-ca-bundle")
    args = parser.parse_args(argv)
    try:
        source = json.loads(args.input.read_text(encoding="utf-8"))
        payload = render(
            source,
            {
                "providerId": args.provider_id,
                "endpoint": args.endpoint,
                "bucket": args.bucket,
                "region": args.region,
                "credentialFile": args.credential_file,
                "prefix": args.prefix,
            },
            node_ca_bundle=args.node_ca_bundle,
        )
        _write_exclusive(args.output, payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        print("ObjectStore configuration rendering refused")
        return 2
    print("ObjectStore configuration rendered; credential values were not read")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
