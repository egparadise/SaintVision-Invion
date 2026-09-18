"""Real PG/bytes/approval tests; the separate Node suite proves process execution."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from inv.approvals import Principal
from inv.contracts import validate_contract
from inv.dispatch import DeliveryQueue
from inv.errors import DomainError
from inv.ids import new_id
from inv.model_runtime import ModelRuntimeStore, approved_model
from inv.policy import action_digest
from inv.sandbox import SandboxProfile
from inv.tooling import ToolGateway, NodePrincipal
from inv.workspace_files import decode_snapshot
from test_model_locality import locality, reserve
from test_model_commit import model
from test_storage_commit import sample, storage_subject
from test_approvals import approval, approved, dispatch
from test_tool_admission import inputs

pytestmark = pytest.mark.postgres


def actors(a, approval):
    approval.people["requester"] = a.principal
    with psycopg.connect(a.e.owner) as c:
        for label in ("alice", "bob"):
            subject = "oidc:" + hashlib.sha256(uuid4().bytes).hexdigest()
            user = new_id("usr")
            approval.people[label] = Principal(a.e.tenant, subject)
            c.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_approve) VALUES(%s,%s,%s,true)",
                (a.e.tenant, a.e.project, subject),
            )
            c.execute(
                "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, user, subject, label),
            )
            c.execute(
                "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,'owner')",
                (a.e.tenant, a.e.project, user),
            )
            c.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (a.e.tenant, subject, user),
            )
    approval.policy["subjectId"] = a.principal.subject_id


@pytest.fixture
def runtime(locality, approval):
    a = locality
    result = reserve(a)
    a.runtime_leases = result["leases"]
    a.runtime_proofs = {l["leaseId"]: l["fencingToken"] for l in result["leases"]}
    a.raw_workload = deepcopy(approval.workload)
    a.raw_workload.update(
        command=["/usr/bin/printf", "model-files"],
        resources={"cpuMillis": 2, "memoryBytes": 10, "gpuCount": 0, "minVramBytes": 0},
    )
    a.runtime_store = ModelRuntimeStore(a.e.db, a.verifier)
    a.approval = approval
    actors(a, approval)
    return a


def freeze(a, *, key="freeze", workload=None):
    return a.runtime_store.prepare(
        a.principal, a.e.project, a.target, workload or a.raw_workload, a.runtime_proofs, key=key
    )


def authorize(a):
    frozen = freeze(a)
    g = a.approval
    g.run = a.e.runs.get(a.e.tenant, a.target)
    g.workload = frozen["workload"]
    g.policy["actionDigest"] = action_digest(g.workload)
    g.command = dispatch(g, approved(g))
    g.profile = SandboxProfile(
        "restricted:test:1",
        frozenset({g.workload["imageDigest"]}),
        frozenset({g.workload["command"][0]}),
    )
    g.gateway = ToolGateway(a.e.db, g.profile)
    g.node = NodePrincipal(a.e.tenant, a.e.node)
    g.proofs = a.runtime_proofs
    return g


def claim(g, **kwargs):
    return g.gateway.claim(g.node, g.command, g.workload, g.proofs, **inputs(g), **kwargs)


def test_frozen_bytes_and_model_hash_are_bound_to_approved_signed_plan(runtime):
    a = runtime
    g = authorize(a)
    (a.root / "data.bin").write_bytes(b"changed data")
    result = claim(g)
    assert result.may_start
    validate_contract("SandboxLaunchSpec", result.launch)
    import base64

    raw = base64.b64decode(result.launch["workspaceInput"]["dataBase64"])
    _, files = decode_snapshot(raw, g.workload["workspaceId"])
    assert files["model/0000.bin"] == b"actual bytes"
    assert g.workload["modelInput"]["inputSha256"] == hashlib.sha256(raw).hexdigest()
    assert not claim(g).may_start


def test_freeze_is_immutable_idempotent_and_tenant_scoped(runtime, monkeypatch):
    a = runtime
    result = freeze(a)
    monkeypatch.setattr(
        a.verifier, "freeze", lambda *args: pytest.fail("Durable replay reread bytes")
    )
    assert freeze(a) == result
    with pytest.raises(DomainError, match="MODEL-0003"):
        freeze(a, key="different")
    with a.e.db.transaction(a.e.other) as c:
        assert not c.execute("SELECT 1 FROM inv.model_runtime_inputs").fetchone()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a.e.db.transaction(a.e.tenant) as c:
            c.execute("DELETE FROM inv.model_runtime_inputs")


@pytest.mark.parametrize("fault", ["cancel", "grant", "lease", "epoch", "location", "root", "node"])
def test_freeze_rechecks_authority_after_file_io(runtime, monkeypatch, fault):
    a = runtime
    original = a.verifier.freeze
    changes = {
        "cancel": (
            "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s",
            a.target,
        ),
        "grant": ("UPDATE inv.project_grants SET enabled=false WHERE project_id=%s", a.e.project),
        "lease": (
            "UPDATE inv.resource_leases SET granted_at=clock_timestamp()-interval '10 seconds',expires_at=clock_timestamp()-interval '1 second' WHERE run_id=%s",
            a.target,
        ),
        "epoch": ("UPDATE inv.control_epoch SET epoch=%s", str(uuid4())),
        "location": (
            "UPDATE public.data_locations SET version=version+1 WHERE contribution_id=%s",
            a.contribution,
        ),
        "root": (
            "UPDATE public.storage_contributions SET version=version+1 WHERE contribution_id=%s",
            a.contribution,
        ),
        "node": ("UPDATE inv.nodes SET status='offline' WHERE node_id=%s", a.e.node),
    }

    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        with psycopg.connect(a.e.owner) as c:
            sql, value = changes[fault]
            c.execute(sql, (value,))
        return result

    monkeypatch.setattr(a.verifier, "freeze", read)
    with pytest.raises(DomainError):
        freeze(a)
    with psycopg.connect(a.e.owner) as c:
        assert (
            c.execute(
                "SELECT count(*) FROM inv.model_runtime_inputs WHERE tenant_id=%s", (a.e.tenant,)
            ).fetchone()[0]
            == 0
        )


@pytest.mark.parametrize("fault", ["bytes", "missing-proof", "stale-proof", "foreign-node", "gpu"])
def test_invalid_model_input_cannot_freeze(runtime, fault):
    a = runtime
    if fault == "bytes":
        (a.root / "data.bin").write_bytes(b"corrupt data")
    elif fault == "missing-proof":
        a.runtime_proofs = {}
    elif fault == "stale-proof":
        a.runtime_proofs = {k: v + "1" for k, v in a.runtime_proofs.items()}
    elif fault == "foreign-node":
        a.raw_workload["targetNodeId"] = new_id("nod")
    else:
        a.raw_workload["resources"]["gpuCount"] = 1
    with pytest.raises(DomainError):
        freeze(a)


@pytest.mark.parametrize("fault", ["cancel", "grant", "node", "root", "fence", "changed-action"])
def test_model_admission_rechecks_current_authority(runtime, fault):
    a = runtime
    g = authorize(a)
    if fault == "changed-action":
        g.workload["command"][1] = "different-action"
    elif fault == "fence":
        g.proofs = {k: v + "1" for k, v in g.proofs.items()}
    else:
        changes = {
            "cancel": (
                "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s",
                a.target,
            ),
            "grant": (
                "UPDATE inv.project_grants SET enabled=false WHERE subject_id=%s",
                a.principal.subject_id,
            ),
            "node": ("UPDATE inv.nodes SET status='offline' WHERE node_id=%s", a.e.node),
            "root": (
                "UPDATE public.storage_contributions SET version=version+1 WHERE contribution_id=%s",
                a.contribution,
            ),
        }
        with psycopg.connect(a.e.owner) as c:
            sql, value = changes[fault]
            c.execute(sql, (value,))
    with pytest.raises(DomainError):
        claim(g)


def test_concurrent_freeze_keeps_one_snapshot(runtime, monkeypatch):
    a = runtime
    barrier = Barrier(2)
    original = a.verifier.freeze

    def read(*args, **kwargs):
        barrier.wait(timeout=10)
        return original(*args, **kwargs)

    monkeypatch.setattr(a.verifier, "freeze", read)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=15) for f in [pool.submit(freeze, a), pool.submit(freeze, a)]]
    assert results[0] == results[1]


def test_queued_model_cannot_start_after_storage_authority_changes(runtime):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    a = runtime
    g = authorize(a)
    assert not claim(g, queue_signing_key=Ed25519PrivateKey.generate()).may_start
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "UPDATE public.storage_contributions SET version=version+1 WHERE contribution_id=%s",
            (a.contribution,),
        )
    attempt = DeliveryQueue(a.e.db).acquire(a.e.tenant, command_id=g.command["commandId"])
    assert attempt is not None and attempt.operation != "execute"


def test_adapter_cannot_commit_inconsistent_frozen_bytes(runtime, monkeypatch):
    a = runtime
    original = a.verifier.freeze

    def inconsistent(*args, **kwargs):
        verified, chunks = original(*args, **kwargs)
        chunks[0] = b"corrupt data"
        return verified, chunks

    monkeypatch.setattr(a.verifier, "freeze", inconsistent)
    with pytest.raises(DomainError):
        freeze(a)
    with a.e.db.transaction(a.e.tenant) as c:
        assert not c.execute(
            "SELECT 1 FROM inv.model_runtime_inputs WHERE run_id=%s", (a.target,)
        ).fetchone()
