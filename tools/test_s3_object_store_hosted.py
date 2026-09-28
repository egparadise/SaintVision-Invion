"""Hosted-only product ObjectStore conformance against disposable MinIO."""

import hashlib
import os
from uuid import uuid4

from inv.object_store import LocalObjectStore, LocalObjects
from inv.s3_client import S3Client, S3Config
from inv.s3_object_store import S3Objects, make_s3_locator


def test_product_adapter_put_get_exists_hash_delete():
    required = (
        "INV_OBJECT_STORE_ENDPOINT",
        "INV_OBJECT_STORE_BUCKET",
        "INV_OBJECT_STORE_ACCESS_KEY_ID",
        "INV_OBJECT_STORE_SECRET_ACCESS_KEY",
        "INV_OBJECT_STORE_REGION",
    )
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, f"hosted object-store inputs missing: {missing}"
    client = S3Client(
        S3Config(
            os.environ["INV_OBJECT_STORE_ENDPOINT"].rstrip("/"),
            os.environ["INV_OBJECT_STORE_BUCKET"],
            os.environ["INV_OBJECT_STORE_ACCESS_KEY_ID"],
            os.environ["INV_OBJECT_STORE_SECRET_ACCESS_KEY"],
            os.environ["INV_OBJECT_STORE_REGION"],
        )
    )
    provider = S3Objects("s3-compatible-v1", "product-conformance", client)
    object_id = str(uuid4())
    locator = make_s3_locator(
        "product-conformance",
        "11111111-1111-4111-8111-111111111111",
        "project_hosted_conformance",
        "objects",
        object_id,
    )
    body = b"saintvision product object-store conformance\n"
    digest = hashlib.sha256(body).hexdigest()
    try:
        assert provider.exists(locator) is False
        provider.put(locator, body, digest)
        assert provider.exists(locator) is True
        assert provider.get(locator, digest, len(body)) == body
        measured = provider.hash(locator)
        assert measured.sha256 == digest and measured.size_bytes == len(body)
    finally:
        provider.delete(locator)
    assert provider.exists(locator) is False


def test_local_compatibility_adapter_uses_the_same_conformance(tmp_path):
    root = tmp_path / "objects"
    root.mkdir(mode=0o700)
    provider = LocalObjectStore(LocalObjects(root))
    locator = "obj-" + uuid4().hex
    body = b"saintvision local object-store conformance\n"
    digest = hashlib.sha256(body).hexdigest()
    assert provider.exists(locator) is False
    provider.put(locator, body, digest)
    assert provider.exists(locator) is True
    assert provider.get(locator, digest, len(body)) == body
    measured = provider.hash(locator)
    assert measured.sha256 == digest and measured.size_bytes == len(body)
    provider.delete(locator)
    assert provider.exists(locator) is False
