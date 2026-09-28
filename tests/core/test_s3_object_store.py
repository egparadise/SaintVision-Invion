"""PG-free product ObjectStore/SigV4 boundaries for the S3 adapter."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import UUID

import pytest

from inv.errors import DomainError
from inv.object_store import LocalObjectStore, ObjectDigest
from inv.s3_client import HttpResponse, S3Client, S3Config
from inv.s3_object_store import S3Objects, make_s3_locator


ROOT = Path(__file__).resolve().parents[2]
TENANT = "aaaaaaaa-1111-4111-8111-111111111111"
OBJECT = "22222222-2222-4222-8222-222222222222"
PROJECT = "proj_01JTEST"
BODY = b"immutable object bytes"
SHA = hashlib.sha256(BODY).hexdigest()
LOCATOR = make_s3_locator("product", TENANT, PROJECT, "objects", OBJECT)


class FakeClient:
    def __init__(self):
        self.calls = []
        self.put_response = HttpResponse(200, {}, b"")
        self.get_response = HttpResponse(
            200, {"x-amz-meta-content-sha256": SHA}, BODY
        )
        self.head_response = HttpResponse(200, {}, b"")
        self.delete_response = HttpResponse(204, {}, b"")
        self.put_error = None

    def request(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        return HttpResponse(200, {}, b"")

    def put(self, key, body, digest):
        self.calls.append(("PUT", key, body, digest))
        if self.put_error:
            raise self.put_error
        return self.put_response

    def get(self, key):
        self.calls.append(("GET", key))
        return self.get_response

    def head(self, key):
        self.calls.append(("HEAD", key))
        return self.head_response

    def delete(self, key):
        self.calls.append(("DELETE", key))
        return self.delete_response


def store(client=None):
    return S3Objects("s3-compatible-v1", "product", client or FakeClient())


def test_server_builds_only_canonical_scoped_locators():
    assert LOCATOR == (
        "product/v1/tenants/aaaaaaaa-1111-4111-8111-111111111111/"
        "projects/proj_01JTEST/objects/22222222-2222-4222-8222-222222222222"
    )
    assert UUID(LOCATOR.rsplit("/", 1)[1]) == UUID(OBJECT)
    with pytest.raises(ValueError):
        make_s3_locator("product", TENANT, "../foreign", "objects", OBJECT)
    with pytest.raises(ValueError):
        make_s3_locator("product", TENANT, PROJECT, "unbounded", OBJECT)


@pytest.mark.parametrize(
    "locator",
    [
        "../product/" + LOCATOR,
        LOCATOR.replace("/objects/", "/unknown/"),
        LOCATOR.replace(TENANT, TENANT.upper()),
        LOCATOR + "/extra",
    ],
)
def test_provider_rejects_noncanonical_or_outside_prefix_locators(locator):
    with pytest.raises(DomainError) as error:
        store().exists(locator)
    assert error.value.code == "STORE-0002"


def test_put_get_hash_and_idempotent_timeout_use_actual_bytes_not_etag():
    client = FakeClient()
    client.put_error = TimeoutError("provider detail must not escape")
    provider = store(client)

    provider.put(LOCATOR, BODY, SHA)
    assert provider.get(LOCATOR, SHA, len(BODY)) == BODY
    assert provider.hash(LOCATOR) == ObjectDigest(SHA, len(BODY))
    assert [call[0] for call in client.calls] == ["PUT", "GET", "GET", "GET"]


def test_put_access_denied_is_never_lowered_to_idempotent_success():
    client = FakeClient()
    client.put_response = HttpResponse(403, {}, b"")
    with pytest.raises(DomainError) as error:
        store(client).put(LOCATOR, BODY, SHA)
    assert error.value.code == "STORE-0001" and error.value.retryable is True
    assert [call[0] for call in client.calls] == ["PUT"]


@pytest.mark.parametrize("damage", ["body", "metadata", "size"])
def test_get_fails_closed_on_every_integrity_drift(damage):
    client = FakeClient()
    if damage == "body":
        client.get_response = HttpResponse(
            200, {"x-amz-meta-content-sha256": SHA}, b"different"
        )
    elif damage == "metadata":
        client.get_response = HttpResponse(200, {"x-amz-meta-content-sha256": "0" * 64}, BODY)
    expected_size = len(BODY) + 1 if damage == "size" else len(BODY)
    with pytest.raises(DomainError) as error:
        store(client).get(LOCATOR, SHA, expected_size)
    assert error.value.code == "VERIFY-0010"


def test_delete_requires_a_subsequent_not_found_observation():
    client = FakeClient()
    provider = store(client)
    with pytest.raises(DomainError) as error:
        provider.delete(LOCATOR)
    assert error.value.code == "STORE-0001" and error.value.retryable is True
    client.head_response = HttpResponse(404, {}, b"")
    provider.delete(LOCATOR)


class FakeFiles:
    def __init__(self):
        self.body = None

    def put(self, locator, body, digest):
        assert hashlib.sha256(body).hexdigest() == digest
        self.body = body

    def read(self, locator, digest, size):
        assert len(self.body) == size and hashlib.sha256(self.body).hexdigest() == digest
        return self.body

    def exists(self, locator):
        return self.body is not None

    def hash(self, locator):
        return ObjectDigest(hashlib.sha256(self.body).hexdigest(), len(self.body))

    def remove(self, locator):
        self.body = None


class FakeLocal:
    def __init__(self):
        self.files = FakeFiles()

    @contextmanager
    def locked(self):
        yield self.files


def test_local_objects_are_exposed_through_the_same_spi_without_scope_discard():
    provider = LocalObjectStore(FakeLocal())
    locator = "obj-" + UUID(OBJECT).hex
    provider.put(locator, BODY, SHA)
    assert provider.exists(locator) is True
    assert provider.get(locator, SHA, len(BODY)) == BODY
    assert provider.hash(locator) == ObjectDigest(SHA, len(BODY))
    provider.delete(locator)
    assert provider.exists(locator) is False
    assert provider.provider_id == "local-bounded-v1"


def test_the_preflight_imports_the_product_signer_instead_of_copying_it():
    spec = importlib.util.spec_from_file_location(
        "verify_storage_roundtrip_shared", ROOT / "tools" / "verify_storage_roundtrip.py"
    )
    verifier = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(verifier)
    assert verifier.S3Client is S3Client
    assert not hasattr(verifier, "_sign")


def test_public_request_contracts_never_accept_object_id_or_provider_locator():
    schema = json.loads(
        (ROOT / "contracts" / "v1alpha1" / "core.schema.json").read_text(encoding="utf-8")
    )
    request_names = {
        name
        for name in schema["$defs"]
        if name.endswith(("Input", "Request", "Spec", "Command"))
    }
    violations = {
        name: sorted({"objectId", "locator"} & set(schema["$defs"][name].get("properties", {})))
        for name in request_names
        if {"objectId", "locator"} & set(schema["$defs"][name].get("properties", {}))
    }
    standalone_requests = sorted((ROOT / "contracts").glob("*-request.schema.json"))
    for path in standalone_requests:
        properties = json.loads(path.read_text(encoding="utf-8")).get("properties", {})
        leaked = sorted({"objectId", "locator"} & set(properties))
        if leaked:
            violations[path.name] = leaked
    assert violations == {}


def test_sigv4_path_encoding_is_deterministic_and_secret_free_from_url():
    transport = FakeClient()
    # Reuse only its request recording surface; S3Client does not depend on its
    # higher-level methods.
    config = S3Config(
        "https://storage.invalid:9443", "bucket-name", "ACCESS", "secret-value", "us-east-1"
    )
    client = S3Client(config, transport)
    response = client._request(
        "GET", "prefix/a space", now=datetime(2026, 9, 28, tzinfo=timezone.utc)
    )
    assert response.status == 200
    method, url, headers, body = transport.calls[0]
    assert method == "GET" and url.endswith("/bucket-name/prefix/a%20space")
    assert "secret-value" not in url and "secret-value" not in json.dumps(headers)
    assert headers["authorization"].startswith("AWS4-HMAC-SHA256 Credential=ACCESS/")
