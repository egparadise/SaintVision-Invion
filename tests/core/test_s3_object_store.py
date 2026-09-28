"""PG-free product ObjectStore/SigV4 boundaries for the S3 adapter."""

from contextlib import contextmanager
from datetime import datetime, timezone
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import UUID

import pytest

from inv.errors import DomainError
from inv.object_store import LocalObjectStore, ObjectDigest
from inv.s3_client import HttpResponse, S3Client, S3Config, _authorization
from inv.s3_object_store import S3Objects, make_s3_locator

ROOT = Path(__file__).resolve().parents[2]
TENANT = "aaaaaaaa-1111-4111-8111-111111111111"
OBJECT = "22222222-2222-4222-8222-222222222222"
PROJECT = "proj_01JTEST"
BODY = b"immutable object bytes"
SHA = hashlib.sha256(BODY).hexdigest()
LOCATOR = make_s3_locator("product", TENANT, PROJECT, "objects", OBJECT)


def _route_parameter_names(function):
    arguments = [
        *function.args.posonlyargs,
        *function.args.args,
        *function.args.kwonlyargs,
    ]
    names = {argument.arg.replace("_", "").lower() for argument in arguments}
    parameter_nodes = [
        *(argument.annotation for argument in arguments if argument.annotation),
        *function.args.defaults,
        *(default for default in function.args.kw_defaults if default),
    ]
    for node in parameter_nodes:
        for call in (child for child in ast.walk(node) if isinstance(child, ast.Call)):
            for keyword in call.keywords:
                if (
                    keyword.arg == "alias"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    names.add(keyword.value.value.replace("_", "").lower())
    return names


class FakeClient:
    def __init__(self):
        self.calls = []
        self.put_response = HttpResponse(200, {}, b"")
        self.get_response = HttpResponse(200, {"x-amz-meta-content-sha256": SHA}, BODY)
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


def test_conditional_put_conflict_preserves_existing_bytes_and_is_not_success():
    client = FakeClient()
    client.put_response = HttpResponse(412, {}, b"")
    different = b"replacement must not overwrite committed bytes"
    with pytest.raises(DomainError) as error:
        store(client).put(LOCATOR, different, hashlib.sha256(different).hexdigest())
    assert error.value.code == "STORE-0005" and error.value.status == 409
    assert client.get_response.body == BODY
    assert [call[0] for call in client.calls] == ["PUT", "GET"]


@pytest.mark.parametrize("damage", ["body", "metadata", "size"])
def test_get_fails_closed_on_every_integrity_drift(damage):
    client = FakeClient()
    if damage == "body":
        client.get_response = HttpResponse(200, {"x-amz-meta-content-sha256": SHA}, b"different")
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
    different = b"replacement"
    with pytest.raises(DomainError) as error:
        provider.put(locator, different, hashlib.sha256(different).hexdigest())
    assert error.value.code == "STORE-0005" and error.value.status == 409
    assert provider.get(locator, SHA, len(BODY)) == BODY
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
        name for name in schema["$defs"] if name.endswith(("Input", "Request", "Spec", "Command"))
    }

    def property_names(value, definitions, seen=frozenset()):
        if not isinstance(value, dict):
            return set()
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            name = reference.rsplit("/", 1)[1]
            if name in seen:
                return set()
            return property_names(definitions[name], definitions, seen | {name})
        found = set(value.get("properties", {}))
        for child in value.values():
            if isinstance(child, dict):
                found |= property_names(child, definitions, seen)
            elif isinstance(child, list):
                for item in child:
                    found |= property_names(item, definitions, seen)
        return found

    forbidden = {"objectId", "locator"}
    violations = {
        name: sorted(forbidden & property_names(schema["$defs"][name], schema["$defs"], {name}))
        for name in request_names
        if forbidden & property_names(schema["$defs"][name], schema["$defs"], {name})
    }
    standalone_requests = sorted((ROOT / "contracts").glob("*-request.schema.json"))
    for path in standalone_requests:
        standalone = json.loads(path.read_text(encoding="utf-8"))
        leaked = sorted(forbidden & property_names(standalone, standalone.get("$defs", {})))
        if leaked:
            violations[path.name] = leaked
    app = ast.parse(
        (ROOT / "services/control-plane/src/inv/app.py").read_text(encoding="utf-8-sig")
    )
    verbs = {"get", "post", "put", "patch", "delete", "websocket"}
    for function in (
        node for node in ast.walk(app) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ):
        routes = [
            decorator
            for decorator in function.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in verbs
        ]
        if not routes:
            continue
        parameters = _route_parameter_names(function)
        if {"objectid", "locator"} & parameters:
            violations[f"route:{function.name}:parameters"] = sorted(parameters)
        for route in routes:
            if route.args and isinstance(route.args[0], ast.Constant):
                value = str(route.args[0].value).replace("_", "").lower()
                if "{objectid" in value or "{locator" in value:
                    violations[f"route:{function.name}:path"] = [str(route.args[0].value)]
    assert violations == {}


def test_route_input_scanner_includes_keyword_only_and_fastapi_aliases():
    tree = ast.parse("""
def route(positional, *, hidden=Query(None, alias="objectId"), other: Annotated[str, Query(alias="locator")]):
    pass
""")
    names = _route_parameter_names(tree.body[0])
    assert {"positional", "hidden", "other", "objectid", "locator"} <= names


@pytest.mark.parametrize("provider_id", ["local-bounded-v1", "Uppercase.Provider"])
def test_s3_provider_requires_lowercase_non_reserved_identity(provider_id):
    with pytest.raises(ValueError, match="Stable provider id"):
        S3Objects(provider_id, "product", FakeClient())


def test_config_secret_is_not_exposed_by_repr():
    config = S3Config("https://storage.invalid", "bucket", "ACCESS", "secret-value", "us-east-1")
    assert "secret-value" not in repr(config)


def test_locator_from_another_configured_prefix_is_retryable_unavailable():
    provider = S3Objects("s3-compatible-v1", "current", FakeClient())
    other = make_s3_locator("retired", TENANT, PROJECT, "objects", OBJECT)
    with pytest.raises(DomainError) as raised:
        provider.get(other, SHA, len(BODY))
    assert (raised.value.code, raised.value.status, raised.value.retryable) == (
        "STORE-0001",
        503,
        True,
    )


def test_locator_with_nested_configured_prefix_drift_is_retryable_unavailable():
    provider = S3Objects("s3-compatible-v1", "product", FakeClient())
    nested = make_s3_locator("product/nested", TENANT, PROJECT, "objects", OBJECT)
    with pytest.raises(DomainError) as raised:
        provider.validate_locator(nested)
    assert (raised.value.code, raised.value.status, raised.value.retryable) == (
        "STORE-0001",
        503,
        True,
    )


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


def test_put_condition_is_signed_so_an_intermediary_cannot_strip_it():
    transport = FakeClient()
    client = S3Client(
        S3Config("https://storage.invalid", "bucket", "ACCESS", "secret", "us-east-1"),
        transport,
    )
    client.put("object", BODY, SHA)
    headers = transport.calls[0][2]
    assert headers["if-none-match"] == "*"
    assert "SignedHeaders=host;if-none-match;x-amz-content-sha256;" in headers["authorization"]


def test_sigv4_matches_the_aws_s3_get_object_known_answer_vector():
    """AWS S3 SigV4 guide, GET Object example dated 2013-05-24."""

    empty_sha = hashlib.sha256(b"").hexdigest()
    config = S3Config(
        "https://examplebucket.s3.amazonaws.com",
        "examplebucket",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
    )
    authorization = _authorization(
        config,
        "GET",
        "/test.txt",
        {
            "host": "examplebucket.s3.amazonaws.com",
            "range": "bytes=0-9",
            "x-amz-content-sha256": empty_sha,
            "x-amz-date": "20130524T000000Z",
        },
        b"",
    )
    assert authorization == (
        "AWS4-HMAC-SHA256 "
        "Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request, "
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date, "
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
