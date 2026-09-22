"""Decision #6 (6a) integration verification -- Claude lane, independent of Codex's suite.

Codex landed ``POST /v1/projects/{project}/runs/{parent}/model-retries`` (563c54ce)
with ``tests/integration/test_model_retry.py``. This file re-verifies the
coordinator's acceptance list over REAL PostgreSQL and REAL HTTP (FastAPI
TestClient on ``inv.app.create_app``), asserting the *observable* contract:

1. only a ``failed`` terminal parent may retry (other states -> 4xx ProblemDetails);
2. Idempotency-Key replay returns the same child; same key + different body -> 409;
   missing key -> 422; a second retry of the same parent under another key -> 409;
3. a subject without ``can_request`` -> 403; another tenant -> 403 (F1 fixed in 4473c7f1), never a child;
4. the response has exactly the fixture's shape and validates against the contract;
5. ``requiresFrozenInputAndApproval`` is true and nothing is auto-approved
   (child stays ``planned``, no tool claim / permit rows);
6. the child is a fresh lineage member with NEW leases (no fencing token reuse);
7. placement reservation (6c) is really wired: the leases in the response exist
   in ``inv.resource_leases`` for the child run.

Fixtures are the shared real-PG chain (``runtime`` from test_model_runtime).
Every assertion that reads the database goes through a separate psycopg
connection so it sees only committed state.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.model_retry import ModelRetryStore
from test_model_retry import fail_unstarted
# The real-PG fixture chain: each module's fixture must be importable here for pytest to resolve it.
from test_model_runtime import runtime  # noqa: F401
from test_model_locality import locality  # noqa: F401
from test_model_commit import model  # noqa: F401
from test_storage_commit import sample, storage_subject  # noqa: F401
from test_approvals import approval  # noqa: F401

pytestmark = pytest.mark.postgres

FIXTURE = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "model-retry-prepare-result.json"


def _body(a):
    r = a.request
    return {
        "cpuMillis": r.cpu_millis,
        "memoryBytes": r.memory_bytes,
        "gpuCount": r.gpu_count,
        "minVramBytes": r.min_vram_bytes,
        "requiredBytes": r.required_bytes,
        "maxHostLoad": float(r.max_host_load),
        "runtime": r.runtime,
        "policyVersion": "model-retry:1",
    }


def _client(a, principals):
    """HTTP client whose bearer token selects one of ``principals`` by name."""

    class Tokens:
        tenant_id = a.e.tenant

        @staticmethod
        def verify(value):
            if value not in principals:
                from inv.errors import DomainError

                raise DomainError("AUTH-0050", "A current access token is required", 401)
            return SimpleNamespace(principal=principals[value], expires_at="2026-09-22T09:00:00Z")

        @staticmethod
        def _keys():
            return None

    return TestClient(
        create_app(a.e.db, Tokens(), model_retry=ModelRetryStore(a.e.db, a.verifier)),
        raise_server_exceptions=False,
    )


def _url(a, parent=None):
    return f"/v1/projects/{a.e.project}/runs/{parent or a.target}/model-retries"


def _post(client, a, *, token="requester", key="claude-retry", body=None, parent=None):
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(_url(a, parent), json=body or _body(a), headers=headers)


def _lineage_count(a):
    with psycopg.connect(a.e.owner) as c:
        return c.execute(
            "SELECT count(*) FROM inv.model_retry_lineage WHERE tenant_id=%s", (a.e.tenant,)
        ).fetchone()[0]


def _set_state(a, state, run=None):
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE inv.runs SET state=%s,version=version+1 WHERE run_id=%s", (state, run or a.target)
        )


def _problem(response, status, code=None):
    assert response.status_code == status, (response.status_code, response.text[:300])
    payload = response.json()
    validate_contract("ProblemDetails", payload)
    if code:
        assert payload["code"] == code, payload
    return payload


# --- 1. only a failed terminal parent -------------------------------------------------

# States reachable from the fixture's ``planned`` parent by one guarded transition
# (inv.guard_run): awaiting_approval / scheduled / cancelled; ``planned`` itself is
# the untouched fixture. running/succeeded need attempt bumps + evidence and are
# covered by the same MODEL-0007 branch (state != 'failed').
@pytest.mark.parametrize("state", ["planned", "awaiting_approval", "scheduled", "cancelled"])
def test_non_failed_parent_is_refused_with_problem_details_and_no_child(runtime, state):
    a = runtime
    before = _lineage_count(a)
    if state != "planned":
        _set_state(a, state)
    with _client(a, {"requester": a.principal}) as client:
        response = _post(client, a, key=f"state-{state}")
    _problem(response, 409, "MODEL-0007")
    assert _lineage_count(a) == before


def test_failed_parent_with_unreleased_leases_waits_for_physical_release(runtime):
    """failed but leases still held -> LEASE-0003, not a child (no permit transfer)."""
    a = runtime
    _set_state(a, "failed")  # NOT releasing a.runtime_leases
    with _client(a, {"requester": a.principal}) as client:
        response = _post(client, a, key="held-leases")
    _problem(response, 409, "LEASE-0003")
    assert _lineage_count(a) == 0


# --- 2..7. the happy path, then idempotency / authz / shape / lineage on top of it ----

def test_failed_parent_yields_one_fresh_child_with_contract_shape_and_real_leases(runtime):
    a = runtime
    fail_unstarted(a)
    parent_tokens = {l["fencingToken"] for l in a.runtime_leases}

    with _client(a, {"requester": a.principal}) as client:
        first = _post(client, a, key="k1")
        assert first.status_code == 201, first.text[:400]
        result = first.json()

        # 4. exact contract shape == fixture shape (keys, nested keys), and validates
        validate_contract("ModelRetryPrepareResult", result)
        fixture = json.loads(FIXTURE.read_text("utf-8"))
        assert set(result) == set(fixture)
        assert set(result["run"]) == set(fixture["run"])
        assert set(result["placement"]) == set(fixture["placement"])
        assert set(result["placement"]["leases"][0]) == set(fixture["placement"]["leases"][0])

        # 5. honest: approval + frozen input still required; nothing auto-approved
        assert result["requiresFrozenInputAndApproval"] is True
        assert result["run"]["state"] == "planned"
        assert result["generation"] == 2 and result["rootRunId"] == a.target
        assert result["parentRunId"] == a.target
        child = result["run"]["runId"]
        assert child != a.target

        # 2. replay: same key + same body -> identical child, no second lineage row
        replay = _post(client, a, key="k1")
        assert replay.status_code == 201 and replay.json() == result
        # same key, different body -> 409 IDEM-0001
        other_body = {**_body(a), "policyVersion": "model-retry:2"}
        _problem(_post(client, a, key="k1", body=other_body), 409, "IDEM-0001")
        # missing key -> 422
        _problem(_post(client, a, key=None), 422, "VAL-0003")
        # another key for the same parent -> 409 (single child per parent)
        _problem(_post(client, a, key="k2"), 409, "MODEL-0003")

    with psycopg.connect(a.e.owner) as c:
        # 6. fresh lineage member, exactly one
        rows = c.execute(
            "SELECT root_run_id,parent_run_id,child_run_id,generation FROM inv.model_retry_lineage WHERE tenant_id=%s",
            (a.e.tenant,),
        ).fetchall()
        assert [tuple(r) for r in rows] == [(a.target, a.target, child, 2)]
        # 7. placement (6c) really reserved: response leases exist for the child in the DB
        db_leases = c.execute(
            "SELECT lease_id, fencing_token FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (child,),
        ).fetchall()
        assert {r[0] for r in db_leases} == {l["leaseId"] for l in result["placement"]["leases"]}
        # 6. no fencing token reuse from the parent's (released) leases
        assert not ({r[1] for r in db_leases} & parent_tokens)
        # 5. no permit / tool claim was minted for the child
        assert not c.execute(
            "SELECT 1 FROM inv.tool_claims WHERE run_id=%s", (child,)
        ).fetchone()
        # idempotency ledger row exists under the retry operation
        assert c.execute(
            "SELECT 1 FROM inv.idempotency WHERE project_id=%s AND operation='model.retry.prepare' AND key='k1'",
            (a.e.project,),
        ).fetchone()


# --- 3. authorization boundaries -----------------------------------------------------

def test_subject_without_can_request_is_refused_403_and_no_child(runtime):
    a = runtime
    fail_unstarted(a)
    people = a.approval.people  # requester(can_request), alice/bob(approve only), outsider(no grant)
    with _client(a, {"alice": people["alice"], "outsider": people["outsider"]}) as client:
        _problem(_post(client, a, token="alice", key="alice"), 403, "AUTH-0030")
        _problem(_post(client, a, token="outsider", key="outsider"), 403, "AUTH-0030")
    assert _lineage_count(a) == 0


def test_other_tenant_is_refused_403_and_never_creates_a_child(runtime):
    """F1 (Claude, 2026-09-22) was: a verified principal of ANOTHER tenant got 503
    SYS-0001 because ``ModelRetryStore.prepare`` inserted the idempotency ledger
    row before any grant check. Codex fixed it in 4473c7f1 with a ``can_request``
    preflight in the caller's tenant scope, so the cross-tenant request is now an
    honest **403 AUTH-0030** ProblemDetails. No child is created either way.
    """
    a = runtime
    fail_unstarted(a)
    intruder = Principal(a.e.other, "requester")
    with _client(a, {"intruder": intruder}) as client:
        response = _post(client, a, token="intruder", key="intruder")
    assert _lineage_count(a) == 0
    with a.e.db.transaction(a.e.other) as c:
        assert not c.execute("SELECT 1 FROM inv.model_retry_lineage").fetchone()
    payload = _problem(response, 403, "AUTH-0030")
    assert payload["retryable"] is False
