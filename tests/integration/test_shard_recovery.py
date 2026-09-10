"""Two real Go/mTLS Nodes, distinct journals/keys, one isolated CI Docker host."""

from concurrent.futures import ThreadPoolExecutor
from copy import copy, deepcopy
from dataclasses import replace
import subprocess
from uuid import uuid4
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from inv.db import Database
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.ids import new_id
from inv.node_channels import node_uri, provision_channel
from inv.node_transport import NodeTLSClient
from inv.observation import NodeObservation
from inv.shard_recovery import ShardRecovery
from inv.shards import ShardRuntime
from inv.tooling import NodePrincipal
from inv.workspace_api import RestrictedWorkspaceRuntime
from pki_support import issue, credentials
from test_approvals import approval, count, decide, challenge
from test_node_runtime import node_runtime
from test_node_delivery import remote, start, policy
from test_shards import admissions, active
from test_snapshots import storage

pytestmark = pytest.mark.postgres


@pytest.fixture
def pair(remote):
    a, b = remote, copy(remote)
    b.e = copy(a.e)
    b.e.node, b.e.resource, b.memory = new_id("nod"), new_id("res"), new_id("res")
    b.node = NodePrincipal(b.e.tenant, b.e.node)
    b.path = a.path / "replacement-node"
    b.path.mkdir(mode=0o700)
    b.key = Ed25519PrivateKey.generate()
    (b.path / "public.key").write_bytes(b.key.public_key().public_bytes_raw())
    b.args = list(a.args)
    for flag, value in (
        ("--node", b.e.node),
        ("--state", str(b.path / "state")),
        ("--public-key", str(b.path / "public.key")),
    ):
        b.args[b.args.index(flag) + 1] = value
    b.server_cert = issue(a.ca, node_uri(b.node, b.e.epoch), server=True)
    b.server_files = credentials(b.path, a.ca, b.server_cert, prefix="server")
    b.peer_policy = b.path / "peer-policy.json"
    policy(b, 1, [a.control_cert.fingerprint])
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES(%s,%s,'online',%s,0)",
            (a.e.tenant, b.e.node, a.e.epoch),
        )
        for resource, kind, amount in (
            (b.e.resource, "cpu", 1000),
            (b.memory, "memory", 268435456),
        ):
            conn.execute(
                "INSERT INTO inv.resources VALUES(%s,%s,%s,%s,%s,%s)",
                (a.e.tenant, resource, b.e.node, kind, amount, amount),
            )
        for node in (a.e.node, b.e.node):
            conn.execute(
                "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
                (a.e.tenant, a.e.project, node),
            )
    start(b)
    try:
        with psycopg.connect(a.e.owner) as conn:
            provision_channel(
                conn,
                b.node,
                epoch=b.e.epoch,
                endpoint=b.endpoint,
                certificate_der=b.server_cert.der,
                expected_version=0,
            )
        targets = {
            n.e.node: RestrictedWorkspaceRuntime(
                a.e.db,
                profile=n.profile,
                node=n.node,
                resources={"cpu": n.e.resource, "memory": n.memory},
                signing_key=n.key,
                policy_version="restricted:recovery:1",
                client=a.client,
            )
            for n in (a, b)
        }
        a.recovery = ShardRecovery(a.e.db, targets)
        yield a, b
    finally:
        if b.daemon.poll() is None:
            b.daemon.terminate()
            try:
                b.daemon.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                b.daemon.kill()
                b.daemon.communicate(timeout=5)


def source(a, *, stopped=True):
    original = admissions(a, [["/probe", "output"], ["/probe", "output"]])
    runtime = ShardRuntime(a.e.db, a.profile)
    result = runtime.enqueue(
        a.e.tenant, a.e.project, "source", original, signing_key=a.key, splittable=True
    )
    runtime.cancel(a.people["requester"], a.e.project, "source", key="cancel-source")
    if stopped:
        worker = DeliveryWorker(a.e.db, a.delivery)
        for shard in original:
            assert worker.once(a.e.tenant, command_id=shard.command["commandId"]) == "stopped"
    return original, result


def prepare(a, b, original, plan="retry-2", source_id="source", *, both_replaced=False):
    intents = [
        {"nodeId": b.e.node if both_replaced or i == 0 else a.e.node, "workload": s.workload}
        for i, s in enumerate(original)
    ]
    return a.recovery.prepare(
        a.people["requester"], a.e.project, source_id, plan, intents, key="prepare:" + plan
    )


def approve(a, prepared, *, first_only=False):
    for shard in prepared["shards"][:1] if first_only else prepared["shards"]:
        row = shard["approval"]
        for actor in ("alice", "bob"):
            row = decide(a, row, actor, challenge(a, row, actor), key=shard["runId"] + actor)


def enqueue(a, plan="retry-2", key=None):
    return a.recovery.enqueue(
        a.people["requester"], a.e.project, plan, key=key or "enqueue:" + plan
    )


def test_two_distinct_nodes_replace_and_aggregate_fresh_runs_once(pair, storage):
    a, b = pair
    original, old = source(a)
    prepared = prepare(a, b, original)
    assert active(a) == 0 and count(a, "shard_recoveries") == 0
    approve(a, prepared)
    result = enqueue(a)
    assert result["generation"] == 2 and result["parentRunId"] != old["parentRunId"]
    assert enqueue(a) == result
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    with a.e.db.transaction(a.e.tenant) as conn:
        commands = [
            str(r["command_id"])
            for r in conn.execute(
                "SELECT command_id FROM inv.shard_commands WHERE plan_id='retry-2'"
            ).fetchall()
        ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(lambda c: worker.once(a.e.tenant, command_id=c), commands)) == [
            "stopped",
            "stopped",
        ]
    worker.once(a.e.tenant)  # Reconcile after simultaneous completions.
    status = ShardRuntime(a.e.db, a.profile).status(a.e.tenant, a.e.project, "retry-2")
    assert (
        status["parentState"] == "succeeded"
        and status["allPhysicallyStopped"]
        and status["allSucceeded"]
    )
    assert status["generation"] == 2 and status["rootPlanId"] == "source"
    assert {s["nodeId"] for s in status["shards"]} == {a.e.node, b.e.node}
    assert count(a, "evidence") == 3 and active(a) == 0
    assert a.e.runs.get(a.e.tenant, old["parentRunId"])["state"] == "cancelled"
    assert all(
        a.e.runs.get(a.e.tenant, s.command["runId"])["state"] == "cancelled" for s in original
    )
    assert len(list((b.path / "state").glob("*.receipt"))) == 1
    assert len(list((a.path / "state").glob("*.receipt"))) == 3
    assert a.server_cert.fingerprint != b.server_cert.fingerprint


def test_unconfirmed_physical_stop_cannot_prepare_or_reserve(pair):
    a, b = pair
    original, _ = source(a, stopped=False)
    before = count(a, "runs")
    with pytest.raises(DomainError, match="LEASE-0003"):
        prepare(a, b, original)
    assert count(a, "runs") == before and active(a) == 4
    assert count(a, "shard_recovery_requests") == 0


def test_missing_second_approval_rolls_back_all_new_authority(pair):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    approve(a, prepared, first_only=True)
    with pytest.raises(DomainError, match="AUTH-0031"):
        enqueue(a)
    assert active(a) == 0 and count(a, "approval_dispatches") == 2
    assert count(a, "tool_claims") == 2 and count(a, "shard_recoveries") == 0
    assert all(
        a.e.runs.get(a.e.tenant, s["runId"])["state"] == "awaiting_approval"
        for s in prepared["shards"]
    )
    # The same request may retry after the missing votes arrive.
    approve(a, {"shards": prepared["shards"][1:]})
    assert enqueue(a)["generation"] == 2


def test_changed_workload_cannot_be_labeled_as_recovery(pair):
    a, b = pair
    original, _ = source(a)
    wrong = deepcopy(original[0].workload)
    wrong["command"].append("changed")
    original[0] = replace(original[0], workload=wrong)
    with pytest.raises(DomainError, match="AUTH-0011"):
        prepare(a, b, original)
    assert count(a, "shard_recovery_requests") == 0 and active(a) == 0


@pytest.mark.parametrize("revoked", ["requester", "voter", "membership"])
def test_authority_revoked_during_node_probe_prevents_admission(pair, monkeypatch, revoked):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    approve(a, prepared)
    target = a.recovery.targets[b.e.node]
    observe = target.observe

    def revoke_after_observe():
        result = observe()
        with psycopg.connect(a.e.owner) as conn:
            if revoked == "membership":
                conn.execute(
                    "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s AND node_id=%s",
                    (a.e.tenant, b.e.node),
                )
            else:
                conn.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
                    (a.e.tenant, "requester" if revoked == "requester" else "alice"),
                )
        return result

    monkeypatch.setattr(target, "observe", revoke_after_observe)
    with pytest.raises(DomainError, match="AUTH-0030"):
        enqueue(a)
    assert (
        active(a) == 0
        and count(a, "approval_dispatches") == 2
        and count(a, "shard_recoveries") == 0
    )


def test_competing_prepared_plans_commit_only_one_replacement(pair):
    a, b = pair
    original, _ = source(a)
    candidates = [prepare(a, b, original, name) for name in ("candidate-a", "candidate-b")]
    for candidate in candidates:
        approve(a, candidate)

    def compete(candidate):
        try:
            return enqueue(a, candidate["planId"])
        except DomainError as error:
            assert error.code in {"NODE-0064", "RES-0007"}
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(compete, candidates))
    assert sum(r is not None for r in results) == 1
    assert count(a, "shard_recoveries") == 1 and count(a, "tool_claims") == 4 and active(a) == 4


def test_three_generation_bound_preserves_terminal_history(pair):
    a, b = pair
    original, _ = source(a)
    runtime = ShardRuntime(a.e.db, a.profile)
    previous = "source"
    for generation in (2, 3):
        name = "generation-" + str(generation)
        prepared = prepare(a, b, original, name, previous)
        approve(a, prepared)
        result = enqueue(a, name)
        assert result["generation"] == generation
        runtime.cancel(a.people["requester"], a.e.project, name, key="cancel:" + name)
        worker = DeliveryWorker(a.e.db, a.delivery)
        assert worker.once(a.e.tenant) == worker.once(a.e.tenant) == "stopped"
        assert active(a) == 0
        previous = name
    with pytest.raises(DomainError, match="NODE-0064"):
        prepare(a, b, original, "generation-4", previous)
    assert count(a, "shard_recoveries") == 2 and count(a, "shard_plans") == 3


def test_partial_queue_failure_is_rolled_back_and_same_key_can_retry(pair, monkeypatch):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    approve(a, prepared)
    from inv.tooling import ToolGateway

    claim = ToolGateway.claim
    calls = []

    def fail_second(*args, **kwargs):
        result = claim(*args, **kwargs)
        calls.append(result)
        if len(calls) == 2:
            raise RuntimeError("synthetic crash after second queue insert")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(ToolGateway, "claim", fail_second)
        with pytest.raises(RuntimeError, match="synthetic crash"):
            enqueue(a)
    assert count(a, "shard_plans") == 1 and count(a, "tool_claims") == 2
    assert count(a, "approval_dispatches") == 2 and active(a) == 0
    assert count(a, "reservation_aborts") == 0
    assert enqueue(a)["generation"] == 2


def test_expired_preparation_can_be_replaced_without_consuming_generation(pair):
    a, b = pair
    original, _ = source(a)
    expired = prepare(a, b, original, "expired")
    approve(a, expired)
    # Move the entire approval time window using the migration owner in this fixture.
    with psycopg.connect(a.e.owner) as conn:
        conn.execute("ALTER TABLE inv.approval_requests DISABLE TRIGGER USER")
        conn.execute(
            "UPDATE inv.approval_requests SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE tenant_id=%s AND approval_id=ANY(%s)",
            (a.e.tenant, [s["approval"]["approvalId"] for s in expired["shards"]]),
        )
        conn.execute("ALTER TABLE inv.approval_requests ENABLE TRIGGER USER")
    with pytest.raises(DomainError, match="AUTH-0031"):
        enqueue(a, "expired")
    replacement = prepare(a, b, original, "fresh")
    approve(a, replacement)
    assert enqueue(a, "fresh")["generation"] == 2 and count(a, "shard_recoveries") == 1


def test_prepared_shard_cannot_dispatch_or_reserve_through_standalone_path(pair):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    approve(a, prepared)
    shard = prepared["shards"][0]
    with pytest.raises(DomainError, match="AUTH-0045"):
        a.store.dispatch(
            a.people["requester"],
            a.e.project,
            shard["approval"]["approvalId"],
            original[0].workload,
            key="bypass",
        )
    target = a.recovery.targets[b.e.node]
    with pytest.raises(DomainError, match="AUTH-0045"):
        a.e.leases.reserve(
            a.e.tenant,
            a.e.project,
            shard["runId"],
            target.allocations(original[0].workload),
            key="bypass",
        )
    assert active(a) == 0 and count(a, "approval_dispatches") == 2


def test_stale_epoch_and_cross_project_requests_do_not_create_recovery(pair):
    a, b = pair
    original, _ = source(a)
    stale = ShardRecovery(Database(a.e.runtime, recovery_epoch=str(uuid4())), a.recovery.targets)
    with pytest.raises(DomainError, match="LEASE-0004"):
        stale.prepare(
            a.people["requester"],
            a.e.project,
            "source",
            "stale",
            [{"nodeId": b.e.node, "workload": s.workload} for s in original],
            key="stale",
        )
    with pytest.raises(DomainError, match="RES-0004"):
        a.recovery.prepare(
            a.people["requester"],
            new_id("prj"),
            "source",
            "wrong-project",
            [{"nodeId": b.e.node, "workload": s.workload} for s in original],
            key="wrong-project",
        )
    assert count(a, "shard_recovery_requests") == 0


def test_cancelled_prepared_child_prevents_all_replacement_dispatch(pair):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    approve(a, prepared)
    child = a.e.runs.get(a.e.tenant, prepared["shards"][1]["runId"])
    a.e.runs.transition(a.e.tenant, child["runId"], "cancelled", expected_version=child["version"])
    with pytest.raises(DomainError, match="GRAPH-0003"):
        enqueue(a)
    assert active(a) == 0 and count(a, "tool_claims") == 2


def test_concurrent_same_key_replays_one_commit_and_rechecks_current_grant(pair):
    a, b = pair
    original, _ = source(a)
    prepared = prepare(a, b, original)
    assert prepare(a, b, original) == prepared
    approve(a, prepared)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: enqueue(a), range(2)))
    assert results[0] == results[1] and count(a, "shard_recoveries") == 1
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id='requester'",
            (a.e.tenant,),
        )
    with pytest.raises(DomainError, match="AUTH-0030"):
        enqueue(a)
    assert count(a, "execution_deliveries") == 4


def test_failed_parent_recovery_can_run_both_shards_on_replacement_node(pair, storage):
    a, b = pair
    original = admissions(a, [["/probe", "output"], ["/probe", "output"]])
    runtime = ShardRuntime(a.e.db, a.profile)
    old = runtime.enqueue(
        a.e.tenant, a.e.project, "source", original, signing_key=a.key, splittable=True
    )
    # Cancel one admitted child: worker fail-fast marks the parent failed and
    # stops its sibling. The next generation still needs two fresh approvals.
    child = a.e.runs.get(a.e.tenant, original[0].command["runId"])
    a.e.runs.transition(a.e.tenant, child["runId"], "cancelled", expected_version=child["version"])
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=storage.provider)
    for shard in original:
        assert worker.once(a.e.tenant, command_id=shard.command["commandId"]) == "stopped"
    assert a.e.runs.get(a.e.tenant, old["parentRunId"])["state"] == "failed"
    prepared = prepare(a, b, original, both_replaced=True)
    approve(a, prepared)
    replacement = enqueue(a)
    assert worker.once(a.e.tenant) == worker.once(a.e.tenant) == "stopped"
    assert a.e.runs.get(a.e.tenant, replacement["parentRunId"])["state"] == "succeeded"
    assert a.e.runs.get(a.e.tenant, old["parentRunId"])["state"] == "failed"
    assert len(list((b.path / "state").glob("*.receipt"))) == 2 and active(a) == 0


@pytest.mark.parametrize("supersessions", [1, 3])
def test_node_observation_retries_with_fresh_nonces_and_a_hard_bound(
    pair, monkeypatch, supersessions
):
    a, _ = pair
    target = a.recovery.targets[a.e.node]
    probe = a.client.probe
    independent = NodeObservation(a.e.db, NodeTLSClient(**a.client_files))
    nonces = []

    def overtake(proof, request):
        nonces.append(request["nonce"])
        response = probe(proof, request)
        if len(nonces) <= supersessions:
            independent.poll(a.node)  # Commit a genuinely newer authenticated probe.
        return response

    monkeypatch.setattr(a.client, "probe", overtake)
    if supersessions == 3:
        with pytest.raises(DomainError, match="NODE-0050") as failure:
            target.observe()
        assert failure.value.retryable and failure.value.status == 409
        assert len(nonces) == 3
    else:
        assert target.observe().node_id == a.e.node
        assert len(nonces) == 2
    assert len(nonces) == len(set(nonces)) and active(a) == 0


def test_probe_scope_failure_is_not_retried(pair, monkeypatch):
    a, _ = pair
    probe = a.client.probe
    calls = []

    def wrong_epoch(proof, request):
        calls.append(request["nonce"])
        response = probe(proof, request)
        response["recoveryEpoch"] = str(uuid4())
        return response

    monkeypatch.setattr(a.client, "probe", wrong_epoch)
    with pytest.raises(DomainError, match="NODE-0050") as failure:
        a.recovery.targets[a.e.node].observe()
    assert failure.value.status == 403 and not failure.value.retryable
    assert len(calls) == 1 and active(a) == 0
