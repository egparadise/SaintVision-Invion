"""Real PG/file negative tests; CPU telemetry is synthetic, not remote acceptance."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
import hashlib

import psycopg
from psycopg.types.json import Jsonb
import pytest
from inv.approvals import Principal
from inv.errors import DomainError
from inv.ids import new_id
from inv.model_locality import LocalModelObservation, ModelLocalityStore
from inv.model_runtime import require_model_reference
from inv.placement import PlacementStore
from inv.scheduler import Request
from test_model_commit import model, commit
from test_storage_commit import sample, storage_subject
from test_postgres import planned
from test_approvals import approval
from test_tool_admission import gateway, claim

pytestmark = pytest.mark.postgres


@pytest.fixture
def locality(model):
    a = model
    commit(a)
    a.target = planned(a.e)["runId"]
    a.request = Request(2, 10, required_bytes=12, max_host_load=Decimal(1))
    a.locality = ModelLocalityStore(a.e.db, a.verifier)
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
        c.execute(
            "INSERT INTO inv.project_resource_limits(tenant_id,project_id,cpu_millis,memory_bytes) VALUES(%s,%s,10,100)",
            (a.e.tenant, a.e.project),
        )
        c.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'memory',100,100)",
            (a.e.tenant, new_id("res"), a.e.node),
        )
        snapshot = {
            "nonce": "0" * 64,
            "tenantId": a.e.tenant,
            "nodeId": a.e.node,
            "recoveryEpoch": a.e.epoch,
            "profileVersion": "synthetic-test",
            "observedAt": datetime.now(timezone.utc).isoformat(),
            "sampleMillis": 100,
            "cpuCapacityMillis": 10,
            "cpuBusyMillis": 0,
            "memoryCapacityBytes": 100,
            "memoryAvailableBytes": 100,
            "osType": "linux",
            "agentVersion": "0.1.0",
        }
        c.execute(
            "INSERT INTO inv.node_resource_snapshots(tenant_id,node_id,recovery_epoch,channel_version,snapshot) VALUES(%s,%s,%s,1,%s)",
            (a.e.tenant, a.e.node, a.e.epoch, Jsonb(snapshot)),
        )
    return a


def observe(a, **kwargs):
    return a.locality.observe(
        a.principal, a.e.project, a.body["modelId"], a.body["version"], **kwargs
    )


def reserve(a, observation=None, *, key="local", run=None, principal=None):
    return PlacementStore(a.e.db).reserve(
        principal or a.principal,
        a.e.project,
        run or a.target,
        a.request,
        key=key,
        policy_version="model-test:1",
        model_observation=observation or observe(a),
    )


def no_reservation(a):
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute(
            "SELECT 1 FROM inv.resource_leases WHERE run_id=%s", (a.target,)
        ).fetchone()
        assert not c.execute(
            "SELECT 1 FROM inv.model_run_inputs WHERE run_id=%s", (a.target,)
        ).fetchone()


def test_verified_locality_binds_existing_leases_and_durable_duplicate(locality):
    a = locality
    measured = observe(a)
    first = reserve(a, measured)
    assert first["placement"]["nodeId"] == a.e.node
    assert first["placement"]["modelInput"]["manifestHash"] == measured.manifest_hash
    assert first["placement"]["modelInput"]["requiresExecutionRevalidation"]
    assert (
        reserve(a, replace(measured, observed_at=measured.observed_at - timedelta(days=1))) == first
    )
    with a.e.db.transaction(a.e.tenant) as c:
        row = c.execute(
            "SELECT input FROM inv.model_run_inputs WHERE run_id=%s", (a.target,)
        ).fetchone()
        assert row["input"]["leases"] == first["leases"]
        with pytest.raises(DomainError, match="MODEL-0006"):
            require_model_reference(c, {"run_id": a.target}, {})
        require_model_reference(c, {"run_id": a.run}, {})


@pytest.mark.parametrize("kind", ["corrupt", "truncated", "missing", "budget"])
def test_manifest_verified_flag_cannot_replace_current_bytes(locality, kind):
    a = locality
    if kind == "missing":
        (a.root / "data.bin").unlink()
    elif kind == "budget":
        a.verifier.max_read_bytes = 1
    else:
        (a.root / "data.bin").write_bytes(b"corrupt data" if kind == "corrupt" else b"cut")
    # corrupt/truncated/missing/budget all fail the byte re-check as MODEL-0001 (ZZPROBE, real PG).
    with pytest.raises(DomainError, match="MODEL-0001"):
        reserve(a)
    no_reservation(a)


@pytest.mark.parametrize(
    "kind",
    ["expired", "future", "location", "root", "membership", "grant", "offline", "scope", "size"],
)
def test_changed_authority_or_observation_cannot_reserve(locality, kind):
    a = locality
    measured = observe(a)
    if kind in ("expired", "future"):
        measured = replace(
            measured,
            observed_at=measured.observed_at + timedelta(seconds=-16 if kind == "expired" else 30),
        )
    elif kind == "scope":
        measured = replace(measured, subject="outsider")
    elif kind == "size":
        a.request = replace(a.request, required_bytes=11)
    else:
        queries = {
            "location": "UPDATE public.data_locations SET version=version+1 WHERE tenant_id=%s",
            "root": "UPDATE public.storage_contributions SET version=version+1 WHERE tenant_id=%s",
            "membership": "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s",
            "grant": "UPDATE inv.project_grants SET can_request=false WHERE tenant_id=%s",
            "offline": "UPDATE inv.nodes SET status='offline' WHERE tenant_id=%s",
        }
        with psycopg.connect(a.e.owner) as c:
            c.execute(queries[kind], (a.e.tenant,))
    # Per-kind refusal codes confirmed vs real PG (ZZPROBE): a stale/future observation is MODEL-0005,
    # a revoked grant AUTH-0030, a dropped membership RES-0003, an out-of-scope/oversize request
    # AUTH-0011; location/root/offline version bumps re-check the model (MODEL-0001). A bare raises
    # conflated authorization, lease-window, membership and model refusals into one.
    expected = {"expired": "MODEL-0005", "future": "MODEL-0005", "location": "MODEL-0001",
                "root": "MODEL-0001", "membership": "RES-0003", "grant": "AUTH-0030",
                "offline": "MODEL-0001", "scope": "AUTH-0011", "size": "AUTH-0011"}
    with pytest.raises(DomainError, match=expected[kind]):
        reserve(a, measured)
    no_reservation(a)


def test_atomic_binding_failure_rolls_back_lease_ledger_and_outbox(locality, monkeypatch):
    a = locality
    measured = observe(a)

    def fail(*args):
        raise DomainError("MODEL-0005", "Injected binding failure")

    monkeypatch.setattr(LocalModelObservation, "bind", fail)
    # The injected bind failure is MODEL-0005 (the fail() above raises it); pin it so the rollback
    # assertions below cannot be reached by some other DomainError.
    with pytest.raises(DomainError, match="MODEL-0005"):
        reserve(a, measured)
    no_reservation(a)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute("SELECT 1 FROM inv.idempotency WHERE key='local'").fetchone()
        assert not c.execute(
            "SELECT 1 FROM inv.outbox WHERE run_id=%s AND event_type='inv.run.placement_reserved'",
            (a.target,),
        ).fetchone()


def test_concurrent_same_key_reserves_once(locality):
    a = locality
    measured = observe(a)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: reserve(a, measured), range(4)))
    assert all(r == results[0] for r in results)
    with a.e.db.transaction(a.e.tenant) as c:
        assert (
            c.execute(
                "SELECT count(*) AS n FROM inv.resource_leases WHERE run_id=%s", (a.target,)
            ).fetchone()["n"]
            == 2
        )


def test_concurrent_model_runs_share_existing_resource_ceilings(locality):
    a = locality
    measured = observe(a)
    runs = [planned(a.e)["runId"] for _ in range(6)]

    def take(run):
        try:
            return reserve(a, measured, key=run, run=run)
        except DomainError as error:
            assert error.code in {"RES-0001", "RES-0003", "RES-0007"}

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(take, runs))
    assert sum(r is not None for r in results) == 4
    with a.e.db.transaction(a.e.tenant) as c:
        assert (
            c.execute(
                "SELECT sum(amount) AS n FROM inv.resource_leases WHERE resource_id=%s AND released_at IS NULL",
                (a.e.resource,),
            ).fetchone()["n"]
            == 9
        )


def test_more_cpu_without_model_copy_cannot_invent_transfer_bandwidth(locality):
    from inv.node_channels import provision_channel, node_uri
    from inv.tooling import NodePrincipal
    from pki_support import authority, issue

    a = locality
    other = new_id("nod")
    principal = NodePrincipal(a.e.tenant, other)
    certificate = issue(authority(), node_uri(principal, a.e.epoch), server=True)
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES(%s,%s,'online',%s,0)",
            (a.e.tenant, other, a.e.epoch),
        )
        c.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, other),
        )
        for kind in ("cpu", "memory"):
            c.execute(
                "INSERT INTO inv.resources VALUES(%s,%s,%s,%s,100,100)",
                (a.e.tenant, new_id("res"), other, kind),
            )
        provision_channel(
            c,
            principal,
            epoch=a.e.epoch,
            endpoint="https://127.0.0.1:18444",
            certificate_der=certificate.der,
            expected_version=0,
        )
        snapshot = c.execute(
            "SELECT snapshot FROM inv.node_resource_snapshots WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        ).fetchone()[0]
        snapshot.update(nodeId=other, cpuCapacityMillis=100)
        c.execute(
            "INSERT INTO inv.node_resource_snapshots(tenant_id,node_id,recovery_epoch,channel_version,snapshot) VALUES(%s,%s,%s,1,%s)",
            (a.e.tenant, other, a.e.epoch, Jsonb(snapshot)),
        )
    result = reserve(a)
    assert result["placement"]["nodeId"] == a.e.node
    assert other in result["placement"]["rejected"]
    assert any("bandwidth" in reason for reason in result["placement"]["rejected"][other])


def test_post_observation_file_change_never_becomes_an_execution_permit(locality):
    a = locality
    measured = observe(a)
    (a.root / "data.bin").write_bytes(b"changed data")
    reserve(a, measured)
    with a.e.db.transaction(a.e.tenant) as c:
        with pytest.raises(DomainError, match="MODEL-0006"):
            require_model_reference(c, {"run_id": a.target}, {})


def test_actual_tool_gateway_cannot_ignore_model_input(locality, approval):
    a = locality
    # This fixture has a linked business project, so grant all three approval
    # actors real business membership before constructing the approved command.
    with psycopg.connect(a.e.owner) as c:
        for label in ("requester", "alice", "bob"):
            subject = "oidc:" + hashlib.sha256(uuid4().bytes).hexdigest()
            approval.people[label] = Principal(a.e.tenant, subject)
            c.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,true)",
                (a.e.tenant, a.e.project, subject, label == "requester"),
            )
            user = new_id("usr")
            c.execute(
                "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, user, subject, subject),
            )
            c.execute(
                "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,'owner')",
                (a.e.tenant, a.e.project, user),
            )
            c.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (a.e.tenant, subject, user),
            )
    approval.policy["subjectId"] = approval.people["requester"].subject_id
    g = gateway.__wrapped__(approval)
    measured = observe(a)
    # The owner fixture attaches the immutable input to an otherwise valid,
    # approved and leased command. The production gateway must still refuse it.
    with a.e.db.transaction(a.e.tenant) as c:
        measured.bind(
            c,
            a.principal,
            a.e.project,
            g.run["runId"],
            {"placement": {"nodeId": a.e.node}, "leases": g.leases},
        )
    with pytest.raises(DomainError, match="MODEL-0006"):
        claim(g)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute(
            "SELECT 1 FROM inv.tool_claims WHERE run_id=%s", (g.run["runId"],)
        ).fetchone()


def test_bound_input_is_immutable_tenant_scoped_and_cannot_be_replaced(locality):
    a = locality
    measured = observe(a)
    reserve(a, measured)
    with pytest.raises(DomainError, match="MODEL-0003"):
        reserve(a, measured, key="second")
    with a.e.db.transaction(a.e.other) as c:
        assert not c.execute("SELECT 1 FROM inv.model_run_inputs").fetchone()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as c:
            c.execute("DELETE FROM inv.model_run_inputs WHERE run_id=%s", (a.target,))
    # An outsider principal is refused as AUTH-0030 (permission), confirmed vs real PG (ZZPROBE).
    with pytest.raises(DomainError, match="AUTH-0030"):
        reserve(a, measured, principal=Principal(a.e.tenant, "outsider"))


@pytest.mark.parametrize(
    "mode", ["tensor-parallel", "pipeline-parallel", "data-parallel", "offload", "request-routing"]
)
def test_unimplemented_modes_are_explicitly_unavailable(locality, mode):
    with pytest.raises(DomainError, match="MODEL-0002"):
        observe(locality, mode=mode)
    no_reservation(locality)
