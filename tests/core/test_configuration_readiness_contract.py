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
from inv.app import create_app
from inv.contracts import validate_contract
from inv.errors import DomainError
from inv.generated.models import ConfigurationReadinessView
from jwt_support import jwt_fixture
from saintvision.config import unresolved_s01_settings


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "fixtures"
    / "configuration-readiness-response.json"
)
SETTING_NAMES = {"INV_NODE_MTLS_CA_BUNDLE", "INV_OBJECT_STORE_ENDPOINT"}


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


def _client(auth, *, operator=True):
    database = _Database(operator=operator)
    client = TestClient(
        create_app(database, auth.auth, unresolved_settings=unresolved_s01_settings),
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
    for name in SETTING_NAMES:
        monkeypatch.delenv(name, raising=False)
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
    for name in SETTING_NAMES:
        monkeypatch.setenv(name, f"private-{name.lower()}")
    client, headers, _ = _client(auth)
    response = client.get("/v1/operations/configuration-readiness", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "unresolvedSettings": []}
    assert "private-" not in response.text


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
