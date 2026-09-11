"""Actual first execution: authenticated draft -> approval -> attempt 1 -> files.

The Node has never executed a preparatory probe. DB/identity/CA are isolated test
fixtures; these are not production-user or two-physical-PC acceptance claims.
"""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest
from fastapi.testclient import TestClient
from inv.app import create_app
from inv.approvals import ApprovalStore, Principal, digest
from inv.dispatch import DeliveryWorker
from inv.errors import DomainError
from inv.ids import new_id
from inv.leases import LeaseStore
from inv.node_channels import provision_channel
from inv.output_ingestion import OutputIngestion, output_bytes
from inv.workspace_api import RestrictedWorkspaceRuntime, WorkspaceAPI
from inv.workspace_files import canonical, decode_snapshot, WorkingGenerations
from jwt_support import jwt_fixture
from tools.studio_templates import AI, GENERAL
from test_approvals import approval, count
from test_node_delivery import remote, start
from test_node_runtime import node_runtime, active, container
from test_snapshots import storage
from test_workspace_api import approve

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.skipif(sys.platform != "linux", reason="Linux first Workspace execution"),
]


def input_files(a, kind="python"):
    files = AI if kind == "ai" else GENERAL
    directories = set()
    rows = []
    for path, text in sorted(files.items()):
        parts = path.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
        raw = text.encode()
        rows.append(
            dict(
                path=path,
                executable=False,
                sha256=hashlib.sha256(raw).hexdigest(),
                sizeBytes=len(raw),
                dataBase64=base64.b64encode(raw).decode(),
            )
        )
    raw = canonical(
        dict(
            format="workspace-snapshot:1",
            workspaceId=a.workspace_id,
            directories=sorted(directories),
            files=rows,
        )
    )
    a.workload["command"] = [
        "/usr/local/bin/python3",
        "-B",
        "src/train.py" if kind == "ai" else "src/app.py",
    ]
    a.prepare_input["workload"] = deepcopy(a.workload)
    a.prepare_input["snapshotBase64"] = base64.b64encode(raw).decode()


@pytest.fixture
def first(remote, storage, tmp_path):
    a = remote
    assert count(a, "execution_attempts") == 0 and count(a, "tool_claims") == 0
    a.storage = storage
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    a.profile = replace(
        a.profile,
        version="restricted:python-first:1",
        images=frozenset({os.environ["INV_PYTHON_NODE_IMAGE"]}),
        executables=frozenset({"/usr/local/bin/python3"}),
    )
    for option, value in [
        ("--profile", a.profile.version),
        ("--image", next(iter(a.profile.images))),
        ("--executable", "/usr/local/bin/python3"),
    ]:
        a.args[a.args.index(option) + 1] = value
    a.workload.update(imageDigest=next(iter(a.profile.images)), timeoutSeconds=10)
    start(a)
    with psycopg.connect(a.e.owner) as conn:
        provision_channel(
            conn,
            a.node,
            epoch=a.e.epoch,
            endpoint=a.endpoint,
            certificate_der=a.server_cert.der,
            expected_version=1,
        )
    a.jwt = jwt_fixture(tmp_path, a.e.tenant)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO inv.project_nodes(tenant_id,project_id,node_id) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.node),
        )
        for actor in ("requester", "alice", "bob"):
            conn.execute(
                "INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve) VALUES(%s,%s,%s,%s,%s)",
                (
                    a.e.tenant,
                    a.e.project,
                    a.jwt.subject(actor),
                    actor == "requester",
                    actor != "requester",
                ),
            )
    a.runtime = RestrictedWorkspaceRuntime(
        a.e.db,
        profile=a.profile,
        node=a.node,
        resources={"cpu": a.e.resource, "memory": a.memory},
        signing_key=a.key,
        policy_version="first-workspace:1",
        client=a.client,
    )
    working_root = tmp_path / "working"
    working_root.mkdir(mode=0o700)
    a.working = WorkingGenerations(working_root)
    a.http = TestClient(
        create_app(a.e.db, a.jwt.auth, workspace=WorkspaceAPI(a.e.db, a.working, a.runtime)),
        raise_server_exceptions=False,
    )
    a.headers = lambda actor="requester", key="first-prepare": {
        "Authorization": "Bearer " + a.jwt.token(actor),
        "Idempotency-Key": key,
    }
    response = a.http.post(
        f"/v1/projects/{a.e.project}/runs", json={}, headers=a.headers(key="first-create")
    )
    assert response.status_code == 201, response.text
    a.run = response.json()
    assert a.run["state"] == "draft" and a.run["attempt"] == 0
    a.workspace_id = a.workload["workspaceId"]
    a.url = f"/v1/projects/{a.e.project}/runs/{a.run['runId']}"
    a.prepare_input = dict(
        startId=str(uuid4()),
        stepId="first-step",
        expectedVersion=a.run["version"],
        targetNodeId=a.e.node,
    )
    input_files(a)
    yield a
    a.http.close()


def prepare(a):
    response = a.http.post(a.url + "/start/prepare", json=a.prepare_input, headers=a.headers())
    assert response.status_code == 201, response.text
    a.prepared = response.json()
    a.enqueue_input = dict(
        startId=a.prepared["startId"],
        approvalId=a.prepared["approval"]["approvalId"],
        expectedVersion=a.prepared["run"]["version"],
    )
    return a.prepared


def enqueue(a):
    response = a.http.post(
        a.url + "/start/enqueue", json=a.enqueue_input, headers=a.headers(key="first-enqueue")
    )
    if response.status_code == 202:
        a.enqueued = response.json()
        a.command = {"commandId": a.enqueued["commandId"]}
    return response


def run(a):
    return a.http.get(a.url, headers=a.headers()).json()


def clean(a):
    assert (
        active(a) == 0
        and count(a, "execution_deliveries") == 0
        and count(a, "approval_dispatches") == 0
    )


def record(a, case, raw=None):
    folder = os.getenv("INV_TEST_EVIDENCE_DIR")
    if not folder:
        return
    with a.e.db.transaction(a.e.tenant) as conn:
        receipt = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.enqueued["commandId"],),
        ).fetchone()["envelope"]
        completion = conn.execute(
            "SELECT evidence_id FROM inv.result_completions WHERE command_id=%s",
            (a.enqueued["commandId"],),
        ).fetchone()
    value = dict(
        scope="first-workspace-synthetic-identity-local-node",
        case=case,
        run=run(a),
        startId=a.prepared["startId"],
        commandId=a.enqueued["commandId"],
        receiptId=receipt["receiptId"],
        evidenceId=completion["evidence_id"] if completion else None,
        exitCode=receipt["exitCode"],
        activeLeases=active(a),
        containerAbsent=container(a) is None,
    )
    if raw:
        _, files = decode_snapshot(raw, a.workspace_id)
        value["fileSHA256"] = {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}
        if "outputs/metrics.json" in files:
            value["metrics"] = json.loads(files["outputs/metrics.json"])
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / ("first-" + a.enqueued["commandId"] + ".json")).write_text(
        json.dumps(value, indent=2), encoding="utf-8"
    )


@pytest.mark.parametrize("kind", ["python", "ai"])
def test_first_attempt_executes_frozen_program_with_real_evidence(first, kind):
    a = first
    input_files(a, kind)
    with ThreadPoolExecutor(max_workers=3) as pool:
        prepared = list(pool.map(lambda _: prepare(a), range(3)))
    assert prepared[0] == prepared[1] == prepared[2]
    assert run(a)["state"] == "awaiting_approval" and run(a)["attempt"] == 0
    clean(a)
    assert count(a, "workspace_checkouts") == 0 and count(a, "workspace_resumptions") == 0
    status = a.http.get(
        a.url + "/starts/" + a.prepared["startId"], headers=a.headers("alice")
    ).json()
    assert status["frozenFiles"] and "dataBase64" not in str(status)
    assert enqueue(a).status_code == 403
    clean(a)
    approve(a)
    # Changing the local upload buffer cannot replace previously approved bytes.
    a.prepare_input["snapshotBase64"] = base64.b64encode(b"changed after approval").decode()
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: enqueue(a), range(3)))
    assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
    assert all(r.json() == responses[0].json() for r in responses)
    assert run(a)["state"] == "scheduled" and run(a)["attempt"] == 0 and active(a) == 2
    worker = DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider)
    assert worker.once(a.e.tenant) == "stopped"
    assert run(a)["state"] == "succeeded" and run(a)["attempt"] == 1
    assert (
        count(a, "execution_attempts") == 1
        and count(a, "result_completions") == 1
        and active(a) == 0
        and container(a) is None
    )
    raw = a.storage.restore(a.e.tenant, a.e.project, a.run["runId"], 1, "first-step")
    _, files = decode_snapshot(raw, a.workspace_id)
    assert (
        files["src/train.py" if kind == "ai" else "src/app.py"]
        == (AI if kind == "ai" else GENERAL)[
            "src/train.py" if kind == "ai" else "src/app.py"
        ].encode()
    )
    if kind == "ai":
        assert json.loads(files["outputs/metrics.json"])["evaluationMSE"] < 1e-8
    record(a, kind, raw)
    a.runtime.observe = lambda: pytest.fail("Accepted replay must not contact Node")
    assert enqueue(a).json() == responses[0].json() and worker.once(a.e.tenant) == "idle"


def test_first_queue_failure_rolls_back_approval_and_all_leases(first):
    a = first
    prepare(a)
    approve(a)
    key = a.runtime.signing_key
    a.runtime.signing_key = None
    assert enqueue(a).status_code == 403
    clean(a)
    assert run(a)["state"] == "awaiting_approval"
    a.runtime.signing_key = key
    assert enqueue(a).status_code == 202
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert run(a)["attempt"] == 1 and active(a) == 0


def test_first_cancel_before_enqueue_never_reserves_or_executes(first):
    a = first
    prepare(a)
    approve(a)
    response = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": run(a)["version"]},
        headers=a.headers(key="cancel-first"),
    )
    assert response.status_code == 200, response.text
    assert enqueue(a).status_code == 409
    clean(a)
    assert run(a)["state"] == "cancelled" and run(a)["attempt"] == 0


@pytest.mark.parametrize("change", ["grant", "node-membership", "capacity", "kill", "runtime"])
def test_first_admission_rechecks_authority_after_observation(first, change):
    a = first
    prepare(a)
    approve(a)
    observe = a.runtime.observe

    def changed():
        result = observe()
        with psycopg.connect(a.e.owner) as conn:
            if change == "grant":
                conn.execute(
                    "UPDATE inv.project_grants SET enabled=false WHERE tenant_id=%s AND subject_id=%s",
                    (a.e.tenant, a.jwt.subject("requester")),
                )
            elif change == "node-membership":
                conn.execute(
                    "UPDATE inv.project_nodes SET enabled=false WHERE tenant_id=%s", (a.e.tenant,)
                )
            elif change == "capacity":
                conn.execute("UPDATE inv.resources SET offered=0 WHERE tenant_id=%s", (a.e.tenant,))
            elif change == "kill":
                conn.execute(
                    "UPDATE inv.tenant_controls SET kill_switch=true,version=version+1 WHERE tenant_id=%s",
                    (a.e.tenant,),
                )
            else:
                a.runtime.policy_version = "changed-runtime:2"
        return result

    a.runtime.observe = changed
    response = enqueue(a)
    assert response.status_code in (403, 409), response.text
    clean(a)
    assert a.e.runs.get(a.e.tenant, a.run["runId"])["state"] == "awaiting_approval"


@pytest.mark.parametrize("bad", ["scope", "digest", "path", "base64", "authority"])
def test_first_input_rejects_invalid_snapshot_without_state_change(first, bad):
    a = first
    manifest = json.loads(base64.b64decode(a.prepare_input["snapshotBase64"]))
    if bad == "scope":
        manifest["workspaceId"] = new_id("wsp")
    elif bad == "digest":
        manifest["files"][0]["sha256"] = "0" * 64
    elif bad == "path":
        manifest["files"][0]["path"] = "../outside.py"
    elif bad == "authority":
        a.prepare_input["policy"] = {"effect": "allow"}
    a.prepare_input["snapshotBase64"] = (
        "!!!!" if bad == "base64" else base64.b64encode(canonical(manifest)).decode()
    )
    response = a.http.post(a.url + "/start/prepare", json=a.prepare_input, headers=a.headers())
    assert response.status_code == 422, response.text
    assert run(a)["state"] == "draft" and count(a, "workspace_starts") == 0
    clean(a)


def test_first_prepare_failure_preserves_draft_and_snapshot_idempotency(first):
    a = first
    a.prepare_input["workload"]["command"] = ["/unapproved"]
    response = a.http.post(a.url + "/start/prepare", json=a.prepare_input, headers=a.headers())
    assert response.status_code == 403, response.text
    assert run(a)["state"] == "draft" and count(a, "workspace_starts") == 0
    input_files(a)
    prepare(a)
    changed = deepcopy(a.prepare_input)
    changed["stepId"] = "other-step"
    response = a.http.post(a.url + "/start/prepare", json=changed, headers=a.headers())
    assert response.status_code == 409, response.text
    assert count(a, "workspace_starts") == 1 and run(a)["attempt"] == 0


def test_first_reservations_require_atomic_path(first):
    a = first
    prepare(a)
    with pytest.raises(DomainError, match="AUTH-0044"):
        LeaseStore(a.e.db).reserve(
            a.e.tenant,
            a.e.project,
            a.run["runId"],
            a.runtime.allocations(a.workload),
            key="outside-first",
        )
    clean(a)


def test_first_approval_cannot_be_consumed_outside_atomic_queue(first):
    a = first
    prepare(a)
    approve(a)
    with pytest.raises(DomainError, match="AUTH-0044"):
        ApprovalStore(a.e.db).dispatch(
            Principal(a.e.tenant, a.jwt.subject("requester")),
            a.e.project,
            a.prepared["approval"]["approvalId"],
            a.prepared["workload"],
            key="outside-dispatch",
        )
    clean(a)
    assert run(a)["state"] == "awaiting_approval"


def test_first_output_recovery_finishes_once_without_reexecution(first):
    a = first
    input_files(a, "ai")
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    assert DeliveryWorker(a.e.db, a.delivery).once(a.e.tenant) == "stopped"
    assert run(a)["state"] == "running" and active(a) == 0 and container(a) is None
    a.daemon.terminate()
    a.daemon.communicate(timeout=12)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(
            pool.map(
                lambda _: OutputIngestion(a.e.db, a.storage.provider).once(
                    a.e.tenant, command_id=a.enqueued["commandId"]
                ),
                range(3),
            )
        )
    assert count(a, "result_completions") == 1 and count(a, "execution_attempts") == 1
    assert run(a)["state"] == "succeeded" and run(a)["attempt"] == 1
    raw = a.storage.restore(a.e.tenant, a.e.project, a.run["runId"], 1, "first-step")
    assert (
        json.loads(decode_snapshot(raw, a.workspace_id)[1]["outputs/metrics.json"])["evaluationMSE"]
        < 1e-8
    )
    record(a, "output-recovery", raw)


def test_first_program_failure_has_no_success_evidence(first):
    a = first
    a.prepare_input["workload"]["command"] = ["/usr/local/bin/python3", "-c", "raise SystemExit(7)"]
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert run(a)["state"] == "failed" and run(a)["attempt"] == 1
    assert active(a) == 0 and container(a) is None and count(a, "result_completions") == 0
    record(a, "failure")


def test_first_queued_cancel_waits_for_actual_node_tombstone(first):
    a = first
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    response = a.http.post(
        a.url + "/cancel",
        json={"expectedVersion": run(a)["version"]},
        headers=a.headers(key="cancel-queued"),
    )
    assert response.status_code == 200, response.text
    assert active(a) == 2
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert (
        active(a) == 0
        and container(a) is None
        and run(a)["attempt"] == 0
        and run(a)["state"] == "cancelled"
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        r = conn.execute(
            "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
            (a.enqueued["commandId"],),
        ).fetchone()["envelope"]
        assert r["stopped"] and not r["processStarted"]
    assert count(a, "result_completions") == 0


def test_first_requested_node_is_explicit_and_never_substituted(first):
    a = first
    a.prepare_input["targetNodeId"] = new_id("nod")
    response = a.http.post(a.url + "/start/prepare", json=a.prepare_input, headers=a.headers())
    assert response.status_code == 403, response.text
    assert run(a)["state"] == "draft" and count(a, "workspace_starts") == 0


@pytest.fixture
def business_first(first):
    a = first
    a.users = {actor: new_id("usr") for actor in ("requester", "alice", "bob")}
    a.workload_id = new_id("wkl")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,%s)",
            (a.e.tenant, a.e.tenant, "Synthetic first"),
        )
        conn.execute(
            "INSERT INTO public.projects(tenant_id,project_id,code,display_name) VALUES(%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.e.project, "Synthetic first"),
        )
        for actor, user in a.users.items():
            conn.execute(
                "INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, user, actor, actor),
            )
            conn.execute(
                "INSERT INTO inv.business_subjects(tenant_id,subject_id,user_id) VALUES(%s,%s,%s)",
                (a.e.tenant, a.jwt.subject(actor), user),
            )
            conn.execute(
                "INSERT INTO public.project_members(tenant_id,project_id,user_id,role_code) VALUES(%s,%s,%s,%s)",
                (a.e.tenant, a.e.project, user, "operator" if actor == "requester" else "approver"),
            )
        conn.execute(
            "INSERT INTO public.workspaces(tenant_id,project_id,workspace_id,name,status,created_by_user_id) VALUES(%s,%s,%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.workspace_id, "Synthetic", "ready", a.users["requester"]),
        )
        conn.execute(
            "INSERT INTO public.workloads(tenant_id,project_id,workload_id,kind,objective,spec,spec_sha256,contract_version,created_by_user_id) VALUES(%s,%s,%s,'batch','Synthetic',%s,%s,'1.0.0',%s)",
            (
                a.e.tenant,
                a.e.project,
                a.workload_id,
                Jsonb(a.workload),
                digest(a.workload),
                a.users["requester"],
            ),
        )
        conn.execute(
            "INSERT INTO public.runs(tenant_id,run_id,workspace_id,workload_id,requested_by_user_id) VALUES(%s,%s,%s,%s,%s)",
            (a.e.tenant, a.run["runId"], a.workspace_id, a.workload_id, a.users["requester"]),
        )
        conn.execute(
            "INSERT INTO inv.business_projects(tenant_id,project_id) VALUES(%s,%s)",
            (a.e.tenant, a.e.project),
        )
        conn.execute(
            "INSERT INTO inv.business_runs(tenant_id,project_id,run_id,workspace_id) VALUES(%s,%s,%s,%s)",
            (a.e.tenant, a.e.project, a.run["runId"], a.workspace_id),
        )
    return a


def test_business_first_run_uses_current_public_identity_and_real_kernel(business_first):
    a = business_first
    prepare(a)
    approve(a)
    assert enqueue(a).status_code == 202
    assert (
        DeliveryWorker(a.e.db, a.delivery, output_provider=a.storage.provider).once(a.e.tenant)
        == "stopped"
    )
    assert run(a)["state"] == "succeeded" and run(a)["attempt"] == 1 and active(a) == 0
    with a.e.db.transaction(a.e.tenant) as conn:
        assert (
            conn.execute(
                "SELECT state FROM public.runs WHERE run_id=%s", (a.run["runId"],)
            ).fetchone()["state"]
            == "draft"
        )
        assert (
            conn.execute("SELECT count(*) AS n FROM public.workspace_edit_locks").fetchone()["n"]
            == 0
        )
    assert count(a, "workspace_resumptions") == 0


@pytest.mark.parametrize("change", ["member", "workload"])
def test_business_first_rechecks_revoked_or_changed_intent(business_first, change):
    a = business_first
    prepare(a)
    approve(a)
    observe = a.runtime.observe

    def changed():
        result = observe()
        with psycopg.connect(a.e.owner) as conn:
            if change == "member":
                conn.execute(
                    "DELETE FROM public.project_members WHERE tenant_id=%s AND user_id=%s",
                    (a.e.tenant, a.users["requester"]),
                )
            else:
                different = deepcopy(a.workload)
                different["command"] = ["/usr/local/bin/python3", "-c", "print(42)"]
                conn.execute(
                    "UPDATE public.workloads SET spec=%s,spec_sha256=%s WHERE tenant_id=%s AND workload_id=%s",
                    (Jsonb(different), digest(different), a.e.tenant, a.workload_id),
                )
        return result

    a.runtime.observe = changed
    response = enqueue(a)
    assert response.status_code == 403, response.text
    clean(a)


def test_business_project_cannot_fallback_to_unmapped_kernel_run(business_first):
    a = business_first
    other = a.http.post(
        f"/v1/projects/{a.e.project}/runs", json={}, headers=a.headers(key="unmapped-create")
    ).json()
    response = a.http.post(
        f"/v1/projects/{a.e.project}/runs/{other['runId']}/start/prepare",
        json=a.prepare_input,
        headers=a.headers(),
    )
    assert response.status_code == 404, response.text
    assert count(a, "workspace_starts") == 0
