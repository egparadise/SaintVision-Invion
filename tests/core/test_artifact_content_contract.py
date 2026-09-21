"""Bind the kernel's raw artifact bytes and their HTTP headers to one shared contract."""

from __future__ import annotations

import hashlib
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import inv.app as kernel_app
from inv.app import create_app
from inv.contracts import validate_contract
from inv.errors import DomainError
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
    class Database:
        @staticmethod
        def transaction(_tenant_id):
            return nullcontext(object())

    monkeypatch.setattr(
        ResultView,
        "_scope",
        lambda self, conn, principal, project, run_id: {"run_id": run_id, "attempt": 1},
    )
    monkeypatch.setattr(
        ResultView,
        "_current",
        staticmethod(lambda conn, run: {"evidence_id": ARTIFACT["evidenceId"]}),
    )
    monkeypatch.setattr(ResultView, "_output", staticmethod(lambda row: {"verified": True}))
    monkeypatch.setattr(
        ResultView,
        "_files",
        staticmethod(
            lambda row, artifact: (
                {"files": [{"path": ARTIFACT["path"], "sha256": ARTIFACT["checksumSha256"], "sizeBytes": ARTIFACT["byteSize"]}]},
                {ARTIFACT["path"]: content},
            )
        ),
    )
    return ResultView(Database())


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
        route
        for route in client.app.routes
        if "/artifacts/content" in getattr(route, "path", "")
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
