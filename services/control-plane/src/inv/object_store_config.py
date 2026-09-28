"""Strict protected configuration for product ObjectStore providers."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from .s3_client import S3Client, S3Config
from .s3_object_store import S3Objects

ENDPOINT_SETTING = "INV_OBJECT_STORE_ENDPOINT"
BUCKET_SETTING = "INV_OBJECT_STORE_BUCKET"
CREDENTIAL_SETTING = "INV_OBJECT_STORE_CREDENTIAL_FILE"
OBJECT_STORE_SETTINGS = frozenset({ENDPOINT_SETTING, BUCKET_SETTING, CREDENTIAL_SETTING})
_KEYS = frozenset({"providerId", "endpoint", "bucket", "region", "credentialFile", "prefix"})
_PROVIDER = re.compile(r"[a-z0-9][a-z0-9.-]{0,63}")
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")
_REGION = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_CONFIG_PATH = re.compile(r"/run/saintvision/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")
_RESERVED_PROVIDER_IDS = frozenset({"local-bounded-v1"})


@dataclass(frozen=True)
class ObjectStoreConfiguration:
    provider_id: str
    endpoint: str
    bucket: str
    region: str
    credential_file: str
    prefix: str


def _canonical_endpoint(value):
    if not isinstance(value, str) or value != value.strip() or not value:
        return None
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        return None
    return value.rstrip("/")


def parse_object_store_configuration(value):
    """Parse structure once; unknown/missing inner keys refuse startup."""

    if not isinstance(value, dict) or set(value) != _KEYS:
        raise ValueError("Invalid objectStore settings")
    provider_id = value["providerId"]
    region = value["region"]
    prefix = value["prefix"]
    if (
        not isinstance(provider_id, str)
        or not _PROVIDER.fullmatch(provider_id)
        or provider_id in _RESERVED_PROVIDER_IDS
        or not isinstance(region, str)
        or not _REGION.fullmatch(region)
        or not isinstance(prefix, str)
        or prefix.startswith("/")
        or prefix.endswith("/")
        or any(
            not _SEGMENT.fullmatch(segment) or segment in {".", ".."}
            for segment in (prefix.split("/") if prefix else ())
        )
    ):
        raise ValueError("Invalid objectStore settings")
    return ObjectStoreConfiguration(
        provider_id,
        value["endpoint"],
        value["bucket"],
        region,
        value["credentialFile"],
        prefix,
    )


def _private_file(path):
    if not isinstance(path, str) or not _CONFIG_PATH.fullmatch(path):
        raise ValueError("Invalid objectStore credential file")
    target = Path(path)
    before = target.lstat()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags)
    try:
        observed = os.fstat(descriptor)
        if (
            not stat.S_ISREG(observed.st_mode)
            or observed.st_nlink != 1
            or observed.st_size > 4096
            or (os.name != "nt" and observed.st_mode & 0o077)
            or (before.st_dev, before.st_ino) != (observed.st_dev, observed.st_ino)
        ):
            raise ValueError("Invalid objectStore credential file")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read(4097)
    finally:
        os.close(descriptor)


def read_object_store_credentials(path):
    try:
        value = json.loads(_private_file(path))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("Invalid objectStore credential file") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"accessKeyId", "secretAccessKey"}
        or not isinstance(value["accessKeyId"], str)
        or not 1 <= len(value["accessKeyId"]) <= 128
        or not isinstance(value["secretAccessKey"], str)
        or not 1 <= len(value["secretAccessKey"]) <= 256
    ):
        raise ValueError("Invalid objectStore credential file")
    return value["accessKeyId"], value["secretAccessKey"]


def unresolved_object_store(configuration):
    missing = []
    if _canonical_endpoint(configuration.endpoint) is None:
        missing.append(ENDPOINT_SETTING)
    if not isinstance(configuration.bucket, str) or not _BUCKET.fullmatch(configuration.bucket):
        missing.append(BUCKET_SETTING)
    try:
        read_object_store_credentials(configuration.credential_file)
    except ValueError:
        missing.append(CREDENTIAL_SETTING)
    return sorted(missing)


def configured_object_store(configuration, *, transport=None):
    missing = unresolved_object_store(configuration)
    if missing:
        raise ValueError("ObjectStore configuration is not ready")
    access_key, secret_key = read_object_store_credentials(configuration.credential_file)
    client = S3Client(
        S3Config(
            _canonical_endpoint(configuration.endpoint),
            configuration.bucket,
            access_key,
            secret_key,
            configuration.region,
        ),
        transport,
    )
    return S3Objects(configuration.provider_id, configuration.prefix, client)
