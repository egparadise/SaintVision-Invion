import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import inv.app as app_module
from inv.app import Boundary, create_app, problem
from inv.contracts import validate_contract
from inv.errors import DomainError


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "fixtures"
    / "problem-details-response.json"
)


def test_shared_problem_details_fixture_matches_backend_contract():
    validate_contract("ProblemDetails", json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_problem_serializer_validates_and_bounds_the_error_detail():
    response = problem(DomainError("SYS-0001", "x" * 1200, 503), "a" * 32)
    body = json.loads(response.body)

    validate_contract("ProblemDetails", body)
    assert body["status"] == 503
    assert len(body["detail"]) == 1000
    assert body["causeRef"] is None and body["evidenceId"] is None


def test_problem_contract_anchor_covers_domain_error_and_capacity_rejection(monkeypatch):
    validated = []
    real_validate = app_module.validate_contract

    def recording_validate(name, value):
        validated.append(name)
        return real_validate(name, value)

    monkeypatch.setattr(app_module, "validate_contract", recording_validate)

    response = TestClient(create_app(), raise_server_exceptions=False).get("/v1/projects")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")

    class SaturatedSlots:
        def acquire(self, *, blocking):
            assert blocking is False
            return False

        def release(self):  # pragma: no cover - capacity rejection never acquires
            raise AssertionError("a rejected request must not release a slot")

    boundary = Boundary(FastAPI(), origins=())
    boundary.slots = SaturatedSlots()
    overloaded = TestClient(boundary, raise_server_exceptions=False).get("/")
    assert overloaded.status_code == 429
    assert overloaded.json()["code"] == "RES-0007"
    assert validated == ["ProblemDetails", "ProblemDetails"]
