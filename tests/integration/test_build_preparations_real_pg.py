"""Card 247 real PostgreSQL request -> approval -> admission -> dispatch path."""

from __future__ import annotations

import base64
from datetime import timedelta
from uuid import uuid4

import psycopg
import pytest

from inv.approvals import ApprovalStore, Principal
from inv.build_execution import BuildExecutionResult, PRODUCT_ENABLE_SETTING
from inv.build_execution_worker import BuildExecutionIntentQueue, BuildExecutionWorker
from inv.build_preparations import BuildPreparationService
from inv.build_product_runtime import BuildExecutionAdmissionStore, BuildProductRuntime
from inv.ids import new_id
from inv.object_store import registered_provider
from inv.policy import action_digest
from test_workspace_api import workspace_http

pytestmark = pytest.mark.postgres


class _MeasuredService:
    def __init__(self):
        self.capsules = []
        self.dispatches = 0

    def bind_source_capsule(self, locator, digest):
        assert locator.startswith("obj-") and len(digest) == 64
        self.capsules.append((locator, digest))

    def execute(self, *_args, **_kwargs):
        self.dispatches += 1
        return BuildExecutionResult(new_id("evd"), "a" * 64, True, True)


def test_build_request_to_worker_is_one_server_owned_chain(workspace_http, monkeypatch):
    a = workspace_http
    source_url = a.url + "/checkouts/" + a.checkout_id + "/files"
    original = a.http.get(source_url, headers=a.headers()).json()
    file = next(item for item in original["snapshot"]["files"] if item["path"] == "src/main.py")
    edited = a.http.post(
        source_url,
        json={
            "expectedRevision": original["revision"],
            "expectedSha256": original["sha256"],
            "changes": [{
                "path": "src/main.py", "expectedSha256": file["sha256"],
                "executable": False,
                "dataBase64": base64.b64encode(b"print('build capsule')\n").decode(),
            }],
        },
        headers=a.headers(key="build-source-edit"),
    )
    assert edited.status_code == 200

    build_run = a.e.runs.create(a.e.tenant, a.e.project)
    build_run = a.e.runs.transition(a.e.tenant, build_run["runId"], "validated", expected_version=1)
    build_run = a.e.runs.transition(
        a.e.tenant, build_run["runId"], "planned", expected_version=build_run["version"]
    )
    requester = Principal(a.e.tenant, a.jwt.subject("requester"))
    approvers = [Principal(a.e.tenant, a.jwt.subject(name)) for name in ("alice", "bob")]
    profile_id = new_id("bpp")
    resource_id = new_id("res")
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            """INSERT INTO inv.build_policy_profiles(
            tenant_id,profile_id,version,project_ids,context_path,dockerfile_path,
            target_platform,target_stage,network_policy_id,cache_policy_id,
            secret_aliases,timeout_seconds)
            VALUES(%s,%s,1,%s,'src','Dockerfile','linux/amd64','runtime','none',
                   'cachepol_s08-default','{}',300)""",
            (a.e.tenant, profile_id, [a.e.project]),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',10,10)",
            (a.e.tenant, resource_id, a.e.node),
        )
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )

    evidence_id = new_id("evd")

    def plan_factory(conn, principal, preparation, request, decision):
        lease_id = new_id("lse")
        lease = conn.execute(
            """INSERT INTO inv.resource_leases(
            tenant_id,project_id,run_id,resource_id,lease_id,amount,expires_at,recovery_epoch)
            VALUES(%s,%s,%s,%s,%s,1,clock_timestamp()+interval '4 minutes',%s)
            RETURNING fencing_token,expires_at""",
            (a.e.tenant, a.e.project, build_run["runId"], resource_id, lease_id, a.e.epoch),
        ).fetchone()
        plan = {
            "apiVersion": "inv.saintvision.ai/v1alpha1", "kind": "BuildPlan",
            "tenantId": a.e.tenant, "projectId": a.e.project,
            "workspaceId": request["workspaceId"], "traceId": "1" * 32,
            "requestDigest": action_digest(request), "actionDigest": decision["actionDigest"],
            "policyDecisionId": decision["decisionId"], "policyVersion": "s08-build-pdp-v1",
            "policyExpiresAt": decision["expiresAt"], "buildSessionId": str(uuid4()),
            "builderInstanceId": "hosted-build-fixture", "builderProfileId": "rootless-v1",
            "builderObservationDigest": "b" * 64, "recoveryEpoch": 1,
            "rootless": True, "privileged": False, "hostAccess": False,
            "networkMode": "none", "networkPolicyId": "none",
            "egressAllowlistDigest": "0" * 64, "devices": [], "binds": [],
            "budget": {"cpuMillis": 1000, "memoryBytes": 1048576, "storageBytes": 1048576},
            "lease": {"leaseId": lease_id, "resourceId": resource_id,
                      "fencingToken": f"{a.e.epoch}:{lease['fencing_token']}",
                      "expiresAt": lease["expires_at"].isoformat()},
            "cacheNamespaceDigest": "c" * 64, "secretRefsDigest": "d" * 64,
            "resolvedBaseImageDigests": ["sha256:" + "e" * 64],
        }
        return plan, evidence_id

    service = BuildPreparationService(
        a.e.db, registered_provider(a.storage.provider), plan_factory=plan_factory
    )
    prepared = service.prepare(
        requester, a.e.project, build_run["runId"],
        {"checkoutId": a.checkout_id, "buildPolicyProfileId": profile_id,
         "expectedRunVersion": build_run["version"], "requestedTarget": "image"},
        key="build-prepare",
    )
    approvals = ApprovalStore(a.e.db)
    review = approvals.review(approvers[0], a.e.project, prepared["approvalId"])
    assert review["workload"]["kind"] == "build" and "contextPath" not in review["workload"]
    row = review["approval"]
    for index, actor in enumerate(approvers):
        challenge = approvals.challenge(actor, a.e.project, row["approvalId"])
        row = approvals.decide(
            actor, a.e.project, row["approvalId"], "approve", challenge["nonce"],
            action_digest=row["actionDigest"], key=f"build-vote-{index}",
        )
    monkeypatch.setenv(PRODUCT_ENABLE_SETTING, "1")
    service.enqueue(
        requester, a.e.project, build_run["runId"], prepared["buildId"],
        {"approvalId": prepared["approvalId"], "expectedRunVersion": row["runVersion"]},
        key="build-enqueue",
    )
    measured = _MeasuredService()
    runtime = BuildProductRuntime(
        BuildExecutionAdmissionStore(a.e.db),
        BuildExecutionWorker(
            BuildExecutionIntentQueue(a.e.db), measured,
            environment={PRODUCT_ENABLE_SETTING: "1"},
        ),
        environment={PRODUCT_ENABLE_SETTING: "1"},
    )
    runtime.once(a.e.tenant)
    assert measured.dispatches == 1 and len(measured.capsules) == 1
    with a.e.db.transaction(a.e.tenant) as conn:
        counts = conn.execute(
            """SELECT
              (SELECT count(*) FROM inv.build_preparations WHERE run_id=%s) AS preparations,
              (SELECT count(*) FROM inv.build_execution_admissions WHERE run_id=%s) AS admissions,
              (SELECT count(*) FROM inv.build_execution_intents WHERE run_id=%s) AS intents""",
            (build_run["runId"], build_run["runId"], build_run["runId"]),
        ).fetchone()
    assert counts == {"preparations": 1, "admissions": 1, "intents": 1}
