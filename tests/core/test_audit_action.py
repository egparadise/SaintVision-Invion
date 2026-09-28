"""The denial audit ``action`` is bounded by the column and carries no identifier.

PG-free: the mapping is a pure function of the matched route. The real-PG
side (``tests/test_api.py``) shows the consequence: a long route without a
credential is a 401 with its denial row, not a 500.

Every test that needs the application's routes goes through
``registered_routes``, which expands lazily included routers: on the pinned
FastAPI (0.141.x) ``include_router()`` leaves an ``_IncludedRouter`` in
``app.routes`` instead of the routes themselves, so a flat scan saw only the
app-level health/readiness routes and the ratchet checked nothing (Codex #189
F1, hosted run 36387023391: 3 ``StopIteration``).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from saintvision.api.app import create_app
from saintvision.api.audit_action import (
    AUDIT_ACTION_LIMIT,
    TEMPLATE_DIGEST_LENGTH,
    UNKNOWN_METHOD,
    UNMATCHED,
    audit_action,
    long_template_action,
)
from saintvision.config import Settings
from saintvision.identity.principal import StaticPrincipalVerifier
from saintvision.ids import PREFIXES

ID_PATTERN = re.compile(r"\b(" + "|".join(sorted(set(PREFIXES.values()))) + r")_[0-9A-Z]{26}\b")
MEMBERS = "/v1/projects/{project_id}/members/{user_id}"


class _EngineStandIn:
    """create_app touches the engine only at startup, which these tests never run."""


def _app() -> FastAPI:
    return create_app(
        engine=_EngineStandIn(),
        settings=Settings(database_url="unused"),
        verifier=StaticPrincipalVerifier({}, allow_outside_dev=True),
        check_partitions_on_startup=False,
    )


def registered_routes(app: FastAPI) -> list[tuple[str, str, object]]:
    """Every ``(method, effective path, original route)`` the app serves.

    Walks ``app.routes`` and, for a lazily included router (``original_router``
    + ``include_context.prefix`` on the pinned FastAPI), its router's routes
    recursively with the include prefix applied. On older FastAPI the routes
    are already flat and the walk is a plain scan. The *original* route is
    returned because that is what the router puts in ``scope["route"]``.
    """

    def walk(routes, prefix: str) -> Iterator[tuple[str, str, object]]:
        for route in routes:
            inner = getattr(route, "original_router", None)
            if inner is not None:
                context = getattr(route, "include_context", None)
                yield from walk(inner.routes, prefix + (getattr(context, "prefix", "") or ""))
                continue
            for method in getattr(route, "methods", None) or ():
                yield method, prefix + route.path, route

    return list(walk(app.routes, ""))


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


def _route(app: FastAPI, method: str, path: str):
    matches = [route for m, p, route in registered_routes(app) if m == method and p == path]
    assert len(matches) == 1, (method, path, len(matches))
    return matches[0]


# ---------------------------------------------------------------- the whole application


def test_the_route_walk_sees_the_product_routes_not_only_the_app_level_ones():
    """Revert (flat scan of ``app.routes``): only health/readiness would be seen."""
    paths = {p for _m, p, _r in registered_routes(_app())}
    assert "/v1/nodes" in paths and MEMBERS in paths
    assert len(paths) > 20, sorted(paths)


def test_the_recorded_template_is_the_effective_path_for_every_route():
    """The handler records ``scope['route'].path``; this pins that no router is
    included with a prefix that the original route's path would not carry."""
    for method, effective, route in registered_routes(_app()):
        assert route.path == effective, (method, effective, route.path)


def test_every_registered_route_records_an_action_within_the_column_without_ids():
    seen = []
    for method, path, route in registered_routes(_app()):
        action = audit_action(_request(method, _worst_case(path), route))
        seen.append((method, path, action))
        assert len(action) <= AUDIT_ACTION_LIMIT, (method, path, action)
        assert not ID_PATTERN.search(action), (method, path, action)
        assert "{" not in action or action == f"{method} {path}", action
    assert len(seen) > 20


def test_every_registered_route_maps_to_a_distinct_action():
    """Codex #189 F2: two long routes must not collapse into one audit action."""
    by_action: dict[str, list[tuple[str, str]]] = {}
    for method, path, route in registered_routes(_app()):
        by_action.setdefault(audit_action(_request(method, _worst_case(path), route)), []).append((method, path))
    collisions = {action: keys for action, keys in by_action.items() if len(keys) > 1}
    assert collisions == {}, collisions


def test_a_long_route_records_the_template_not_the_path():
    """The kind of route that turned the 401 into a 500: 86-89 characters with real ids."""
    route = _route(_app(), "PUT", MEMBERS)
    path = _worst_case(route.path)
    assert len(f"PUT {path}") > AUDIT_ACTION_LIMIT
    action = audit_action(_request("PUT", path, route))
    assert action == f"PUT {MEMBERS}"
    assert "prj_" not in action and "usr_" not in action


def test_the_raw_path_form_overflows_the_column_for_that_route():
    """Pins why the mapping exists: the previous ``METHOD path`` did not fit."""
    route = _route(_app(), "DELETE", MEMBERS)
    assert len(f"DELETE {_worst_case(route.path)}") == 89 > AUDIT_ACTION_LIMIT


def test_a_short_route_keeps_its_exact_action():
    route = _route(_app(), "GET", "/v1/nodes")
    assert audit_action(_request("GET", "/v1/nodes", route)) == "GET /v1/nodes"


# ---------------------------------------------------------------- fallbacks


def test_an_unmatched_path_records_the_fixed_fallback_and_nothing_from_the_url():
    path = "/v1/projects/prj_00000000000000000000000000/does-not-exist/" + "x" * 200
    action = audit_action(_request("GET", path))
    assert action == f"GET {UNMATCHED}"
    assert len(action) <= AUDIT_ACTION_LIMIT


def _long_router(name: str, template: str) -> APIRouter:
    router = APIRouter()

    @router.get(template, name=name)
    def endpoint():  # pragma: no cover - never called
        return {}

    return router


LONG_A = "/v1/" + "/".join(f"segment-{i}/{{p{i}}}" for i in range(6)) + "/a"
LONG_B = "/v1/" + "/".join(f"segment-{i}/{{p{i}}}" for i in range(6)) + "/b"


def test_a_template_too_long_for_the_column_records_a_name_prefix_and_a_template_digest():
    assert len(f"GET {LONG_A}") > AUDIT_ACTION_LIMIT
    route = _long_router("long_template_read", LONG_A).routes[0]
    action = audit_action(_request("GET", _worst_case(LONG_A), route))
    assert action == long_template_action("GET", LONG_A, "long_template_read")
    assert action.startswith("GET long_template_read#") and len(action) <= AUDIT_ACTION_LIMIT
    assert re.fullmatch(r"GET long_template_read#[0-9a-f]{%d}" % TEMPLATE_DIGEST_LENGTH, action)
    assert "{" not in action and "0000" not in action


def test_two_long_templates_with_the_same_name_prefix_record_different_actions():
    """Codex #189 F2: the digest, not the cut name, carries the identity."""
    name = "n" * 200
    a = audit_action(_request("GET", _worst_case(LONG_A), _long_router(name, LONG_A).routes[0]))
    b = audit_action(_request("GET", _worst_case(LONG_B), _long_router(name, LONG_B).routes[0]))
    assert a != b
    assert len(a) == len(b) == AUDIT_ACTION_LIMIT
    assert a.split("#")[0] == b.split("#")[0]                       # same cut name, different digest


def test_the_long_form_is_independent_of_the_request_path():
    route = _long_router("read", LONG_A).routes[0]
    one = audit_action(_request("GET", _worst_case(LONG_A), route))
    other = audit_action(_request("GET", LONG_A.replace("{p0}", "zzz_" + "9" * 26), route))
    assert one == other


def test_a_route_without_a_name_still_gets_a_bounded_distinct_action():
    action = long_template_action("GET", LONG_A, None)
    assert action.startswith("GET route#") and len(action) <= AUDIT_ACTION_LIMIT


# ---------------------------------------------------------------- the method is scope input too


@pytest.mark.parametrize("method", ["get", "GET", "Delete"])
def test_an_http_token_method_is_normalised_to_upper_case(method):
    assert audit_action(_request(method, "/x")) == f"{method.upper()} {UNMATCHED}"


@pytest.mark.parametrize("method", ["", "G E T", "x" * 17, "GET\n", "gét", "<script>"])
def test_a_method_that_is_not_an_http_token_is_recorded_as_unknown(method):
    action = audit_action(_request(method, "/x"))
    assert action == f"{UNKNOWN_METHOD} {UNMATCHED}"


def test_a_long_template_with_the_longest_admitted_method_still_fits():
    assert len(long_template_action("M" * 16, LONG_A, "n" * 100)) == AUDIT_ACTION_LIMIT


# ---------------------------------------------------------------- the handler sees the matched route


def test_the_handler_sees_the_matched_route_when_a_dependency_raises():
    """The denial handler runs after routing, so ``scope['route']`` is populated
    even though the endpoint never ran -- including through ``include_router``."""
    app = FastAPI()
    router = APIRouter(prefix="/v1")
    captured = {}

    def deny():
        raise HTTPException(status_code=401)

    @router.get("/things/{thing_id}/parts/{part_id}", dependencies=[Depends(deny)])
    def read():  # pragma: no cover - the dependency refuses first
        return {}

    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def handler(request, exc):
        captured["action"] = audit_action(request)
        return JSONResponse(status_code=exc.status_code, content={})

    with TestClient(app) as client:
        assert client.get("/v1/things/thg_0/parts/prt_0").status_code == 401
        assert client.get("/nowhere").status_code == 404
    assert captured["action"] == "GET /v1/things/{thing_id}/parts/{part_id}"
