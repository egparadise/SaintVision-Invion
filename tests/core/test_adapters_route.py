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


def build(monkeypatch, *, rows=None, adapter=None, unknown=(), world=None):
    monkeypatch.setattr(
        adapters_route.agents, "readiness", lambda: [dict(row) for row in (rows or ROWS)]
    )

    # The shared denial recorder writes through the app's engine, which this file
    # does not have. Recorded so a refusal's audit call can be asserted -- and so
    # a *non*-refusal can be asserted to make none.
    recorded = world if world is not None else {}
    recorded.setdefault("denials", [])
    from saintvision.api import app as app_module

    monkeypatch.setattr(
        app_module,
        "record_denial_out_of_band",
        lambda _engine, **kwargs: recorded["denials"].append(kwargs),
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


def test_an_unknown_adapter_name_is_the_canonical_404(monkeypatch):
    """Updated on purpose, which is what the previous version of this test asked for.

    It used to pin FastAPI's ``HTTPException`` body -- ``{"detail": "unknown
    adapter: nope"}``, with no ``code`` and no ``type`` -- as a record of what this
    surface served, and said the canonicalisation was a separate card. This is that
    card, so the assertion moved with the behaviour rather than being deleted.
    """
    from saintvision.api.problem import CANONICAL_KEYS

    client = build(monkeypatch, unknown={"nope"})
    response = client.get("/v1/adapters/nope", headers=AUTH)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert set(body) == set(CANONICAL_KEYS), body
    assert body["type"] == "about:blank"
    assert body["code"] == "RES-0004"
    assert body["title"] == "RES-0004"
    assert body["status"] == 404
    assert body["category"] == "RES"
    assert body["retryable"] is False
    assert body["detail"] == "No such adapter."


def test_the_canonical_404_does_not_echo_the_name_the_caller_sent(monkeypatch):
    """The old detail repeated the path value.

    A screen renders this body, so caller-controlled text in it is the caller
    choosing what a reader sees. The name is in the request they already have.
    """
    client = build(monkeypatch, unknown={"<img src=x onerror=alert(1)>"})
    response = client.get("/v1/adapters/<img src=x onerror=alert(1)>", headers=AUTH)
    assert response.status_code == 404
    assert "img" not in response.text
    assert "onerror" not in response.text


def test_an_unknown_adapter_is_not_recorded_as_a_denial(monkeypatch):
    """A 404 is not a refusal of access.

    The shared boundary audits AUTH/SEC problems at 401 and 403 (#195). Recording
    a not-found as a denial would fill the AC-02 trail with requests nobody was
    refused.
    """
    world = {}
    client = build(monkeypatch, unknown={"nope"}, world=world)
    assert client.get("/v1/adapters/nope", headers=AUTH).status_code == 404
    assert world["denials"] == []


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


def test_the_router_declares_exactly_these_two_adapter_paths():
    """About the router itself: two GETs, no more and no fewer."""
    routes = {
        route.path: route.methods
        for route in adapters_route.router.routes
        if "adapters" in getattr(route, "path", "")
    }
    assert routes == {"/v1/adapters": {"GET"}, "/v1/adapters/{name}": {"GET"}}


def test_the_real_dispatch_sends_these_paths_to_the_business_app():
    """A route the deployed topology never reaches is not a served route.

    The first version of this test restated ``BusinessDispatch``'s selection --
    projects, settings, adapters -- inside the test, which means removing
    ``adapters`` from that tuple in ``inv.business_surface`` would have changed
    nothing here. So the real dispatch is constructed and asked, and the answer
    that matters is which of two apps received the request.
    """
    from fastapi import FastAPI
    from inv.business_surface import BusinessDispatch

    kernel, business = FastAPI(), FastAPI()

    @kernel.get("/{rest:path}")
    def kernel_catch_all(rest: str):
        return {"servedBy": "kernel"}

    @business.get("/{rest:path}")
    def business_catch_all(rest: str):
        return {"servedBy": "business"}

    with TestClient(BusinessDispatch(kernel, business)) as client:
        for path in ("/v1/adapters", "/v1/adapters/claude-code"):
            assert client.get(path).json() == {"servedBy": "business"}, path
        # A path the business app does not declare still goes to the kernel,
        # or the two assertions above would also pass with a dispatch that
        # forwarded everything.
        assert client.get("/v1/runs").json() == {"servedBy": "kernel"}


def test_the_single_adapter_response_now_has_a_declared_type():
    """The other half of #180's observation, closed for the route that can be.

    Both routes were ``-> dict``, so ``export_schemas`` generated nothing and a
    shape change broke no gate. The single-adapter response is one row with one
    shape, so it now has a ``Strict`` model and a generated contract.
    """
    import json
    import pathlib

    from saintvision.api import schemas
    from tools.export_schemas import exported

    model = schemas.AdapterReadinessResponse
    assert "adapter-readiness-response" in exported()
    generated = pathlib.Path("contracts/adapter-readiness-response.schema.json")
    schema = json.loads(generated.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    # The thirteen keys observed from agents.readiness() plus the two from probe().
    assert set(schema["properties"]) == {
        "adapter",
        "executable",
        "installed",
        "path",
        "installedElsewhere",
        "version",
        "loginState",
        "loginDetail",
        "headless",
        "missing",
        "instructions",
        "reachable",
        "latencyMs",
    }
    assert set(model.model_fields) and model.model_config["extra"] == "forbid"


def test_the_single_adapter_route_declares_that_model():
    from saintvision.api import schemas

    matches = [
        route
        for route in adapters_route.router.routes
        if getattr(route, "path", None) == "/v1/adapters/{name}"
    ]
    assert len(matches) == 1
    assert matches[0].response_model is schemas.AdapterReadinessResponse


def test_the_list_response_still_has_no_declared_type_and_why():
    """Recorded, not fixed -- and now with the reason, which is a measurement.

    ``agents.readiness()`` returns two row shapes: the eleven-key row, and a
    five-key row when one tool raises (``adapter``, ``executable``, ``installed``,
    ``loginState``, ``error``). A response model would fill the missing keys with
    defaults, changing the wire shape a screen sees for a broken tool -- a public
    change owned by the frontend, not a side effect of canonicalising a 404.
    """
    import inspect

    from saintvision.adapters import agents

    source = inspect.getsource(agents.readiness)
    assert '"error": type(error).__name__' in source
    assert '"headless"' not in source, "the error row does not carry it"

    matches = [
        route
        for route in adapters_route.router.routes
        if getattr(route, "path", None) == "/v1/adapters"
    ]
    assert len(matches) == 1
    # FastAPI takes the model from the ``-> dict`` annotation, so it is ``dict``:
    # an open type that pins nothing and generates no contract. That is the state
    # this test records, as distinct from the single-adapter route above.
    assert matches[0].response_model is dict
    from tools.export_schemas import exported

    assert "adapter-list-response" not in exported()
