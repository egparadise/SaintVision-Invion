"""Authenticated operational observation for unresolved S01 settings."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import inv.app as app_module
import inv.configuration_readiness as readiness_module
from inv.app import create_app
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.generated.models import ConfigurationReadinessView
from jwt_support import jwt_fixture
from inv.configuration_readiness import configured_s01_readiness
from pki_support import authority, issue

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "fixtures"
    / "configuration-readiness-response.json"
)
SETTING_NAMES = {
    "INV_NODE_MTLS_CA_BUNDLE",
    "INV_OBJECT_STORE_ENDPOINT",
}


class _Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, *, operator=True):
        self.operator = operator
        self.statements = []

    def execute(self, statement, params=()):
        self.statements.append((statement, params))
        row = None
        if self.operator:
            row = {
                "enabled": True,
                "person_id": uuid4(),
                "can_contain": True,
                "can_resume": False,
                "can_approve": False,
            }
        return _Cursor(row)


class _Database:
    def __init__(self, *, operator=True):
        self.conn = _Connection(operator=operator)
        self.tenant_ids = []

    @contextmanager
    def transaction(self, tenant_id):
        self.tenant_ids.append(tenant_id)
        yield self.conn


@pytest.fixture
def auth(tmp_path):
    return jwt_fixture(tmp_path, str(uuid4()))


def _client(auth, *, operator=True, unresolved_settings=None):
    database = _Database(operator=operator)
    client = TestClient(
        create_app(
            database,
            auth.auth,
            unresolved_settings=unresolved_settings or configured_s01_readiness({}),
        ),
        raise_server_exceptions=False,
    )
    headers = {"Authorization": "Bearer " + auth.token()}
    return client, headers, database


def test_shared_configuration_readiness_fixture_matches_generated_contract():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parsed = ConfigurationReadinessView.model_validate(payload)
    assert parsed.model_dump(by_alias=True, mode="json") == payload
    validate_contract("ConfigurationReadinessView", payload)


@pytest.mark.parametrize(
    "damage",
    [
        {"status": "ready", "unresolvedSettings": ["INV_SECRET_VALUE"]},
        {"status": "blocked", "unresolvedSettings": [], "value": "private"},
    ],
)
def test_configuration_readiness_contract_rejects_unknown_names_and_values(damage):
    with pytest.raises(ValidationError):
        ConfigurationReadinessView.model_validate(damage)


def test_runtime_contract_rejects_duplicate_setting_names():
    with pytest.raises(DomainError) as caught:
        validate_contract(
            "ConfigurationReadinessView",
            {
                "status": "blocked",
                "unresolvedSettings": [
                    "INV_NODE_MTLS_CA_BUNDLE",
                    "INV_NODE_MTLS_CA_BUNDLE",
                ],
            },
        )
    assert caught.value.code == "VAL-0002"


def test_operator_route_reports_names_only_and_anchors_response_contract(auth, monkeypatch):
    observed = []
    real_validate = app_module.validate_contract

    def recording_validate(name, value):
        observed.append(name)
        return real_validate(name, value)

    monkeypatch.setattr(app_module, "validate_contract", recording_validate)
    client, headers, database = _client(auth)
    response = client.get("/v1/operations/configuration-readiness", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "blocked",
        "unresolvedSettings": sorted(SETTING_NAMES),
    }
    assert "ConfigurationReadinessView" in observed
    assert database.tenant_ids == [auth.tenant]
    assert len(database.conn.statements) == 1
    assert all("value" not in key.lower() for key in response.json())


def test_operator_route_reports_ready_without_echoing_values(auth, monkeypatch):
    ca_bundle = authority().pem
    ca_file = "/run/saintvision/node-mtls-ca.pem"
    monkeypatch.setattr(readiness_module, "trusted_file", lambda path: ca_bundle)
    endpoint = "https://objects.example.invalid:9443/saintvision"
    provider = configured_s01_readiness(
        {"nodeMtlsCaBundle": ca_file, "objectStoreEndpoint": endpoint}
    )
    client, headers, _ = _client(auth, unresolved_settings=provider)
    response = client.get("/v1/operations/configuration-readiness", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "unresolvedSettings": []}
    assert ca_file not in response.text and endpoint not in response.text


def test_one_invalid_setting_keeps_the_route_blocked(auth, monkeypatch):
    monkeypatch.setattr(readiness_module, "trusted_file", lambda path: authority().pem)
    provider = configured_s01_readiness(
        {
            "nodeMtlsCaBundle": "/run/saintvision/node-mtls-ca.pem",
            "objectStoreEndpoint": "not-a-url",
        }
    )
    client, headers, _ = _client(auth, unresolved_settings=provider)
    response = client.get("/v1/operations/configuration-readiness", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "status": "blocked",
        "unresolvedSettings": ["INV_OBJECT_STORE_ENDPOINT"],
    }


@pytest.mark.parametrize("ca_case", ["missing", "malformed", "leaf"])
def test_missing_malformed_or_non_ca_pem_is_unresolved(monkeypatch, ca_case):
    if ca_case == "malformed":
        raw = b"-----BEGIN CERTIFICATE-----\ninvalid\n-----END CERTIFICATE-----\n"
    elif ca_case == "leaf":
        ca = authority()
        raw = issue(ca, "spiffe://saintvision.test/node", server=True).pem
    else:
        raw = None

    def read_ca(_path):
        if raw is None:
            raise FileNotFoundError()
        return raw

    monkeypatch.setattr(readiness_module, "trusted_file", read_ca)
    provider = configured_s01_readiness(
        {
            "nodeMtlsCaBundle": "/run/saintvision/node-mtls-ca.pem",
            "objectStoreEndpoint": "http://minio:9000",
        }
    )
    assert provider() == ["INV_NODE_MTLS_CA_BUNDLE"]


def test_ca_bundle_outside_the_read_only_configuration_volume_is_unresolved(monkeypatch):
    def unexpected_read(_path):
        raise AssertionError("an outside path must be rejected before file access")

    monkeypatch.setattr(readiness_module, "trusted_file", unexpected_read)
    provider = configured_s01_readiness(
        {
            "nodeMtlsCaBundle": "/etc/ssl/certs/ca-certificates.crt",
            "objectStoreEndpoint": "http://minio:9000",
        }
    )
    assert provider() == ["INV_NODE_MTLS_CA_BUNDLE"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://user@example.invalid/storage",
        "https://example.invalid/storage#fragment",
        "https://example.invalid:99999/storage",
    ],
)
def test_object_store_endpoint_rejects_credentials_fragments_and_bad_ports(endpoint):
    provider = configured_s01_readiness(
        {
            "nodeMtlsCaBundle": None,
            "objectStoreEndpoint": endpoint,
        }
    )
    assert "INV_OBJECT_STORE_ENDPOINT" in provider()


def test_operator_route_requires_bearer_and_current_operator_grant(auth):
    client, headers, _ = _client(auth, operator=False)
    missing = client.get("/v1/operations/configuration-readiness")
    forbidden = client.get("/v1/operations/configuration-readiness", headers=headers)

    assert (missing.status_code, missing.json()["code"]) == (401, "AUTH-0050")
    assert (forbidden.status_code, forbidden.json()["code"]) == (403, "AUTH-0062")
    validate_contract("ProblemDetails", missing.json())
    validate_contract("ProblemDetails", forbidden.json())


def test_unconfigured_factory_fails_closed_instead_of_guessing_settings(auth):
    database = _Database()
    client = TestClient(create_app(database, auth.auth), raise_server_exceptions=False)
    response = client.get(
        "/v1/operations/configuration-readiness",
        headers={"Authorization": "Bearer " + auth.token()},
    )
    assert (response.status_code, response.json()["code"]) == (503, "SYS-0001")
