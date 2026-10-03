"""Card 247 real PostgreSQL request -> approval -> admission -> dispatch path."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from itertools import product
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
from inv.errors import DomainError
from inv.ids import new_id
from inv.object_store import registered_provider
from inv.policy import action_digest
from test_approvals import approval  # noqa: F401 - registers node runtime fixture dependency
from test_node_delivery import remote  # noqa: F401 - registers workspace fixture dependency
from test_node_runtime import node_runtime  # noqa: F401 - registers remote fixture dependency
from test_snapshots import storage  # noqa: F401 - registers workspace fixture dependency
from test_workspace_api import workspace_http

pytestmark = pytest.mark.postgres
BASE_IMAGE_DIGEST = "sha256:" + "1" * 64


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


def _setup_prepared_build(
    workspace_http,
    *,
    key="build-prepare",
    profile_budget=(10, 1048576, 1048576),
    profile_digest=BASE_IMAGE_DIGEST,
    profile_drift=None,
):
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
                 "dataBase64": base64.b64encode(
                     ("FROM saintvision.invalid/base@" + BASE_IMAGE_DIGEST + " AS runtime\n").encode()
                 ).decode()},
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
            cache_mode,secret_aliases,timeout_seconds,budget_cpu_millis,
            budget_memory_bytes,budget_storage_bytes,base_image_digests)
            VALUES(%s,%s,1,%s,'src','src/Dockerfile','linux/amd64','runtime','none',
                   'cachepol_s08-default','read-only','{}',300,%s,%s,%s,%s)""",
            (
                a.e.tenant,
                profile_id,
                [a.e.project],
                *profile_budget,
                [profile_digest] if all(value is not None for value in profile_budget) else None,
            ),
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

    capsule_store = registered_provider(a.storage.provider)
    if profile_drift is not None:
        drift_column, drift_value = profile_drift
        assert drift_column in {"budget_cpu_millis", "base_image_digests"}

        class _DriftingCapsuleStore:
            def __init__(self, delegate):
                self.delegate = delegate
                self.changed = False

            def __getattr__(self, name):
                return getattr(self.delegate, name)

            def put(self, locator, raw, expected_sha256):
                result = self.delegate.put(locator, raw, expected_sha256)
                if not self.changed:
                    self.changed = True
                    with psycopg.connect(a.e.owner) as conn:
                        conn.execute("SET LOCAL session_replication_role=replica")
                        conn.execute(
                            f"UPDATE inv.build_policy_profiles SET {drift_column}=%s "
                            "WHERE profile_id=%s AND version=1",
                            (drift_value, profile_id),
                        )
                return result

        capsule_store = _DriftingCapsuleStore(capsule_store)

    service = BuildPreparationService(a.e.db, capsule_store, plan_factory=authority)
    prepared = service.prepare(
        requester, a.e.project, build_run["runId"],
        {"checkoutId": a.checkout_id, "buildPolicyProfileId": profile_id,
         "expectedRunVersion": build_run["version"], "requestedTarget": "image"},
        key=key,
    )
    return {
        "a": a,
        "source_url": source_url,
        "build_run": build_run,
        "requester": requester,
        "approvers": approvers,
        "profile_id": profile_id,
        "service": service,
        "prepared": prepared,
        "prepare_input": {
            "checkoutId": a.checkout_id,
            "buildPolicyProfileId": profile_id,
            "expectedRunVersion": build_run["version"],
            "requestedTarget": "image",
        },
    }


def _approve_prepared_build(context):
    a = context["a"]
    prepared = context["prepared"]
    approvers = context["approvers"]
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
    return row


def test_build_request_to_worker_is_one_server_owned_chain(workspace_http, monkeypatch):
    context = _setup_prepared_build(workspace_http)
    a = context["a"]
    build_run = context["build_run"]
    requester = context["requester"]
    service = context["service"]
    prepared = context["prepared"]
    row = _approve_prepared_build(context)
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
        plan = conn.execute(
            "SELECT plan FROM inv.build_execution_admissions WHERE run_id=%s",
            (build_run["runId"],),
        ).fetchone()["plan"]
        limits = conn.execute(
            "SELECT cpu_millis,memory_bytes FROM inv.project_resource_limits WHERE project_id=%s",
            (a.e.project,),
        ).fetchone()
        storage = conn.execute(
            "SELECT quota_bytes FROM inv.storage_budgets WHERE project_id=%s",
            (a.e.project,),
        ).fetchone()
    assert counts == {"preparations": 1, "admissions": 1, "intents": 1}
    assert plan["budget"] == {
        "cpuMillis": 10,
        "memoryBytes": 1048576,
        "storageBytes": 1048576,
    }
    assert plan["budget"]["cpuMillis"] <= limits["cpu_millis"]
    assert plan["budget"]["memoryBytes"] <= limits["memory_bytes"]
    assert plan["budget"]["storageBytes"] <= storage["quota_bytes"]
    assert plan["resolvedBaseImageDigests"] == [BASE_IMAGE_DIGEST]


def test_missing_positive_storage_policy_fails_before_admission(workspace_http, monkeypatch):
    context = _setup_prepared_build(workspace_http)
    a, prepared = context["a"], context["prepared"]
    row = _approve_prepared_build(context)
    with psycopg.connect(a.e.owner) as conn:
        conn.execute(
            "UPDATE inv.storage_budgets SET quota_bytes=0 WHERE tenant_id=%s AND project_id=%s",
            (a.e.tenant, a.e.project),
        )
    monkeypatch.setenv(PRODUCT_ENABLE_SETTING, "1")
    with pytest.raises(DomainError) as refused:
        context["service"].enqueue(
            context["requester"],
            a.e.project,
            context["build_run"]["runId"],
            prepared["buildId"],
            {"approvalId": prepared["approvalId"], "expectedRunVersion": row["runVersion"]},
            key="build-enqueue-no-storage-policy",
        )
    assert (refused.value.code, refused.value.status, refused.value.retryable) == (
        "RES-0006",
        503,
        True,
    )
    with a.e.db.transaction(a.e.tenant) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM inv.build_execution_admissions WHERE run_id=%s",
            (context["build_run"]["runId"],),
        ).fetchone()["n"] == 0


def test_pre_0063_profile_without_budget_or_base_pin_fails_closed_during_prepare(
    workspace_http,
):
    with pytest.raises(DomainError) as refused:
        _setup_prepared_build(workspace_http, profile_budget=(None, None, None))
    assert (refused.value.code, refused.value.status, refused.value.retryable) == (
        "RES-0006",
        503,
        True,
    )


@pytest.mark.parametrize("present", list(product((False, True), repeat=4)))
def test_0063_budget_constraint_is_all_or_none_for_every_null_combination(
    workspace_http, present
):
    a = workspace_http
    values = (
        10 if present[0] else None,
        1048576 if present[1] else None,
        1048576 if present[2] else None,
        [BASE_IMAGE_DIGEST] if present[3] else None,
    )
    statement = """INSERT INTO inv.build_policy_profiles(
        tenant_id,profile_id,version,project_ids,context_path,dockerfile_path,
        target_platform,target_stage,network_policy_id,cache_policy_id,
        cache_mode,secret_aliases,timeout_seconds,budget_cpu_millis,
        budget_memory_bytes,budget_storage_bytes,base_image_digests)
        VALUES(%s,%s,1,%s,'src','src/Dockerfile','linux/amd64','runtime','none',
               'cachepol-s08-constraint','read-only','{}',300,%s,%s,%s,%s)"""
    with psycopg.connect(a.e.owner) as conn:
        if all(present) or not any(present):
            conn.execute(
                statement,
                (a.e.tenant, new_id("bpp"), [a.e.project], *values),
            )
            conn.rollback()
        else:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(
                    statement,
                    (a.e.tenant, new_id("bpp"), [a.e.project], *values),
                )
            conn.rollback()


@pytest.mark.parametrize("budget", [(0, 1048576, 1048576), (-1, 1048576, 1048576)])
def test_0063_budget_constraint_rejects_non_positive_complete_budget(workspace_http, budget):
    a = workspace_http
    with psycopg.connect(a.e.owner) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                """INSERT INTO inv.build_policy_profiles(
                tenant_id,profile_id,version,project_ids,context_path,dockerfile_path,
                target_platform,target_stage,network_policy_id,cache_policy_id,
                cache_mode,secret_aliases,timeout_seconds,budget_cpu_millis,
                budget_memory_bytes,budget_storage_bytes,base_image_digests)
                VALUES(%s,%s,1,%s,'src','src/Dockerfile','linux/amd64','runtime','none',
                       'cachepol-s08-positive','read-only','{}',300,%s,%s,%s,%s)""",
                (a.e.tenant, new_id("bpp"), [a.e.project], *budget, [BASE_IMAGE_DIGEST]),
            )
        conn.rollback()


def test_profile_budget_above_project_ceiling_fails_before_admission(
    workspace_http, monkeypatch
):
    context = _setup_prepared_build(
        workspace_http, profile_budget=(11, 1048576, 1048576)
    )
    row = _approve_prepared_build(context)
    monkeypatch.setenv(PRODUCT_ENABLE_SETTING, "1")
    with pytest.raises(DomainError) as refused:
        context["service"].enqueue(
            context["requester"],
            context["a"].e.project,
            context["build_run"]["runId"],
            context["prepared"]["buildId"],
            {"approvalId": context["prepared"]["approvalId"],
             "expectedRunVersion": row["runVersion"]},
            key="build-enqueue-over-project-ceiling",
        )
    assert (refused.value.code, refused.value.status) == ("RES-0006", 503)
    with context["a"].e.db.transaction(context["a"].e.tenant) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM inv.build_execution_admissions WHERE run_id=%s",
            (context["build_run"]["runId"],),
        ).fetchone()["n"] == 0


def test_profile_base_pin_must_equal_the_immutable_snapshot(workspace_http):
    with pytest.raises(DomainError) as refused:
        _setup_prepared_build(
            workspace_http,
            profile_digest="sha256:" + "2" * 64,
        )
    assert (refused.value.code, refused.value.status) == ("VERIFY-0002", 422)


@pytest.mark.parametrize(
    "profile_drift",
    [
        ("base_image_digests", ["sha256:" + "2" * 64]),
        ("budget_cpu_millis", 9),
    ],
)
def test_final_prepare_transaction_rejects_profile_authority_drift(
    workspace_http, profile_drift
):
    with pytest.raises(DomainError) as refused:
        _setup_prepared_build(workspace_http, profile_drift=profile_drift)
    assert (refused.value.code, refused.value.status) == ("VERIFY-0002", 422)


def test_build_authority_rows_are_immutable_even_to_the_owner(workspace_http):
    context = _setup_prepared_build(workspace_http)
    a, prepared = context["a"], context["prepared"]
    statements = (
        (
            "UPDATE inv.build_policy_profiles SET timeout_seconds=301 WHERE profile_id=%s",
            (context["profile_id"],),
        ),
        (
            "DELETE FROM inv.build_policy_profiles WHERE profile_id=%s",
            (context["profile_id"],),
        ),
        (
            "UPDATE inv.build_preparations SET request_sha256=%s WHERE build_id=%s",
            ("f" * 64, prepared["buildId"]),
        ),
        (
            "DELETE FROM inv.build_preparations WHERE build_id=%s",
            (prepared["buildId"],),
        ),
    )
    with psycopg.connect(a.e.owner, autocommit=True) as conn:
        for statement, parameters in statements:
            with pytest.raises(psycopg.errors.CheckViolation):
                conn.execute(statement, parameters)


def test_prepare_rate_limit_is_enforced_before_repeated_failed_work(workspace_http):
    context = _setup_prepared_build(workspace_http, key="rate-1")
    a, service = context["a"], context["service"]
    for index in range(2, 6):
        with pytest.raises(DomainError) as refused:
            service.prepare(
                context["requester"],
                a.e.project,
                context["build_run"]["runId"],
                context["prepare_input"],
                key=f"rate-{index}",
            )
        assert refused.value.code != "RES-0007"
    with pytest.raises(DomainError) as exhausted:
        service.prepare(
            context["requester"],
            a.e.project,
            context["build_run"]["runId"],
            context["prepare_input"],
            key="rate-6",
        )
    assert (exhausted.value.code, exhausted.value.status, exhausted.value.retryable) == (
        "RES-0007",
        429,
        True,
    )


def test_source_drift_before_enqueue_expires_approval_without_admission(
    workspace_http, monkeypatch
):
    context = _setup_prepared_build(workspace_http)
    a, prepared = context["a"], context["prepared"]
    row = _approve_prepared_build(context)
    current = a.http.get(context["source_url"], headers=a.headers()).json()
    source = next(
        item for item in current["snapshot"]["files"] if item["path"] == "src/main.py"
    )
    changed = a.http.post(
        context["source_url"],
        json={
            "expectedRevision": current["revision"],
            "expectedSha256": current["sha256"],
            "changes": [
                {
                    "path": "src/main.py",
                    "expectedSha256": source["sha256"],
                    "executable": False,
                    "dataBase64": base64.b64encode(b"print('drift after quorum')\n").decode(),
                }
            ],
        },
        headers=a.headers(key="build-drift-after-quorum"),
    )
    assert changed.status_code == 200
    monkeypatch.setenv(PRODUCT_ENABLE_SETTING, "1")
    with pytest.raises(DomainError) as drifted:
        context["service"].enqueue(
            context["requester"],
            a.e.project,
            context["build_run"]["runId"],
            prepared["buildId"],
            {"approvalId": prepared["approvalId"], "expectedRunVersion": row["runVersion"]},
            key="build-enqueue-after-drift",
        )
    assert (drifted.value.code, drifted.value.status) == ("VERIFY-0002", 422)
    with a.e.db.transaction(a.e.tenant) as conn:
        observed = conn.execute(
            """SELECT a.status,r.state,
            (SELECT count(*) FROM inv.approval_audit x
             WHERE x.approval_id=a.approval_id AND x.phase='expired'
               AND x.actor_id='system:build-preparation-drift') AS terminal_audits,
            (SELECT count(*) FROM inv.build_execution_admissions x
             WHERE x.run_id=r.run_id) AS admissions
            FROM inv.approval_requests a JOIN inv.runs r USING(tenant_id,run_id)
            WHERE a.approval_id=%s""",
            (prepared["approvalId"],),
        ).fetchone()
    assert observed == {
        "status": "expired",
        "state": "failed",
        "terminal_audits": 1,
        "admissions": 0,
    }


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
