"""Bind the kernel's raw artifact bytes and their HTTP headers to one shared contract."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager, nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import inv.app as kernel_app
from inv.app import create_app
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.object_store import LocalObjectStore, ObjectStoreRegistry
from inv.result_view import ResultView

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "contracts" / "fixtures" / "artifact-content-response.json"
BODY = b"artifact-content-contract-fixture\n"
ARTIFACT = {
    "path": "outputs/metrics.json",
    "checksumSha256": hashlib.sha256(BODY).hexdigest(),
    "byteSize": len(BODY),
    "verified": True,
    "evidenceId": "evd_00000000000000000000000000",
}


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        ResultView,
        "download",
        lambda self, principal, run_id, path, project=None: {
            "content": BODY,
            "artifact": ARTIFACT,
        },
    )

    class Tokens:
        @staticmethod
        def verify(_token):
            return SimpleNamespace(principal=object())

    return TestClient(
        create_app(database=object(), tokens=Tokens()),
        raise_server_exceptions=False,
    )


def test_shared_artifact_content_metadata_fixture_matches_contract():
    payload = _fixture()
    validate_contract("ArtifactContentResponse", payload)
    assert payload["artifact"] == ARTIFACT


def _view_with_committed_file(monkeypatch, content: bytes) -> ResultView:
    stored = b'{"stored":"provider-object"}'

    class Database:
        @staticmethod
        def transaction(_tenant_id):
            return nullcontext(object())

    class Provider:
        provider_id = "s3-compatible-v1"

        @staticmethod
        def get(locator, digest, size):
            assert locator == "scoped/provider/locator"
            assert digest == hashlib.sha256(stored).hexdigest() and size == len(stored)
            return stored

    monkeypatch.setattr(
        ResultView,
        "_scope",
        lambda self, conn, principal, project, run_id: {
            "run_id": run_id,
            "project_id": "prj_contract",
            "attempt": 1,
        },
    )
    evidence = {"outputSha256": hashlib.sha256(stored).hexdigest()}
    monkeypatch.setattr(
        ResultView,
        "_current",
        staticmethod(
            lambda conn, run: {
                "evidence_id": ARTIFACT["evidenceId"],
                "evidence": evidence,
                "commitment": evidence,
                "object_state": "ready",
                "object_id": "22222222-2222-4222-8222-222222222222",
                "provider_id": "s3-compatible-v1",
                "locator": "scoped/provider/locator",
                "content_hash": hashlib.sha256(stored).hexdigest(),
                "size_bytes": len(stored),
                "delivery": {"payload": "unused-by-test-double"},
            }
        ),
    )
    monkeypatch.setattr(
        ResultView,
        "_files",
        staticmethod(
            lambda row, artifact: (
                {
                    "files": [
                        {
                            "path": ARTIFACT["path"],
                            "sha256": ARTIFACT["checksumSha256"],
                            "sizeBytes": ARTIFACT["byteSize"],
                        }
                    ]
                },
                {ARTIFACT["path"]: content},
            )
        ),
    )
    return ResultView(Database(), ObjectStoreRegistry([Provider()]))


def test_result_view_download_preserves_the_manifest_artifact_record(monkeypatch):
    principal = SimpleNamespace(tenant_id="tenant-contract")
    download = _view_with_committed_file(monkeypatch, BODY).download(
        principal, "run_00000000000000000000000000", ARTIFACT["path"]
    )
    assert download == {"content": BODY, "artifact": ARTIFACT}


def test_result_view_download_refuses_bytes_that_disagree_with_manifest(monkeypatch):
    principal = SimpleNamespace(tenant_id="tenant-contract")
    with pytest.raises(DomainError, match="Committed artifact bytes differ"):
        _view_with_committed_file(monkeypatch, b"different bytes").download(
            principal, "run_00000000000000000000000000", ARTIFACT["path"]
        )


def test_result_view_download_has_no_receipt_fallback_when_provider_is_unavailable(
    monkeypatch,
):
    principal = SimpleNamespace(tenant_id="tenant-contract")
    view = _view_with_committed_file(monkeypatch, BODY)
    view.object_stores = ObjectStoreRegistry()
    with pytest.raises(DomainError) as denied:
        view.download(principal, "run_00000000000000000000000000", ARTIFACT["path"])
    assert (denied.value.code, denied.value.status, denied.value.retryable) == (
        "STORE-0001",
        503,
        True,
    )


def test_result_view_download_maps_missing_provider_object_to_retryable_503(
    monkeypatch,
):
    principal = SimpleNamespace(tenant_id="tenant-contract")
    view = _view_with_committed_file(monkeypatch, BODY)
    provider = view.object_stores.resolve("s3-compatible-v1")
    monkeypatch.setattr(
        provider,
        "get",
        lambda *_args: (_ for _ in ()).throw(FileNotFoundError()),
    )
    with pytest.raises(DomainError) as denied:
        view.download(principal, "run_00000000000000000000000000", ARTIFACT["path"])
    assert (denied.value.code, denied.value.status, denied.value.retryable) == (
        "STORE-0001",
        503,
        True,
    )


def test_result_view_download_revalidates_the_ticket_after_remote_io(monkeypatch):
    principal = SimpleNamespace(tenant_id="tenant-contract")
    view = _view_with_committed_file(monkeypatch, BODY)
    original = ResultView._current(object(), object())
    changed = {**original, "locator": "scoped/provider/changed"}
    rows = iter((original, changed))
    monkeypatch.setattr(ResultView, "_current", staticmethod(lambda _conn, _run: next(rows)))
    with pytest.raises(DomainError) as denied:
        view.download(principal, "run_00000000000000000000000000", ARTIFACT["path"])
    assert (denied.value.code, denied.value.status) == ("VERIFY-0023", 409)


def test_local_download_holds_provider_lock_through_short_db_revalidation(monkeypatch):
    events = []
    stored = b'{"stored":"local-provider-object"}'
    digest = hashlib.sha256(stored).hexdigest()
    row = {
        "evidence_id": ARTIFACT["evidenceId"],
        "evidence": {"outputSha256": digest},
        "commitment": {"outputSha256": digest},
        "object_state": "ready",
        "object_id": "22222222-2222-4222-8222-222222222222",
        "provider_id": "local-bounded-v1",
        "locator": "obj-22222222222242228222222222222222",
        "content_hash": digest,
        "size_bytes": len(stored),
        "delivery": {"payload": "unused-by-test-double"},
    }

    class Transaction:
        def __enter__(self):
            events.append("db-enter")
            return object()

        def __exit__(self, *_args):
            events.append("db-exit")

    class Database:
        @staticmethod
        def transaction(_tenant):
            return Transaction()

    class Files:
        @staticmethod
        def read(locator, expected_digest, expected_size):
            events.append("provider-read")
            assert (locator, expected_digest, expected_size) == (
                row["locator"],
                digest,
                len(stored),
            )
            return stored

    class Legacy:
        @contextmanager
        def locked(self):
            events.append("provider-enter")
            try:
                yield Files()
            finally:
                events.append("provider-exit")

    provider = object.__new__(LocalObjectStore)
    provider.legacy = Legacy()
    view = ResultView(Database(), ObjectStoreRegistry([provider]))
    monkeypatch.setattr(
        ResultView,
        "_scope",
        lambda self, conn, principal, project, run_id: {
            "run_id": run_id,
            "project_id": "prj_contract",
            "attempt": 1,
        },
    )
    monkeypatch.setattr(ResultView, "_current", staticmethod(lambda _conn, _run: row))
    monkeypatch.setattr(
        ResultView,
        "_files",
        staticmethod(
            lambda _ticket, _artifact: (
                {
                    "files": [
                        {
                            "path": ARTIFACT["path"],
                            "sha256": ARTIFACT["checksumSha256"],
                            "sizeBytes": ARTIFACT["byteSize"],
                        }
                    ]
                },
                {ARTIFACT["path"]: BODY},
            )
        ),
    )
    assert (
        view.download(
            SimpleNamespace(tenant_id="tenant-contract"),
            "run_00000000000000000000000000",
            ARTIFACT["path"],
        )["content"]
        == BODY
    )
    assert events == [
        "db-enter",
        "db-exit",
        "provider-enter",
        "provider-read",
        "db-enter",
        "db-exit",
        "provider-exit",
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["artifact"].pop("checksumSha256"),
        lambda value: value.update(contentType="application/json"),
        lambda value: value["artifact"].update(byteSize=-1),
        lambda value: value.update(inventedHeader="accepted"),
    ],
)
def test_artifact_content_contract_rejects_transport_drift(mutate):
    payload = _fixture()
    mutate(payload)
    with pytest.raises(DomainError, match="ArtifactContentResponse: invalid contract"):
        validate_contract("ArtifactContentResponse", payload)


@pytest.mark.parametrize(
    "route_path",
    [
        "/v1/runs/run_00000000000000000000000000/artifacts/content",
        "/v1/projects/project_00000000000000000000000000/runs/run_00000000000000000000000000/artifacts/content",
    ],
    ids=["run-alias", "project-run-alias"],
)
@pytest.mark.parametrize(
    "request_headers",
    [
        {"Authorization": "Bearer contract-test"},
        {
            "Authorization": "Bearer contract-test",
            "Range": "bytes=0-3",
            "If-None-Match": "*",
        },
    ],
    ids=["ordinary-full-response", "range-and-conditional-ignored"],
)
def test_artifact_content_route_returns_raw_bytes_bound_to_contract_headers(
    client, route_path, request_headers
):
    response = client.get(
        route_path,
        params={"path": "outputs/metrics.json"},
        headers=request_headers,
    )

    assert response.status_code == 200
    assert response.content == BODY
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["content-disposition"] == 'attachment; filename="artifact.bin"'
    assert response.headers["x-content-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert int(response.headers["content-length"]) == len(response.content)
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "content-range" not in response.headers
    assert "etag" not in response.headers
    observed = {
        "statusCode": response.status_code,
        "contentType": response.headers["content-type"],
        "contentDisposition": response.headers["content-disposition"],
        "artifact": ARTIFACT,
        "contentTypeOptions": response.headers["x-content-type-options"],
    }
    validate_contract("ArtifactContentResponse", observed)
    assert observed == _fixture()


def test_artifact_content_routes_are_only_aliases_of_one_response_handler(client):
    expected = {
        "/v1/runs/{run_id}/artifacts/content",
        "/v1/projects/{project}/runs/{run_id}/artifacts/content",
    }
    routes = [
        route for route in client.app.routes if "/artifacts/content" in getattr(route, "path", "")
    ]

    assert len(routes) == 2
    assert {route.path for route in routes} == expected
    assert len({route.endpoint for route in routes}) == 1


def test_artifact_content_route_refuses_contract_invalid_response_metadata(client, monkeypatch):
    real_validate = kernel_app.validate_contract

    def reject_artifact_metadata(name, value):
        if name == "ArtifactContentResponse":
            return real_validate(name, {**value, "unexpected": True})
        return real_validate(name, value)

    monkeypatch.setattr(kernel_app, "validate_contract", reject_artifact_metadata)
    response = client.get(
        "/v1/runs/run_00000000000000000000000000/artifacts/content",
        params={"path": "outputs/metrics.json"},
        headers={"Authorization": "Bearer contract-test"},
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "VAL-0002"
    assert BODY.decode() not in response.text
