"""The canonical 403 denial audit contract (Codex, #191): one shared recorder.

A refused request is audited at the application's exception-handler boundary
and nowhere else: the canonical handler and the legacy ``InvError`` handler
call the one ``_record_denial`` helper that ``create_app`` builds, once per
refused request, before the response is built. What it records comes only from
what the request already proved: the actor and tenant that ``get_principal``
pinned on ``request.state`` for a verified credential, the bounded
``audit_action`` (#189), and the path's project id only when it is one.

PG-free: the recorder is replaced by a list, so these prove *when* it is called
and *with what*. The rows themselves, RLS, and the "mutation 0, audit 1"
accounting are ``tests/integration/test_canonical_denial_audit_real_pg.py``.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from saintvision.api import app as app_module
from saintvision.api.app import create_app
from saintvision.api.audit_action import AUDIT_ACTION_LIMIT, audit_action, long_template_action
from saintvision.api.deps import get_principal
from saintvision.api.problem import (
    AUTH_PROJECT,
    GRAPH_PRECONDITION,
    RES_NOT_FOUND,
    VAL_REQUEST,
    CanonicalProblem,
    is_audited_denial,
)
from saintvision.api.v1 import lineage_query, model_release, run_records
from saintvision.config import Settings
from saintvision.errors import AUTH_PROJECT_SCOPE, InvError
from saintvision.identity.principal import Principal, StaticPrincipalVerifier

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT = "prj_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
MODEL = "mdl_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
USER = "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E"
NOW = dt.datetime(2026, 9, 28, 8, 0, tzinfo=dt.timezone.utc)
TOKEN = "denial-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _app(monkeypatch, recorded, *, recorder_error=None):
    """A real app with a stub route that refuses, and the recorder captured."""

    def recorder(_engine, **kwargs):
        if recorder_error is not None:
            raise recorder_error
        recorded.append(kwargs)

    monkeypatch.setattr(app_module, "record_denial_out_of_band", recorder)
    principal = Principal(user_id=USER, tenant_id=TENANT, external_subject="oidc:denial")
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )

    refusals: dict[str, Exception] = {}

    @app.get("/v1/projects/{project_id}/refuse/{which}", dependencies=[Depends(get_principal)])
    def refuse(project_id: str, which: str):
        raise refusals[which]

    @app.get("/v1/anonymous/{project_id}/refuse/{which}")
    def refuse_anonymously(project_id: str, which: str):
        raise refusals[which]

    app.state.refusals = refusals
    return TestClient(app, raise_server_exceptions=False)


def _refusals():
    return {
        "auth-403": CanonicalProblem(AUTH_PROJECT, 403, "This project is not accessible."),
        "auth-401": CanonicalProblem("AUTH-0001", 401, "A bearer credential is required."),
        "sec-403": CanonicalProblem("SEC-0001", 403, "Refused."),
        "auth-409": CanonicalProblem("AUTH-0030", 409, "Not a denial status."),
        "val-403": CanonicalProblem(VAL_REQUEST, 403, "Not an AUTH/SEC category."),
        "graph-403": CanonicalProblem(GRAPH_PRECONDITION, 403, "Not an AUTH/SEC category."),
        "res-404": CanonicalProblem(RES_NOT_FOUND, 404, "No such thing."),
        "inv-auth": InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal"),
    }


# ---------------------------------------------------------------- the shared handler


def test_a_canonical_auth_403_is_recorded_exactly_once_with_the_verified_actor_and_the_response_trace(monkeypatch):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/auth-403", headers=AUTH)
    assert response.status_code == 403, response.text
    body = response.json()
    assert body["code"] == "AUTH-0030"
    assert len(recorded) == 1
    call = recorded[0]
    assert call["actor_type"] == "user" and call["actor_id"] == USER and call["tenant_id"] == TENANT
    assert call["outcome"] == "deny" and call["reason_code"] == "AUTH-0030"
    assert call["trace_id"] == body["traceId"]
    assert call["action"] == "GET /v1/projects/{project_id}/refuse/{which}"
    assert call["target_type"] == "project" and call["target_id"] == PROJECT
    assert call["detail"] == {}
    assert call["now"] == NOW
    assert PROJECT not in call["action"] and USER not in call["action"]


@pytest.mark.parametrize("which", ["auth-401", "sec-403"])
def test_every_auth_or_sec_denial_status_is_recorded(monkeypatch, which):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/{which}", headers=AUTH)
    assert response.status_code in (401, 403)
    assert len(recorded) == 1 and recorded[0]["reason_code"] == response.json()["code"]


@pytest.mark.parametrize("which", ["auth-409", "val-403", "graph-403", "res-404"])
def test_a_problem_that_is_not_an_auth_or_sec_denial_is_not_recorded(monkeypatch, which):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/{which}", headers=AUTH)
    assert response.status_code in (403, 404, 409)
    assert recorded == []


def test_the_legacy_inv_error_handler_records_through_the_same_helper_and_shape(monkeypatch):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/inv-auth", headers=AUTH)
    assert response.status_code == 403, response.text
    assert len(recorded) == 1
    call = recorded[0]
    assert call["reason_code"] == "AUTH-PROJECT-SCOPE" and call["trace_id"] == response.json()["traceId"]
    assert call["target_type"] == "project" and call["target_id"] == PROJECT
    assert call["actor_id"] == USER and call["tenant_id"] == TENANT and call["detail"] == {}
    assert call["action"] == "GET /v1/projects/{project_id}/refuse/{which}"


def test_a_project_id_that_is_not_a_project_id_is_not_recorded_as_a_target(monkeypatch):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    for bad in ("not-a-project", "usr_01J8Z3XQ2K9WMV5T7N4B6C8D0E", "prj_" + "x" * 300):
        recorded.clear()
        response = client.get(f"/v1/projects/{bad}/refuse/auth-403", headers=AUTH)
        assert response.status_code == 403
        assert recorded[0]["target_type"] is None and recorded[0]["target_id"] is None
        assert bad not in recorded[0]["action"] and recorded[0]["detail"] == {}


def test_an_unauthenticated_denial_is_anonymous_with_no_tenant(monkeypatch):
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/auth-403")             # no credential
    assert response.status_code == 401                                          # get_principal refuses first
    assert len(recorded) == 1
    assert recorded[0]["actor_type"] == "anonymous" and recorded[0]["actor_id"] is None
    assert recorded[0]["tenant_id"] is None and recorded[0]["reason_code"] == "AUTH-MISSING-CREDENTIAL"


def test_the_actor_comes_from_request_state_not_from_the_header(monkeypatch):
    """A route that refuses without ``get_principal`` running has no verified
    actor, whatever the header says."""
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/anonymous/{PROJECT}/refuse/auth-403", headers=AUTH)
    assert response.status_code == 403
    assert recorded[0]["actor_type"] == "anonymous" and recorded[0]["tenant_id"] is None


def test_a_recorder_failure_is_a_generic_500_not_a_403_and_not_a_disclosure(monkeypatch):
    """Fail-closed: an audit failure is not disguised as a successful refusal."""
    recorded: list = []
    client = _app(monkeypatch, recorded, recorder_error=RuntimeError("audit_events: permission denied for relation"))
    client.app.state.refusals.update(_refusals())
    response = client.get(f"/v1/projects/{PROJECT}/refuse/auth-403", headers=AUTH)
    assert response.status_code == 500, response.text
    assert "AUTH-0030" not in response.text and "permission denied" not in response.text
    assert "audit_events" not in response.text
    assert recorded == []


def test_is_audited_denial_is_the_category_and_status_rule():
    assert is_audited_denial(CanonicalProblem(AUTH_PROJECT, 403, "x"))
    assert is_audited_denial(CanonicalProblem("SEC-0001", 401, "x"))
    assert not is_audited_denial(CanonicalProblem(AUTH_PROJECT, 409, "x"))
    assert not is_audited_denial(CanonicalProblem(GRAPH_PRECONDITION, 403, "x"))


def test_no_route_records_a_denial_itself():
    """The boundary is the only recorder: no route module touches the audit
    writer for a refusal (a route is inside the transaction the refusal rolls
    back, and per-route recording drifts)."""
    import pathlib

    root = pathlib.Path(run_records.__file__).parent
    for path in root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "record_denial_out_of_band" not in source, path.name


# ---------------------------------------------------------------- action regression on the real routes


def _denied_app(monkeypatch, recorded):
    def recorder(_engine, **kwargs):
        recorded.append(kwargs)

    monkeypatch.setattr(app_module, "record_denial_out_of_band", recorder)

    def deny(_session, *, tenant_id, project_id, user_id):
        raise InvError(AUTH_PROJECT_SCOPE, "project is not accessible to this principal")

    # Every business route checks access through this one function first.
    # #175 lineage and #184 run_records share ``lineage_query._membership``.
    monkeypatch.setattr(lineage_query.project_service, "require_project_access", deny)
    monkeypatch.setattr(model_release.project_service, "require_project_access", deny)
    import contextlib

    for module in (model_release,):
        monkeypatch.setattr(module, "make_session_factory", lambda _engine: _NullFactory())
        monkeypatch.setattr(module, "tenant_scope", lambda _session, _tenant: contextlib.nullcontext())
        # Card 84 F1 put the permission span under the lock-wait bound too; the
        # bound issues SET LOCAL on the session, which this PG-free stand-in
        # does not execute. Stubbed like tenant_scope: the subject here is the
        # denial audit action, and the bound has its own tests (test_lock_wait).
        monkeypatch.setattr(module, "bounded_lock_wait", lambda _session, *, timeout_ms: contextlib.nullcontext())
    from saintvision.api.deps import get_session

    principal = Principal(user_id=USER, tenant_id=TENANT, external_subject="oidc:denial")
    app = create_app(
        engine=object(),
        settings=Settings(database_url="postgresql://unused"),
        verifier=StaticPrincipalVerifier({TOKEN: principal}, allow_outside_dev=True),
        clock=lambda: NOW,
        check_partitions_on_startup=False,
    )
    app.dependency_overrides[get_session] = lambda: object()
    return TestClient(app, raise_server_exceptions=False)


class _NullFactory:
    def __call__(self):
        import contextlib

        class _S:
            @contextlib.contextmanager
            def begin(self):
                yield

        @contextlib.contextmanager
        def cm():
            yield _S()

        return cm()


VERSION_ID_TEXT = "1.4.0"
RUN = "run_01J8Z3XQ2K9WMV5T7N4B6C8D0E"

REPRESENTATIVE = [
    # #184 R1 record: the template fits the column, so it is recorded verbatim
    ("GET", f"/v1/projects/{PROJECT}/runs/{RUN}/record",
     "GET /v1/projects/{project_id}/runs/{run_id}/record"),
    # #167 release: the template is 80+ characters, so the digest form
    ("POST", f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION_ID_TEXT}/release",
     long_template_action("POST", "/v1/projects/{project_id}/models/{model_id}/versions/{version}/release",
                          "release_model_version")),
]


@pytest.mark.parametrize("method,path,expected", REPRESENTATIVE)
def test_a_denied_request_on_a_representative_route_records_the_bounded_template_action(monkeypatch, method, path, expected):
    recorded: list = []
    client = _denied_app(monkeypatch, recorded)
    headers = {**AUTH, "Content-Type": "application/json"}
    content = b'{"licensePolicy":"x","classification":"internal"}' if method == "POST" else None
    response = client.request(method, path, headers=headers, content=content)
    assert response.status_code == 403, response.text
    assert len(recorded) == 1
    action = recorded[0]["action"]
    assert action == expected
    assert len(action) <= AUDIT_ACTION_LIMIT
    for raw in (PROJECT, MODEL, VERSION_ID_TEXT, RUN):
        assert raw not in action
    assert recorded[0]["target_id"] == PROJECT and recorded[0]["actor_id"] == USER


def test_the_release_action_is_the_digest_form_and_carries_no_id(monkeypatch):
    recorded: list = []
    client = _denied_app(monkeypatch, recorded)
    path = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION_ID_TEXT}/release"
    response = client.post(path, headers={**AUTH, "Content-Type": "application/json"}, content=b'{"licensePolicy":"x","classification":"internal"}')
    assert response.status_code == 403, response.text
    action = recorded[0]["action"]
    assert "#" in action and action.startswith("POST ") and len(action) <= AUDIT_ACTION_LIMIT
    assert MODEL not in action and PROJECT not in action and "{" not in action


def test_the_lineage_trace_action_is_the_digest_form_and_carries_no_id(monkeypatch):
    recorded: list = []
    client = _denied_app(monkeypatch, recorded)
    path = f"/v1/projects/{PROJECT}/models/{MODEL}/versions/{VERSION_ID_TEXT}/lineage"
    response = client.get(path, headers=AUTH)
    assert response.status_code == 403, response.text
    action = recorded[0]["action"]
    assert "#" in action and action.startswith("GET ") and len(action) <= AUDIT_ACTION_LIMIT
    assert MODEL not in action and PROJECT not in action


def test_the_audit_action_helper_is_what_the_recorder_uses(monkeypatch):
    """Revert (re-assembling ``METHOD path`` in the recorder): the recorded
    action would carry the ids and exceed the column."""
    recorded: list = []
    client = _app(monkeypatch, recorded)
    client.app.state.refusals.update(_refusals())
    seen = {}
    real = audit_action

    def spy(request):
        seen["action"] = real(request)
        return seen["action"]

    monkeypatch.setattr(app_module, "audit_action", spy)
    client.get(f"/v1/projects/{PROJECT}/refuse/auth-403", headers=AUTH)
    assert recorded[0]["action"] == seen["action"]
