"""Real PG/file retry invariants; physical stop/replacement is covered by Node tests."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.errors import DomainError
from inv.contracts import validate_contract
from inv.model_retry import ModelRetryStore
from test_model_runtime import runtime
from test_model_locality import locality
from test_model_commit import model
from test_storage_commit import sample, storage_subject
from test_approvals import approval

pytestmark = pytest.mark.postgres


def fail_unstarted(a, run=None, leases=None, *, state="failed"):
    run = run or a.target
    leases = leases or a.runtime_leases
    with psycopg.connect(a.e.owner) as c:
        c.execute("UPDATE inv.runs SET state=%s,version=version+1 WHERE run_id=%s", (state, run))
    # There is no execution claim in this unit fixture, so these logical
    # reservations can be released without simulating a process stop receipt.
    for lease in leases:
        a.e.leases.release(
            a.e.tenant,
            lease["leaseId"],
            lease["fencingToken"],
            authenticated_node_id=a.e.node,
            stop_receipt=str(uuid4()),
        )


def retry(a, parent=None, *, key="retry"):
    return ModelRetryStore(a.e.db, a.verifier).prepare(
        a.principal,
        a.e.project,
        parent or a.target,
        a.request,
        key=key,
        policy_version="model-retry:1",
    )


def test_failed_model_run_retry_is_served_with_fresh_child_and_replays(runtime):
    a = runtime
    fail_unstarted(a)

    class Tokens:
        tenant_id = a.e.tenant

        @staticmethod
        def verify(value):
            return SimpleNamespace(principal=a.principal, expires_at="2026-09-22T09:00:00Z")

        @staticmethod
        def _keys():
            return None
    request = a.request
    body = {
        "cpuMillis": request.cpu_millis,
        "memoryBytes": request.memory_bytes,
        "gpuCount": request.gpu_count,
        "minVramBytes": request.min_vram_bytes,
        "requiredBytes": request.required_bytes,
        "maxHostLoad": float(request.max_host_load),
        "runtime": request.runtime,
        "policyVersion": "model-retry:1",
    }
    headers = {
        "Authorization": "Bearer synthetic",
        "Idempotency-Key": "http-model-retry",
    }
    url = f"/v1/projects/{a.e.project}/runs/{a.target}/model-retries"
    app = create_app(
        a.e.db,
        Tokens(),
        model_retry=ModelRetryStore(a.e.db, a.verifier),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        first = client.post(url, json=body, headers=headers)
        replay = client.post(url, json=body, headers=headers)
        conflict = client.post(
            url,
            json={**body, "policyVersion": "model-retry:changed"},
            headers=headers,
        )
    assert first.status_code == replay.status_code == 201, (first.json(), replay.json())
    assert first.json() == replay.json()
    result = first.json()
    validate_contract("ModelRetryPrepareResult", result)
    assert result["parentRunId"] == a.target
    assert result["run"]["runId"] != a.target
    assert result["run"]["state"] == "planned"
    assert result["placement"]["runId"] == result["run"]["runId"]
    assert result["requiresFrozenInputAndApproval"] is True
    assert conflict.status_code == 409
    validate_contract("ProblemDetails", conflict.json())
    with a.e.db.transaction(a.e.tenant) as conn:
        assert not conn.execute("SELECT 1 FROM inv.tool_claims").fetchone()

    class InvalidModelRetry:
        @staticmethod
        def prepare(*args, **kwargs):
            return {
                "rootRunId": result["rootRunId"],
                "parentRunId": result["parentRunId"],
                "generation": result["generation"],
                "run": result["run"],
                "reservation": {
                    "runId": result["placement"]["runId"],
                    "placement": {
                        "nodeId": result["placement"]["nodeId"],
                        "snapshotId": result["placement"]["snapshotId"],
                        "policyVersion": result["placement"]["policyVersion"],
                    },
                    "leases": result["placement"]["leases"],
                },
                "requiresFrozenInputAndApproval": False,
            }

    with TestClient(
        create_app(a.e.db, Tokens(), model_retry=InvalidModelRetry()),
        raise_server_exceptions=False,
    ) as client:
        rejected = client.post(
            url,
            json=body,
            headers={**headers, "Idempotency-Key": "invalid-service-result"},
        )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "VAL-0002"


def test_retry_uses_new_run_fences_and_requires_new_approval(runtime):
    a = runtime
    fail_unstarted(a)
    result = retry(a)
    assert result == retry(a)
    assert result["generation"] == 2 and result["rootRunId"] == a.target
    assert result["requiresFrozenInputAndApproval"]
    assert result["run"]["state"] == "planned"
    assert result["run"]["runId"] != a.target
    old = {l["fencingToken"] for l in a.runtime_leases}
    assert not old & {l["fencingToken"] for l in result["reservation"]["leases"]}
    with pytest.raises(DomainError, match="MODEL-0003"):
        retry(a, key="another")
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute("SELECT 1 FROM inv.tool_claims").fetchone()


def test_three_generations_are_a_hard_budget(runtime):
    a = runtime
    fail_unstarted(a)
    second = retry(a)
    fail_unstarted(a, second["run"]["runId"], second["reservation"]["leases"])
    third = retry(a, second["run"]["runId"], key="third")
    assert third["generation"] == 3 and third["rootRunId"] == a.target
    fail_unstarted(a, third["run"]["runId"], third["reservation"]["leases"])
    with pytest.raises(DomainError, match="MODEL-0007"):
        retry(a, third["run"]["runId"], key="fourth")


@pytest.mark.parametrize("fault", ["active", "cancel", "grant", "bytes"])
def test_retry_cannot_bypass_stop_cancel_grant_or_locality(runtime, fault):
    a = runtime
    if fault == "active":
        with psycopg.connect(a.e.owner) as c:
            c.execute(
                "UPDATE inv.runs SET state='failed',version=version+1 WHERE run_id=%s", (a.target,)
            )
    else:
        fail_unstarted(a, state="cancelled" if fault == "cancel" else "failed")
        if fault == "grant":
            with psycopg.connect(a.e.owner) as c:
                c.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE subject_id=%s",
                    (a.principal.subject_id,),
                )
        elif fault == "bytes":
            (a.root / "data.bin").write_bytes(b"corrupt data")
    with pytest.raises(DomainError):
        retry(a)
    with psycopg.connect(a.e.owner) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM inv.model_retry_lineage WHERE tenant_id=%s", (a.e.tenant,)
            ).fetchone()[0]
            == 0
        )


def test_failed_new_reservation_rolls_back_child_and_lineage(runtime):
    a = runtime
    fail_unstarted(a)
    with psycopg.connect(a.e.owner) as c:
        before = c.execute(
            "SELECT count(*) FROM inv.runs WHERE tenant_id=%s", (a.e.tenant,)
        ).fetchone()[0]
        c.execute(
            "UPDATE inv.project_resource_limits SET cpu_millis=1,version=version+1 WHERE tenant_id=%s",
            (a.e.tenant,),
        )
    with pytest.raises(DomainError):
        retry(a)
    with psycopg.connect(a.e.owner) as c:
        assert (
            c.execute("SELECT count(*) FROM inv.runs WHERE tenant_id=%s", (a.e.tenant,)).fetchone()[
                0
            ]
            == before
        )
        assert (
            c.execute(
                "SELECT count(*) FROM inv.model_retry_lineage WHERE tenant_id=%s", (a.e.tenant,)
            ).fetchone()[0]
            == 0
        )


def test_concurrent_retry_is_single_child_and_tenant_private(runtime):
    a = runtime
    fail_unstarted(a)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: retry(a), range(2)))
    assert results[0] == results[1]
    with a.e.db.transaction(a.e.other) as c:
        assert not c.execute("SELECT 1 FROM inv.model_retry_lineage").fetchone()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as c:
            c.execute("DELETE FROM inv.model_retry_lineage")
