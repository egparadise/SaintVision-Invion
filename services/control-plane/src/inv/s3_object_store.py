"""Immutable bounded ObjectStore adapter for S3-compatible providers."""

from __future__ import annotations

import hashlib
import re
from uuid import UUID

from .errors import DomainError
from .object_store import MAX_BYTES, ObjectDigest
from .s3_client import S3Client


_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_NAMESPACES = frozenset({"objects", "run-outputs", "workspace-outputs", "checkpoints"})


def _prefix_segments(prefix: str) -> tuple[str, ...]:
    if not isinstance(prefix, str) or prefix.startswith("/") or prefix.endswith("/"):
        raise ValueError("S3 object prefix must be a relative canonical path")
    values = tuple(prefix.split("/")) if prefix else ()
    if any(not _SEGMENT.fullmatch(value) or value in {".", ".."} for value in values):
        raise ValueError("S3 object prefix must be a relative canonical path")
    return values


def make_s3_locator(prefix, tenant_id, project_id, namespace, object_id):
    """Build a server-owned provider key; no HTTP field accepts this value."""

    base = _prefix_segments(prefix)
    tenant = str(UUID(str(tenant_id)))
    project = str(project_id)
    object_uuid = str(UUID(str(object_id)))
    if not _SEGMENT.fullmatch(project) or namespace not in _NAMESPACES:
        raise ValueError("Object scope is not canonical")
    return "/".join(
        (*base, "v1", "tenants", tenant, "projects", project, namespace, object_uuid)
    )


class S3Objects:
    """Bounded immutable provider using persisted scoped opaque locators."""

    def __init__(self, provider_id: str, prefix: str, client: S3Client):
        if not _SEGMENT.fullmatch(provider_id):
            raise ValueError("Stable provider id required")
        self.provider_id = provider_id
        self._prefix = _prefix_segments(prefix)
        self.client = client

    def _key(self, locator: str) -> str:
        if not isinstance(locator, str) or locator.startswith("/") or locator.endswith("/"):
            raise DomainError("STORE-0002", "Invalid object locator", 422)
        values = tuple(locator.split("/"))
        suffix = values[len(self._prefix) :]
        if values[: len(self._prefix)] != self._prefix or len(suffix) != 7:
            raise DomainError("STORE-0002", "Invalid object locator", 422)
        version, tenants, tenant, projects, project, namespace, object_id = suffix
        try:
            canonical_tenant = str(UUID(tenant))
            canonical_object = str(UUID(object_id))
        except (ValueError, AttributeError):
            raise DomainError("STORE-0002", "Invalid object locator", 422) from None
        if (
            version != "v1"
            or tenants != "tenants"
            or projects != "projects"
            or tenant != canonical_tenant
            or object_id != canonical_object
            or not _SEGMENT.fullmatch(project)
            or namespace not in _NAMESPACES
        ):
            raise DomainError("STORE-0002", "Invalid object locator", 422)
        return locator

    @staticmethod
    def _expected(body, digest, size=None):
        if (
            not isinstance(body, bytes)
            or not isinstance(digest, str)
            or not _SHA256.fullmatch(digest)
            or len(body) > MAX_BYTES
            or (size is not None and (type(size) is not int or size != len(body)))
            or hashlib.sha256(body).hexdigest() != digest
        ):
            raise DomainError("VERIFY-0010", "Object content differs", 422)

    @staticmethod
    def _unavailable():
        return DomainError("STORE-0001", "Object provider unavailable", 503, True)

    def _read(self, key):
        try:
            response = self.client.get(key)
        except Exception:
            raise self._unavailable() from None
        if response.status == 404:
            raise FileNotFoundError from None
        if response.status != 200:
            raise self._unavailable()
        if len(response.body) > MAX_BYTES:
            raise DomainError("STORE-0003", "Object exceeds bounded size", 422)
        return response

    def put(self, locator, body, expected_sha256):
        key = self._key(locator)
        self._expected(body, expected_sha256)
        try:
            response = self.client.put(key, body, expected_sha256)
            published = response.status in {200, 201, 204}
            ambiguous = response.status in {409, 412} or response.status >= 500
        except Exception:
            published = False
            ambiguous = True
        if not published and not ambiguous:
            raise self._unavailable()
        # A timeout is ambiguous and a conflict may be an idempotent replay.
        # Only an actual byte read can complete either case.
        try:
            observed = self._read(key)
        except FileNotFoundError:
            raise self._unavailable() from None
        actual = hashlib.sha256(observed.body).hexdigest()
        metadata = observed.headers.get("x-amz-meta-content-sha256")
        if (
            actual == expected_sha256
            and len(observed.body) == len(body)
            and metadata == expected_sha256
        ):
            return
        if not published:
            raise DomainError("STORE-0005", "Immutable object already differs", 409)
        raise DomainError("VERIFY-0010", "Stored object checksum differs", 422)

    def get(self, locator, expected_sha256, expected_size):
        key = self._key(locator)
        response = self._read(key)
        self._expected(response.body, expected_sha256, expected_size)
        metadata = response.headers.get("x-amz-meta-content-sha256")
        if metadata != expected_sha256:
            raise DomainError("VERIFY-0010", "Stored object checksum differs", 422)
        return response.body

    def exists(self, locator):
        key = self._key(locator)
        try:
            response = self.client.head(key)
        except Exception:
            raise self._unavailable() from None
        if response.status == 200:
            return True
        if response.status == 404:
            return False
        raise self._unavailable()

    def hash(self, locator):
        response = self._read(self._key(locator))
        return ObjectDigest(hashlib.sha256(response.body).hexdigest(), len(response.body))

    def delete(self, locator):
        key = self._key(locator)
        try:
            response = self.client.delete(key)
        except Exception:
            raise self._unavailable() from None
        if response.status not in {200, 202, 204, 404}:
            raise self._unavailable()
        if self.exists(locator):
            raise DomainError("STORE-0001", "Object remained after deletion", 503, True)
