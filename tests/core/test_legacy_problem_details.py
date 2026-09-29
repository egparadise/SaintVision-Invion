"""Legacy resource absence at the API boundary (card 135).

The services keep their historical ``InvError`` codes for internal callers,
but an HTTP caller gets the strict public ``ProblemDetails`` contract.  A
missing row and a row hidden by tenant/project policy are deliberately the
same response, and resource absence is not an authentication denial audit.
"""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from saintvision.api import app as app_module
from saintvision.api.app import create_app
from saintvision.api.problem import CANONICAL_KEYS
from saintvision.config import Settings
from saintvision.errors import (
    RES_ARTIFACT_NOT_FOUND,
    RES_CONTRIBUTION_NOT_FOUND,
    RES_NODE_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    RES_WORKSPACE_NOT_FOUND,
    InvError,
)
from saintvision.identity.principal import StaticPrincipalVerifier


LEGACY_NOT_FOUND_CODES = (
    RES_NODE_NOT_FOUND,
    RES_CONTRIBUTION_NOT_FOUND,
    RES_RUN_NOT_FOUND,
    RES_WORKSPACE_NOT_FOUND,
    RES_ARTIFACT_NOT_FOUND,
)


def _client(monkeypatch, recorded: list[dict]) -> TestClient:
    def recorder(_engine, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(app_module, "record_denial_out_of_band", recorder)
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        clock=lambda: dt.datetime(2026, 9, 29, tzinfo=dt.timezone.utc),
        check_partitions_on_startup=False,
    )

    @app.get("/card-135/{legacy_code}")
    def missing(legacy_code: str):
        raise InvError(legacy_code, "resource-specific text must not cross the boundary")

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("legacy_code", LEGACY_NOT_FOUND_CODES)
def test_every_unambiguous_legacy_not_found_is_the_same_canonical_404(monkeypatch, legacy_code):
    recorded: list[dict] = []
    response = _client(monkeypatch, recorded).get(f"/card-135/{legacy_code}")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert tuple(body) == CANONICAL_KEYS
    assert body == {
        "type": "about:blank",
        "title": "RES-0004",
        "status": 404,
        "code": "RES-0004",
        "category": "RES",
        "detail": "No such resource.",
        "retryable": False,
        "traceId": body["traceId"],
        "causeRef": None,
        "evidenceId": None,
    }
    assert recorded == []


def test_a_non_not_found_legacy_resource_problem_is_not_globally_reclassified(monkeypatch):
    recorded: list[dict] = []
    response = _client(monkeypatch, recorded).get("/card-135/RES-HEARTBEAT-STALE")

    assert response.status_code == 409
    assert response.json()["code"] == "RES-HEARTBEAT-STALE"
    assert recorded == []
