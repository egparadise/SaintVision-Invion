"""Card 247 real PostgreSQL request -> approval -> admission -> dispatch path."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from inv.approvals import ApprovalStore, Principal
from inv.build_execution import BuildExecutionResult, PRODUCT_ENABLE_SETTING
from inv.build_execution_worker import BuildExecutionIntentQueue, BuildExecutionWorker
from inv.build_governance import BuildProviderObservation
from inv.build_preparations import BuildPreparationService, ConfiguredBuildPlanAuthority
from inv.build_product_runtime import BuildExecutionAdmissionStore, BuildProductRuntime
from inv.buildkit_transport import MeasuredBuilder
from inv.ids import new_id
from inv.object_store import registered_provider
from inv.policy import action_digest
from test_node_delivery import remote  # noqa: F401 - registers workspace fixture dependency
from test_snapshots import storage  # noqa: F401 - registers workspace fixture dependency
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
            "changes": [
                {"path": "src/main.py", "expectedSha256": file["sha256"],
                 "executable": False,
                 "dataBase64": base64.b64encode(b"print('build capsule')\n").decode()},
                {"path": "src/Dockerfile", "expectedSha256": None,
                 "executable": False,
                 "dataBase64": base64.b64encode(b"FROM scratch\n").decode()},
            ],
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
            cache_mode,secret_aliases,timeout_seconds)
            VALUES(%s,%s,1,%s,'src','src/Dockerfile','linux/amd64','runtime','none',
                   'cachepol_s08-default','read-only','{}',300)""",
            (a.e.tenant, profile_id, [a.e.project]),
        )
        conn.execute(
            "INSERT INTO inv.resources VALUES(%s,%s,%s,'cpu',10,10)",
            (a.e.tenant, resource_id, a.e.node),
        )
        conn.execute(
            """INSERT INTO inv.project_resource_limits(
            tenant_id,project_id,cpu_millis,memory_bytes) VALUES(%s,%s,10,1048576)""",
            (a.e.tenant, a.e.project),
        )
        conn.execute(
            "UPDATE inv.nodes SET heartbeat_at=clock_timestamp() WHERE tenant_id=%s AND node_id=%s",
            (a.e.tenant, a.e.node),
        )

    measured_builder = MeasuredBuilder(
        BuildProviderObservation(
            "hosted-build-fixture", "rootless-v1", "b" * 64, 1,
            datetime.now(timezone.utc),
        ),
        "worker-1",
        ("linux/amd64",),
        "fixture",
        "fixture",
        {},
        {},
    )
    authority = ConfiguredBuildPlanAuthority.__new__(ConfiguredBuildPlanAuthority)
    authority.db = a.e.db
    authority.node_id = a.e.node
    authority.transport = type("MeasuredTransport", (), {"measure": lambda self: measured_builder})()

    service = BuildPreparationService(
        a.e.db, registered_provider(a.storage.provider), plan_factory=authority
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
    assert review["workload"]["cacheMode"] == "read-only"
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


def test_legacy_build_quorum_and_approved_drift_terminalize_without_invalid_transition(
    workspace_http,
):
    """Card 241 direct authority still votes; approved drift maps to expired."""

    a = workspace_http
    run = a.e.runs.create(a.e.tenant, a.e.project)
    run = a.e.runs.transition(a.e.tenant, run["runId"], "validated", expected_version=1)
    run = a.e.runs.transition(
        a.e.tenant, run["runId"], "planned", expected_version=run["version"]
    )
    requester = Principal(a.e.tenant, a.jwt.subject("requester"))
    approvers = [Principal(a.e.tenant, a.jwt.subject(name)) for name in ("alice", "bob")]
    request = {
        "apiVersion": "inv.saintvision.ai/v1alpha1",
        "kind": "BuildRequest",
        "tenantId": a.e.tenant,
        "projectId": a.e.project,
        "workspaceId": a.workspace_id,
        "sourceCommitSha": "a" * 40,
        "sourceTreeSha": "b" * 40,
        "contextPath": "src",
        "dockerfilePath": "src/Dockerfile",
        "targetPlatform": "linux/amd64",
        "targetStage": "runtime",
        "networkPolicyId": "none",
        "cachePolicyId": "cachepol_s08-default",
        "secretRefIds": [],
        "timeoutSeconds": 300,
    }
    policy = {
        "decisionId": str(uuid4()),
        "tenantId": a.e.tenant,
        "projectId": a.e.project,
        "subjectId": requester.subject_id,
        "effect": "require_approval",
        "riskLevel": "L2",
        "actionDigest": action_digest(
            {
                "action": "runtime.build.execute",
                "tenantId": a.e.tenant,
                "projectId": a.e.project,
                "workspaceId": a.workspace_id,
                "requestDigest": action_digest(request),
            }
        ),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "requiredApprovals": 2,
        "approvedBy": [],
    }
    approvals = ApprovalStore(a.e.db)
    row = approvals.request(
        requester,
        run["runId"],
        request,
        policy,
        policy_version="s08-build-pdp-v1",
        expected_version=run["version"],
        key="legacy-build-request",
    )
    for index, actor in enumerate(approvers):
        challenge = approvals.challenge(actor, a.e.project, row["approvalId"])
        row = approvals.decide(
            actor,
            a.e.project,
            row["approvalId"],
            "approve",
            challenge["nonce"],
            action_digest=row["actionDigest"],
            key=f"legacy-build-vote-{index}",
        )
    assert row["status"] == "approved"

    BuildPreparationService(a.e.db, registered_provider(a.storage.provider))._terminalize(
        requester, a.e.project, run["runId"], row["approvalId"], "VERIFY-0002"
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        observed = conn.execute(
            """SELECT a.status,r.state,
            (SELECT count(*) FROM inv.approval_audit x
             WHERE x.approval_id=a.approval_id AND x.phase='expired'
               AND x.actor_id='system:build-preparation-drift') AS terminal_audits,
            (SELECT count(*) FROM inv.outbox o WHERE o.run_id=r.run_id
               AND o.event_type='inv.build.preparation_terminalized') AS terminal_events
            FROM inv.approval_requests a JOIN inv.runs r USING(tenant_id,run_id)
            WHERE a.approval_id=%s""",
            (row["approvalId"],),
        ).fetchone()
    assert observed == {
        "status": "expired",
        "state": "failed",
        "terminal_audits": 1,
        "terminal_events": 1,
    }
