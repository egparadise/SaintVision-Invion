"""The adapter status routes, at the surface that actually serves them.

``GET /v1/adapters`` and ``GET /v1/adapters/{name}`` have been served through
``BusinessDispatch`` since S03, and a grep for ``v1/adapters`` across ``tests/``
returned nothing: ``tests/test_cli_adapters.py`` calls ``adapters/agents.py``
directly, so the route layer -- the credential check, the response shape, the
404, the ``readyCount`` arithmetic -- had never been exercised. That is gap G-01
of the consolidated evidence triage.

``agents.readiness()`` is stubbed throughout. What is under test is the route;
whether the real CLI binaries are present is a different gap (G-11) and is
answered by hosted CI provisioning, not here.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from saintvision.api.app import create_app
from saintvision.api.v1 import adapters as adapters_route
from saintvision.config import Settings
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
AUTH = {"Authorization": "Bearer adapters-token"}

#: The four rows the real sweep returns, reduced to the fields the route reads.
#: ``headless`` is false for antigravity because it has no documented headless
#: invocation, which is the case that makes ``readyCount`` more than a count of
#: installed tools.
ROWS = [
    {
        "adapter": "claude-code",
        "executable": "claude",
        "installed": True,
        "headless": True,
        "loginState": "logged_in",
    },
    {
        "adapter": "codex-cli",
        "executable": "codex",
        "installed": True,
        "headless": True,
        "loginState": "logged_out",
    },
    {
        "adapter": "gemini-cli",
        "executable": "gemini",
        "installed": False,
        "headless": True,
        "loginState": "unknown",
    },
    {
        "adapter": "antigravity",
        "executable": "antigravity",
        "installed": True,
        "headless": False,
        "loginState": "logged_in",
    },
]


class Probe:
    def __init__(self, *, reachable=True, latency_ms=12):
        self.reachable = reachable
        self.latency_ms = latency_ms


class Adapter:
    """Stands in for ``CliAdapter``: the two calls the route makes."""

    def __init__(self, row, probe=None):
        self._row = row
        self._probe = probe or Probe()

    def readiness(self):
        return dict(self._row)

    def probe(self):
        return self._probe


def build(monkeypatch, *, rows=None, adapter=None, unknown=()):
    monkeypatch.setattr(
        adapters_route.agents, "readiness", lambda: [dict(row) for row in (rows or ROWS)]
    )

    def adapter_for(name):
        if name in unknown:
            raise KeyError(name)
        return adapter or Adapter(next(row for row in ROWS if row["adapter"] == name))

    monkeypatch.setattr(adapters_route.agents, "adapter_for", adapter_for)

    principal = Principal(
        user_id="usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        tenant_id=TENANT,
        external_subject="oidc:adapters",
    )
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier(
            {"adapters-token": principal}, allow_outside_dev=True
        ),
        check_partitions_on_startup=False,
    )
    return TestClient(app, raise_server_exceptions=False)


def test_the_list_answers_with_the_scope_of_what_it_measured(monkeypatch):
    """The two honesty fields are part of the contract, not decoration.

    ``measurementScope`` and ``remoteNodeReadiness`` are what stop a caller
    reading this as the state of the fleet: it is what the control-plane host can
    see about itself. Remote node readiness needs physical nodes and is a
    separate, externally blocked item.
    """
    client = build(monkeypatch)
    response = client.get("/v1/adapters", headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "adapters",
        "measurementScope",
        "remoteNodeReadiness",
        "readyCount",
        "note",
    }
    assert body["measurementScope"] == "control-plane-host"
    assert body["remoteNodeReadiness"] == "unknown"
    assert "never changed" in body["note"]
    # Ordered, so a status screen does not reshuffle between refreshes.
    assert [row["adapter"] for row in body["adapters"]] == [
        "claude-code",
        "codex-cli",
        "gemini-cli",
        "antigravity",
    ]


def test_ready_means_installed_and_headless_and_signed_in(monkeypatch):
    """Only the first row qualifies, and each of the other three misses once."""
    client = build(monkeypatch)
    body = client.get("/v1/adapters", headers=AUTH).json()
    assert body["readyCount"] == 1


@pytest.mark.parametrize(
    "row",
    [
        {"installed": False, "headless": True, "loginState": "logged_in"},
        {"installed": True, "headless": False, "loginState": "logged_in"},
        {"installed": True, "headless": True, "loginState": "logged_out"},
        {"installed": True, "headless": True, "loginState": "unknown"},
    ],
)
def test_each_near_miss_is_not_counted_as_ready(monkeypatch, row):
    client = build(monkeypatch, rows=[{"adapter": "claude-code", **row}])
    body = client.get("/v1/adapters", headers=AUTH).json()
    assert body["readyCount"] == 0, row


def test_a_fully_ready_single_tool_is_counted(monkeypatch):
    """The positive control, so the four near misses are not passing vacuously."""
    client = build(
        monkeypatch,
        rows=[
            {
                "adapter": "claude-code",
                "installed": True,
                "headless": True,
                "loginState": "logged_in",
            }
        ],
    )
    assert client.get("/v1/adapters", headers=AUTH).json()["readyCount"] == 1


def test_one_broken_tool_is_reported_as_its_own_state_not_a_failed_request(monkeypatch):
    """A screen showing three answers and a problem beats a screen showing nothing.

    ``agents.readiness()`` turns a per-tool failure into a row with an ``error``
    key; the route must pass that through rather than fail the request.
    """
    broken = {
        "adapter": "codex-cli",
        "executable": "codex",
        "installed": False,
        "loginState": "unknown",
        "error": "FileNotFoundError",
    }
    client = build(monkeypatch, rows=[ROWS[0], broken])
    response = client.get("/v1/adapters", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["adapters"][1]["error"] == "FileNotFoundError"
    # A row with no ``headless`` key must not be counted, and must not raise.
    assert body["readyCount"] == 1


def test_reading_one_adapter_adds_the_probe_to_its_readiness(monkeypatch):
    client = build(
        monkeypatch,
        adapter=Adapter(ROWS[0], probe=Probe(reachable=True, latency_ms=41)),
    )
    response = client.get("/v1/adapters/claude-code", headers=AUTH)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["adapter"] == "claude-code"
    assert body["reachable"] is True
    assert body["latencyMs"] == 41
    # The readiness fields are carried through, not replaced by the probe.
    assert body["installed"] is True
    assert body["loginState"] == "logged_in"


def test_an_unreachable_adapter_is_still_a_200_with_reachable_false(monkeypatch):
    """Not reachable is an answer about the tool, not an error about the request."""
    client = build(
        monkeypatch,
        adapter=Adapter(ROWS[2], probe=Probe(reachable=False, latency_ms=None)),
    )
    response = client.get("/v1/adapters/gemini-cli", headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["reachable"] is False
    assert body["latencyMs"] is None


def test_an_unknown_adapter_name_is_a_404(monkeypatch):
    """Pinned as it behaves today, deliberately.

    This route answers with FastAPI's ``HTTPException`` body -- ``{"detail": ...}``
    -- and not the canonical ``ProblemDetails``. That is the pre-existing shape of
    this surface, and changing it is a public contract change; #167 drew the same
    line by applying the canonical envelope to its new route and leaving the
    existing ones alone. So this test records what is served rather than what
    ought to be, and the canonicalisation is a separate card.
    """
    client = build(monkeypatch, unknown={"nope"})
    response = client.get("/v1/adapters/nope", headers=AUTH)
    assert response.status_code == 404
    body = response.json()
    assert body == {"detail": "unknown adapter: nope"}
    # Named so a future canonicalisation has to update this test on purpose.
    assert "code" not in body and "type" not in body


@pytest.mark.parametrize("path", ["/v1/adapters", "/v1/adapters/claude-code"])
def test_both_routes_require_a_credential(monkeypatch, path):
    # The legacy handler records the denial out of band, which needs a real
    # engine; this file has none, so the write is stubbed. What is under test is
    # that the route refuses, not that the denial is written.
    from saintvision.api import app as app_module

    monkeypatch.setattr(app_module, "record_denial_out_of_band", lambda *a, **k: None)
    client = build(monkeypatch)
    response = client.get(path)
    assert response.status_code == 401, response.text
    assert response.json()["code"] == "AUTH-MISSING-CREDENTIAL"
    assert response.headers["www-authenticate"] == "Bearer"


def test_both_routes_are_visible_to_the_business_dispatch_selection():
    """A route the deployed topology never reaches is not a served route.

    ``BusinessDispatch`` picks business traffic out of the projects, settings and
    adapters routers, so these two are reachable by construction -- pinned here
    because that is the property the rest of this file depends on.
    """
    from saintvision.api.v1 import projects, settings as settings_router

    routes = {
        route.path: route.methods
        for module in (projects, settings_router, adapters_route)
        for route in module.router.routes
        if "adapters" in getattr(route, "path", "")
    }
    assert routes == {"/v1/adapters": {"GET"}, "/v1/adapters/{name}": {"GET"}}


def test_the_list_response_has_no_declared_type_yet():
    """Recorded, not fixed: this response is pinned only by the test above.

    Business request and response contracts live in ``api/schemas.py`` and
    ``tools/export_schemas.py`` generates their JSON Schema. These two routes are
    annotated ``-> dict``, so nothing generates a schema for them and
    ``export_schemas --check`` cannot notice a shape change. Adding a response
    type is a contract change, so it is a follow-up rather than part of this gap.
    """
    from saintvision.api import schemas

    assert not any(
        name.startswith("Adapter") or name.startswith("AdapterList")
        for name in dir(schemas)
    )
    source = open(adapters_route.__file__, encoding="utf-8").read()
    assert "response_model" not in source
