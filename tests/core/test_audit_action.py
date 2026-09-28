"""The denial audit ``action`` is bounded by the column and carries no identifier.

PG-free: the mapping is a pure function of the matched route. The real-PG
side (``tests/test_api.py``) shows the consequence: a long route without a
credential is a 401 with its denial row, not a 500.
"""

from __future__ import annotations

import re

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from saintvision.api.app import create_app
from saintvision.api.audit_action import AUDIT_ACTION_LIMIT, UNMATCHED, audit_action
from saintvision.config import Settings
from saintvision.identity.principal import StaticPrincipalVerifier
from saintvision.ids import PREFIXES

ID_PATTERN = re.compile(r"\b(" + "|".join(sorted(set(PREFIXES.values()))) + r")_[0-9A-Z]{26}\b")


class _EngineStandIn:
    """create_app touches the engine only at startup, which these tests never run."""


def _routes():
    app = create_app(
        engine=_EngineStandIn(),
        settings=Settings(database_url="unused"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        check_partitions_on_startup=False,
    )
    return [route for route in app.routes if getattr(route, "methods", None)]


def _request(method: str, path: str, route=None) -> Request:
    scope = {"type": "http", "method": method, "path": path, "headers": [], "query_string": b""}
    if route is not None:
        scope["route"] = route
    return Request(scope)


def _worst_case(template: str) -> str:
    """The template with every placeholder filled by a real-width prefixed id."""

    def fill(match):
        key = match.group(1).removesuffix("_id")
        prefix = PREFIXES.get(key, "xxx")
        return f"{prefix}_{'0' * 26}"

    return re.sub(r"\{([^}:]+)(?::[^}]*)?\}", fill, template)


def test_every_registered_route_records_an_action_within_the_column():
    seen = []
    for route in _routes():
        for method in route.methods:
            action = audit_action(_request(method, _worst_case(route.path), route))
            seen.append((method, route.path, action))
            assert len(action) <= AUDIT_ACTION_LIMIT, (method, route.path, action)
            assert not ID_PATTERN.search(action), (method, route.path, action)
            assert "{" not in action or action == f"{method} {route.path}", action
    assert seen, "no routes registered"


def test_a_long_route_records_the_template_not_the_path():
    """The route that turned the 401 into a 500: 86-89 characters with real ids."""
    route = next(r for r in _routes() if r.path == "/v1/projects/{project_id}/members/{user_id}")
    path = _worst_case(route.path)
    assert len(f"PUT {path}") > AUDIT_ACTION_LIMIT
    action = audit_action(_request("PUT", path, route))
    assert action == "PUT /v1/projects/{project_id}/members/{user_id}"
    assert "prj_" not in action and "usr_" not in action


def test_the_raw_path_form_overflows_the_column_for_that_route():
    """Pins why the mapping exists: the previous ``METHOD path`` did not fit."""
    route = next(r for r in _routes() if r.path == "/v1/projects/{project_id}/members/{user_id}")
    assert len(f"DELETE {_worst_case(route.path)}") == 89 > AUDIT_ACTION_LIMIT


def test_a_short_route_keeps_its_exact_action():
    route = next(r for r in _routes() if r.path == "/v1/nodes" and "GET" in r.methods)
    assert audit_action(_request("GET", "/v1/nodes", route)) == "GET /v1/nodes"


def test_an_unmatched_path_records_the_fixed_fallback_and_nothing_from_the_url():
    path = "/v1/projects/prj_00000000000000000000000000/does-not-exist/" + "x" * 200
    action = audit_action(_request("GET", path))
    assert action == f"GET {UNMATCHED}"
    assert len(action) <= AUDIT_ACTION_LIMIT


def test_a_template_too_long_for_the_column_falls_back_to_the_route_name():
    router = APIRouter()
    template = "/v1/" + "/".join(f"segment-{i}/{{p{i}}}" for i in range(6))
    assert len(f"GET {template}") > AUDIT_ACTION_LIMIT

    @router.get(template, name="long_template_read")
    def long_template_read():  # pragma: no cover - never called
        return {}

    route = router.routes[0]
    action = audit_action(_request("GET", _worst_case(template), route))
    assert action == "GET long_template_read"
    assert len(action) <= AUDIT_ACTION_LIMIT


def test_an_absurdly_long_route_name_is_still_bounded():
    router = APIRouter()
    template = "/v1/" + "/".join(f"segment-{i}/{{p{i}}}" for i in range(6))

    @router.get(template, name="n" * 200)
    def named():  # pragma: no cover - never called
        return {}

    assert len(audit_action(_request("GET", template, router.routes[0]))) == AUDIT_ACTION_LIMIT


def test_the_handler_sees_the_matched_route_when_a_dependency_raises():
    """The denial handler runs after routing, so ``scope['route']`` is populated
    even though the endpoint never ran."""
    from fastapi import Depends, HTTPException

    app = FastAPI()
    captured = {}

    def deny():
        raise HTTPException(status_code=401)

    @app.get("/v1/things/{thing_id}/parts/{part_id}", dependencies=[Depends(deny)])
    def read():  # pragma: no cover - the dependency refuses first
        return {}

    @app.exception_handler(HTTPException)
    async def handler(request, exc):
        captured["action"] = audit_action(request)
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content={})

    with TestClient(app) as client:
        assert client.get("/v1/things/thg_0/parts/prt_0").status_code == 401
        assert client.get("/nowhere").status_code == 404
    assert captured["action"] == "GET /v1/things/{thing_id}/parts/{part_id}"


@pytest.mark.parametrize("method", ["get", "GET"])
def test_the_method_is_normalised(method):
    assert audit_action(_request(method, "/x")).startswith("GET ")
