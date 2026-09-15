"""Actual Go Node/mTLS/Docker Python model input; isolated, not physical-PC acceptance."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import copy, deepcopy
from decimal import Decimal
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import time
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
import pytest
from inv.dispatch import DeliveryWorker
from inv.ids import new_id
from inv.leases import Allocation
from inv.model_commit import ModelManifestStore
from inv.model_locality import ModelLocalityStore
from inv.model_manifest import ConfiguredModelVerifier, RootBinding
from inv.model_runtime import ModelRuntimeStore
from inv.model_retry import ModelRetryStore
from inv.node_channels import node_uri, provision_channel
from inv.observation import NodeObservation
from inv.output_ingestion import OutputIngestion
from inv.placement import PlacementStore
from inv.policy import action_digest
from inv.scheduler import Request
from inv.tooling import ToolGateway, NodePrincipal
from inv.workspace_api import RestrictedWorkspaceRuntime
from inv.workspace_files import decode_snapshot
from saintvision.storage.readroot import ReadRoot
from model_support import model_body
from test_approvals import approval, request as request_approval, decide, challenge, dispatch, count
from test_node_delivery import remote, start, policy
from test_node_runtime import node_runtime, active, container
from test_snapshots import storage
from test_storage_commit import register_owner
from test_workspace_start import first
from test_model_runtime import actors
from test_tool_admission import inputs
from pki_support import issue, credentials
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Real Linux Node model execution"),
]


@pytest.fixture
def model_extra(first, request):
    if not getattr(request, "param", False):
        yield None
        return
    a, b = first, copy(first)
    b.e = copy(a.e)
    b.e.node, b.e.resource, b.memory = new_id("nod"), new_id("res"), new_id("res")
    b.node = NodePrincipal(b.e.tenant, b.e.node)
    b.path = a.path / "replacement-model-node"
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
    with psycopg.connect(a.e.owner) as c:
        c.execute(
            "INSERT INTO inv.nodes(tenant_id,node_id,status,recovery_epoch,clock_skew_seconds) VALUES(%s,%s,'online',%s,0)",
            (a.e.tenant, b.e.node, a.e.epoch),
        )
        for resource, kind, amount in (
            (b.e.resource, "cpu", 1000),
            (b.memory, "memory", 268435456),
        ):
            c.execute(
                "INSERT INTO inv.resources VALUES(%s,%s,%s,%s,%s,%s)",
                (a.e.tenant, resource, b.e.node, kind, amount, amount),
            )
        c.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, b.e.node),
        )
    start(b)
    try:
        with psycopg.connect(a.e.owner) as c:
            provision_channel(
                c,
                b.node,
                epoch=b.e.epoch,
                endpoint=b.endpoint,
                certificate_der=b.server_cert.der,
                expected_version=0,
            )
        b.runtime = RestrictedWorkspaceRuntime(
            a.e.db,
            profile=b.profile,
            node=b.node,
            resources={"cpu": b.e.resource, "memory": b.memory},
            signing_key=b.key,
            policy_version="model-retry:1",
            client=a.client,
        )
        yield b
    finally:
        if b.daemon.poll() is None:
            b.daemon.terminate()
            b.daemon.communicate(timeout=12)


@pytest.fixture
def model_node(first, tmp_path, model_extra):
    a = first
    a.root = tmp_path / "model-source"
    a.root.mkdir(mode=0o700)
    weights = b"[2,1]"
    (a.root / "data.bin").write_bytes(weights)
    a.contribution = new_id("stc")
    a.principal, a.user = register_owner(a.e, a.contribution, a.root)
    with psycopg.connect(a.e.owner) as c:
        location = c.execute(
            "UPDATE public.data_locations SET byte_size=%s,checksum_sha256=%s WHERE contribution_id=%s RETURNING location_id",
            (len(weights), hashlib.sha256(weights).hexdigest(), a.contribution),
        ).fetchone()[0]
        c.execute(
            "INSERT INTO inv.project_resource_limits(tenant_id,project_id,cpu_millis,memory_bytes) VALUES(%s,%s,1000,268435456)",
            (a.e.tenant, a.e.project),
        )
    a.body = model_body(a.e.node, [location], [weights])
    a.body["format"] = "json-linear-v1"
    roots = [RootBinding(a.e.node, a.contribution, 1, ReadRoot(a.root))]
    import_allocations = [Allocation(a.e.resource, 1)]
    a.extra_node = model_extra
    if model_extra is not None:
        b = model_extra
        second_root = b.path / "model-source"
        second_root.mkdir(mode=0o700)
        (second_root / "data.bin").write_bytes(weights)
        contribution, location = new_id("stc"), new_id("dtl")
        with psycopg.connect(a.e.owner) as c:
            c.execute(
                "INSERT INTO public.nodes(node_id,tenant_id,hostname,os_type,os_version,agent_version,status,enrolled_at,heartbeat_sequence,version) VALUES(%s,%s,'replacement','linux','test','test','active',now(),0,1)",
                (b.e.node, a.e.tenant),
            )
            c.execute(
                "INSERT INTO public.storage_contributions(contribution_id,tenant_id,node_id,declared_path,normalized_path,mode,status,registered_by_user_id) VALUES(%s,%s,%s,%s,%s,'read_only','active',%s)",
                (contribution, a.e.tenant, b.e.node, str(second_root), str(second_root), a.user),
            )
            c.execute(
                "INSERT INTO public.data_locations(location_id,tenant_id,contribution_id,uri,kind,relative_path,byte_size,checksum_sha256) VALUES(%s,%s,%s,'file:replacement/data.bin','dataset','data.bin',%s,%s)",
                (
                    location,
                    a.e.tenant,
                    contribution,
                    len(weights),
                    hashlib.sha256(weights).hexdigest(),
                ),
            )
        roots.append(RootBinding(b.e.node, contribution, 1, ReadRoot(second_root)))
        a.body["replicas"].append(
            {
                "shardIndex": 0,
                "locationId": location,
                "locationVersion": 1,
                "nodeId": b.e.node,
                "state": "verified",
            }
        )
        import_allocations.append(Allocation(b.e.resource, 1))
        NodeObservation(a.e.db, a.client).poll(b.node)
    a.verifier = ConfiguredModelVerifier(roots)
    NodeObservation(a.e.db, a.client).poll(a.node)
    # Import worker fixture owns this logical lease; it has no Node process claim.
    imported = a.e.runs.create(a.e.tenant, a.e.project)
    for state in ("validated", "planned"):
        imported = a.e.runs.transition(
            a.e.tenant, imported["runId"], state, expected_version=imported["version"]
        )
    import_leases = a.e.leases.reserve(
        a.e.tenant,
        a.e.project,
        imported["runId"],
        sorted(import_allocations),
        key="import",
        ttl_seconds=300,
    )
    proofs = {lease["leaseId"]: lease["fencingToken"] for lease in import_leases}
    for state in ("scheduled", "running"):
        imported = a.e.runs.transition(
            a.e.tenant,
            imported["runId"],
            state,
            expected_version=imported["version"],
            proofs=proofs,
        )
    ModelManifestStore(a.e.db, a.verifier).commit(
        a.principal, a.e.project, imported["runId"], a.body, proofs, key="model-import"
    )
    for lease in import_leases:
        a.e.leases.release(
            a.e.tenant,
            lease["leaseId"],
            lease["fencingToken"],
            authenticated_node_id=(
                a.e.node if lease["resourceId"] == a.e.resource else model_extra.e.node
            ),
            stop_receipt=str(uuid4()),
        )
    for state in ("validated", "planned"):
        a.run = a.e.runs.transition(
            a.e.tenant, a.run["runId"], state, expected_version=a.run["version"]
        )
    NodeObservation(a.e.db, a.client).poll_resources(a.node)
    observed = ModelLocalityStore(a.e.db, a.verifier).observe(
        a.principal, a.e.project, a.body["modelId"], a.body["version"]
    )
    placement = PlacementStore(a.e.db).reserve(
        a.principal,
        a.e.project,
        a.run["runId"],
        Request(500, 67108864, required_bytes=len(weights), max_host_load=Decimal(1)),
        key="model-place",
        policy_version="model-node:1",
        model_observation=observed,
        node_ids=[a.e.node],
    )
    a.leases = placement["leases"]
    a.proofs = {l["leaseId"]: l["fencingToken"] for l in a.leases}
    a.workload["command"] = [
        "/usr/local/bin/python3",
        "-B",
        "-c",
        "import json,pathlib; w=json.loads(pathlib.Path('model/0000.bin').read_text()); result=w[0]*3+w[1]; pathlib.Path('outputs').mkdir(); pathlib.Path('outputs/prediction.json').write_text(json.dumps({'prediction':result})); print(result)",
    ]
    actors(a, a)
    a.model_runtime = ModelRuntimeStore(a.e.db, a.verifier)
    return a


def enqueue_model(a, *, short_validity=False):
    result = a.model_runtime.prepare(
        a.principal,
        a.e.project,
        a.run["runId"],
        a.workload,
        a.proofs,
        key="runtime:" + a.run["runId"],
    )
    a.workload = result["workload"]
    a.input_id = a.workload["modelInput"]["inputId"]
    a.policy["actionDigest"] = action_digest(a.workload)
    a.policy["decisionId"] = str(uuid4())
    row = request_approval(a, key="model-approval:" + a.run["runId"])
    for actor in ("alice", "bob"):
        row = decide(
            a, row, actor, challenge(a, row, actor), key="model-vote:" + a.run["runId"] + actor
        )
    a.command = dispatch(a, row, key="model-dispatch:" + a.run["runId"])
    a.gateway = ToolGateway(a.e.db, a.profile)
    options = inputs(a)
    options["runtime"] = a.runtime.observe()
    if short_validity:
        options["runtime"] = replace(
            options["runtime"], expires_at=datetime.now(timezone.utc) + timedelta(seconds=2)
        )
    claimed = a.gateway.claim(
        a.node, a.command, a.workload, a.proofs, queue_signing_key=a.key, **options
    )
    assert not claimed.may_start


def run(a):
    return a.e.runs.get(a.e.tenant, a.run["runId"])


def prediction(a):
    raw = a.storage.restore(a.e.tenant, a.e.project, a.run["runId"], 1, a.input_id)
    _, files = decode_snapshot(raw, a.workspace_id)
    assert files["model/0000.bin"] == b"[2,1]"
    return json.loads(files["outputs/prediction.json"])["prediction"]


def record(a, case):
    directory = os.getenv("INV_TEST_EVIDENCE_DIR")
    if not directory:
        return
    with a.e.db.transaction(a.e.tenant) as c:
        rows = c.execute(
            "SELECT content_hash,peer_sha256,envelope FROM inv.node_stop_receipts ORDER BY recorded_at"
        ).fetchall()
    receipts = []
    for row in rows:
        receipt = row["envelope"]
        receipts.append(
            {
                **{
                    k: receipt[k]
                    for k in (
                        "commandId",
                        "nodeId",
                        "recoveryEpoch",
                        "processStarted",
                        "exitCode",
                        "reason",
                    )
                },
                "receiptHash": row["content_hash"],
                "authenticatedPeerSHA256": row["peer_sha256"],
                "outputHash": receipt.get("output", {}).get("sha256"),
            }
        )
    proof = {
        "case": case,
        "scope": "isolated-Go-mTLS-Docker; not physical-PC acceptance",
        "modelInput": a.workload["modelInput"],
        "run": run(a),
        "receipts": receipts,
        "executionAttempts": count(a, "execution_attempts"),
        "resultCompletions": count(a, "result_completions"),
        "activeLeases": active(a),
    }
    Path(directory, "model-" + case + ".json").write_text(
        json.dumps(proof, sort_keys=True, indent=2) + "\n"
    )


def test_real_model_input_execution_and_durable_duplicate(model_node):
    a = model_node
    enqueue_model(a)
    (a.root / "data.bin").write_bytes(b"[9,9]")
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    assert run(a)["state"] == "succeeded" and prediction(a) == 7
    assert worker.once(a.e.tenant) == "idle"
    assert count(a, "execution_attempts") == 1 and count(a, "result_completions") == 1
    assert active(a) == 0 and container(a) is None
    record(a, "single")


def test_model_output_recovers_after_node_shutdown_without_reexecution(model_node):
    a = model_node
    enqueue_model(a)
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant) == "stopped"
    assert run(a)["state"] == "running"
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda _: OutputIngestion(a.e.db, a.storage.provider).once(
                    a.e.tenant, command_id=a.command["commandId"]
                ),
                range(3),
            )
        )
    assert run(a)["state"] == "succeeded" and prediction(a) == 7
    assert count(a, "execution_attempts") == 1 and count(a, "result_completions") == 1
    assert active(a) == 0 and container(a) is None
    record(a, "output-recovery")


@pytest.mark.parametrize("fault", ["cancel", "stale", "node-loss"])
def test_model_cannot_start_with_cancelled_expired_or_lost_authority(model_node, fault):
    a = model_node
    enqueue_model(a, short_validity=fault == "stale")
    if fault == "stale":
        time.sleep(3)
    with psycopg.connect(a.e.owner) as c:
        if fault == "cancel":
            c.execute(
                "UPDATE inv.runs SET state='cancelled',version=version+1 WHERE run_id=%s",
                (a.run["runId"],),
            )
        elif fault == "node-loss":
            c.execute("UPDATE inv.nodes SET status='offline' WHERE node_id=%s", (a.e.node,))
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    with a.e.db.transaction(a.e.tenant) as c:
        receipt = c.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.command["commandId"],),
        ).fetchone()["envelope"]
    assert receipt["processStarted"] is False
    assert count(a, "execution_attempts") == 0 and count(a, "result_completions") == 0
    assert active(a) == 0 and container(a) is None
    record(a, fault)


@pytest.mark.parametrize("model_extra", [True], indirect=True)
def test_failed_model_retries_on_second_real_node_with_new_approval(model_node):
    a = model_node
    b = a.extra_node
    successful_command = list(a.workload["command"])
    a.workload["command"] = ["/usr/local/bin/python3", "-B", "-c", "raise SystemExit(7)"]
    enqueue_model(a)
    original_run = a.run["runId"]
    original_command = a.command["commandId"]
    original_fences = set(a.proofs.values())
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert run(a)["state"] == "failed" and active(a) == 0
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    with psycopg.connect(a.e.owner) as c:
        c.execute("UPDATE inv.nodes SET status='offline' WHERE node_id=%s", (a.e.node,))
    NodeObservation(a.e.db, a.client).poll_resources(b.node)
    recovery = ModelRetryStore(a.e.db, a.verifier).prepare(
        a.principal,
        a.e.project,
        original_run,
        Request(500, 67108864, required_bytes=a.body["totalBytes"], max_host_load=Decimal(1)),
        key="retry-on-replacement",
        policy_version="model-retry:1",
        node_ids=[b.e.node],
    )
    assert recovery["reservation"]["placement"]["nodeId"] == b.e.node
    assert recovery["requiresFrozenInputAndApproval"] and recovery["generation"] == 2
    a.run = recovery["run"]
    a.leases = recovery["reservation"]["leases"]
    a.proofs = {l["leaseId"]: l["fencingToken"] for l in a.leases}
    assert not original_fences & set(a.proofs.values())
    a.workload = deepcopy(a.workload)
    a.workload.pop("modelInput")
    a.workload["targetNodeId"] = b.e.node
    a.workload["command"] = successful_command
    a.node, a.profile, a.key, a.runtime = b.node, b.profile, b.key, b.runtime
    enqueue_model(a)
    assert a.command["commandId"] != original_command
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert run(a)["state"] == "succeeded" and prediction(a) == 7
    assert a.e.runs.get(a.e.tenant, original_run)["state"] == "failed"
    assert (
        count(a, "execution_attempts") == 2
        and count(a, "result_completions") == 1
        and active(a) == 0
    )

    record(a, "replacement-node")
