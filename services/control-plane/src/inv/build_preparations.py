"""Public build prepare/enqueue boundary over server-owned build documents.

Only the four-field prepare input and two-field enqueue input cross HTTP.  Raw
BuildRequest/BuildPlan/PolicyDecision documents remain server-owned.  Product
dispatch is disabled unless ``INV_BUILDKIT_PRODUCT_ENABLED`` is exactly ``1``.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import hashlib
import os
from typing import Callable, Mapping
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from .approvals import ApprovalStore, Principal, digest
from .build_execution import PRODUCT_ENABLE_SETTING, PRODUCT_ENABLE_VALUE
from .build_governance import canonical_build_action
from .contracts import validate_contract
from .db import BoundDatabase
from .errors import DomainError
from .ids import new_id
from .policy import action_digest
from .runs import event
from .workspace_files import decode_snapshot

PREPARE_LIMITS = (("subject", "prepare", 5), ("project", "combined", 30),
                  ("tenant-project", "combined", 60))
ENQUEUE_LIMITS = (("subject", "enqueue", 10), ("project", "combined", 30),
                  ("tenant-project", "combined", 60))


def _sha1(kind: bytes, body: bytes) -> str:
    framed = kind + b" " + str(len(body)).encode("ascii") + b"\0" + body
    return hashlib.sha1(framed).hexdigest()


def _identity_decision(decision: Mapping) -> dict:
    result = deepcopy(dict(decision))
    result.pop("approvedBy", None)
    return result


class BuildPreparationService:
    """Coordinate source capture, approval quorum, and trusted admission creation."""

    def __init__(self, database, capsule_store, *, plan_factory: Callable | None = None):
        self.db = database
        self.capsule_store = capsule_store
        self.plan_factory = plan_factory

    def _reserve(self, principal, project_id, operation, key, payload, limits):
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise DomainError("VAL-0003", "Idempotency key is required", 422)
        request_hash = digest({"subject": principal.subject_id, "epoch": self.db.recovery_epoch,
                               "payload": payload})
        with self.db.transaction(principal.tenant_id) as conn:
            ApprovalStore(BoundDatabase(self.db, principal.tenant_id, conn))._grant(
                conn, project_id, principal.subject_id, "can_request"
            )
            conn.execute(
                """INSERT INTO inv.idempotency(tenant_id,project_id,operation,key,request_hash)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (principal.tenant_id, project_id, operation, key, request_hash),
            )
            ledger = conn.execute(
                """SELECT request_hash,response FROM inv.idempotency
                WHERE project_id=%s AND operation=%s AND key=%s FOR UPDATE""",
                (project_id, operation, key),
            ).fetchone()
            if not ledger or ledger["request_hash"] != request_hash:
                raise DomainError("IDEM-0001", "Idempotency key was already used", 409)
            if ledger["response"] is not None:
                return deepcopy(ledger["response"])
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            window = now.replace(second=0, microsecond=0)
            conn.execute(
                "DELETE FROM inv.build_preparation_rate_windows "
                "WHERE window_started_at < clock_timestamp() - interval '35 days'"
            )
            for scope, rate_operation, maximum in limits:
                subject = principal.subject_id if scope == "subject" else "*"
                count = conn.execute(
                    """INSERT INTO inv.build_preparation_rate_windows(
                    tenant_id,project_id,scope,subject_id,operation,window_started_at,count)
                    VALUES(%s,%s,%s,%s,%s,%s,1)
                    ON CONFLICT(tenant_id,project_id,scope,subject_id,operation,window_started_at)
                    DO UPDATE SET count=inv.build_preparation_rate_windows.count+1,
                                  updated_at=clock_timestamp()
                    RETURNING count""",
                    (principal.tenant_id, project_id, scope, subject, rate_operation, window),
                ).fetchone()["count"]
                if count > maximum:
                    raise DomainError("RES-0007", "Build request rate budget exceeded", 429, True)
            return None

    def _save_replay(self, conn, principal, project_id, operation, key, response):
        updated = conn.execute(
            """UPDATE inv.idempotency SET response=%s
            WHERE project_id=%s AND operation=%s AND key=%s AND response IS NULL""",
            (Jsonb(response), project_id, operation, key),
        ).rowcount
        if updated != 1:
            row = conn.execute(
                "SELECT response FROM inv.idempotency WHERE project_id=%s AND operation=%s AND key=%s",
                (project_id, operation, key),
            ).fetchone()
            if not row or row["response"] != response:
                raise DomainError("IDEM-0001", "Idempotency response differs", 409)

    def prepare(self, principal: Principal, project_id: str, run_id: str, data: Mapping, *, key: str):
        data = dict(data)
        validate_contract("BuildPreparationInput", data)
        replay = self._reserve(
            principal, project_id, "build.prepare", key,
            {"projectId": project_id, "runId": run_id, **data}, PREPARE_LIMITS,
        )
        if replay is not None:
            validate_contract("BuildPreparationView", replay)
            return replay

        # Short read transaction.  The immutable editor bytes are copied before
        # ObjectStore I/O; no DB lock is held during that I/O.
        with self.db.transaction(principal.tenant_id) as conn:
            approvals = ApprovalStore(BoundDatabase(self.db, principal.tenant_id, conn))
            approvals._grant(conn, project_id, principal.subject_id, "can_request")
            run = conn.execute(
                "SELECT * FROM inv.runs WHERE project_id=%s AND run_id=%s",
                (project_id, run_id),
            ).fetchone()
            checkout = conn.execute(
                """SELECT c.*,e.revision,e.content_hash,e.snapshot
                FROM inv.workspace_checkouts c JOIN LATERAL (
                  SELECT revision,content_hash,snapshot FROM inv.workspace_edits
                  WHERE checkout_id=c.checkout_id ORDER BY revision DESC LIMIT 1
                ) e ON true WHERE c.project_id=%s AND c.checkout_id=%s""",
                (project_id, UUID(data["checkoutId"])),
            ).fetchone()
            profile = conn.execute(
                """SELECT * FROM inv.build_policy_profiles
                WHERE profile_id=%s AND %s=ANY(project_ids)
                ORDER BY version DESC LIMIT 1""",
                (data["buildPolicyProfileId"], project_id),
            ).fetchone()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if not run or run["state"] != "planned" or run["version"] != data["expectedRunVersion"]:
            raise DomainError("GRAPH-0003", "Build preparation requires the current planned Run")
        if not checkout or not profile:
            raise DomainError("RES-0004", "Build preparation authority was not found", 404)
        raw = bytes(checkout["snapshot"])
        decode_snapshot(raw, checkout["workspace_id"])
        snapshot_sha = hashlib.sha256(raw).hexdigest()
        if snapshot_sha != checkout["content_hash"]:
            raise DomainError("VERIFY-0002", "Workspace snapshot digest differs", 422)
        capsule_sha = snapshot_sha
        locator = f"build-capsules/{principal.tenant_id}/{project_id}/{capsule_sha}"
        self.capsule_store.put(locator, raw, capsule_sha)

        request = {
            "apiVersion": "inv.saintvision.ai/v1alpha1", "kind": "BuildRequest",
            "tenantId": principal.tenant_id, "projectId": project_id,
            "workspaceId": checkout["workspace_id"],
            "sourceCommitSha": _sha1(b"commit", raw), "sourceTreeSha": _sha1(b"tree", raw),
            "contextPath": profile["context_path"],
            "dockerfilePath": profile["dockerfile_path"],
            "targetPlatform": profile["target_platform"],
            "targetStage": profile["target_stage"],
            "networkPolicyId": profile["network_policy_id"],
            "cachePolicyId": profile["cache_policy_id"],
            "secretRefIds": list(profile["secret_aliases"]),
            "timeoutSeconds": profile["timeout_seconds"],
        }
        validate_contract("BuildRequest", request)
        action_hash = action_digest(canonical_build_action(request))
        expires = now + timedelta(seconds=600)
        policy = {
            "decisionId": str(uuid4()), "tenantId": principal.tenant_id,
            "projectId": project_id, "subjectId": principal.subject_id,
            "effect": "require_approval", "riskLevel": "L2", "actionDigest": action_hash,
            "expiresAt": expires.isoformat(), "requiredApprovals": 2, "approvedBy": [],
        }
        validate_contract("PolicyDecision", policy)
        request_sha = digest(request)
        decision_sha = digest(policy)
        identity_sha = digest(_identity_decision(policy))
        build_id = new_id("bld")

        with self.db.transaction(principal.tenant_id) as conn:
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            approval = ApprovalStore(bound).request(
                principal, run_id, request, policy, policy_version="s08-build-pdp-v1",
                expected_version=data["expectedRunVersion"], key=f"build:{key}",
            )
            current = conn.execute(
                """SELECT revision,content_hash FROM inv.workspace_edits
                WHERE checkout_id=%s ORDER BY revision DESC LIMIT 1 FOR SHARE""",
                (UUID(data["checkoutId"]),),
            ).fetchone()
            locked_profile = conn.execute(
                """SELECT * FROM inv.build_policy_profiles
                WHERE profile_id=%s AND version=%s FOR SHARE""",
                (profile["profile_id"], profile["version"]),
            ).fetchone()
            if (not current or current["revision"] != checkout["revision"]
                    or current["content_hash"] != snapshot_sha or not locked_profile
                    or project_id not in locked_profile["project_ids"]):
                raise DomainError("VERIFY-0002", "Build source or policy profile drifted", 422)
            conn.execute(
                """INSERT INTO inv.build_preparations(
                tenant_id,project_id,run_id,build_id,source_run_id,checkout_id,source_revision,
                source_snapshot_sha256,source_capsule_sha256,source_capsule_locator,approval_id,
                requester_id,profile_id,profile_version,expected_run_version,bound_run_version,
                request_sha256,decision_sha256,decision_identity_sha256,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (principal.tenant_id, project_id, run_id, build_id, checkout["run_id"],
                 checkout["checkout_id"], checkout["revision"], snapshot_sha, capsule_sha,
                 locator, approval["approvalId"], principal.subject_id, profile["profile_id"],
                 profile["version"], data["expectedRunVersion"], approval["runVersion"],
                 request_sha, decision_sha, identity_sha, expires),
            )
            event(conn, principal.tenant_id, run_id, "inv.build.preparation_requested",
                  {"buildId": build_id, "approvalId": approval["approvalId"],
                   "requestDigest": request_sha, "profileVersion": profile["version"]})
            event(conn, principal.tenant_id, run_id, "inv.build.approval_bound",
                  {"buildId": build_id, "approvalId": approval["approvalId"],
                   "decisionIdentityDigest": identity_sha})
            response = {"buildId": build_id, "runId": run_id,
                        "sourceRunId": checkout["run_id"], "approvalId": approval["approvalId"],
                        "requestDigest": request_sha, "decisionIdentityDigest": identity_sha,
                        "status": "awaiting_approval", "expiresAt": expires.isoformat()}
            validate_contract("BuildPreparationView", response)
            self._save_replay(conn, principal, project_id, "build.prepare", key, response)
            return response

    def enqueue(self, principal: Principal, project_id: str, run_id: str, build_id: str,
                data: Mapping, *, key: str):
        data = dict(data)
        validate_contract("BuildEnqueueInput", data)
        if os.environ.get(PRODUCT_ENABLE_SETTING) != PRODUCT_ENABLE_VALUE:
            raise DomainError("RES-0006", "Product BuildKit dispatch is disabled", 503, True)
        replay = self._reserve(
            principal, project_id, "build.enqueue", key,
            {"projectId": project_id, "runId": run_id, "buildId": build_id, **data},
            ENQUEUE_LIMITS,
        )
        if replay is not None:
            return replay
        if self.plan_factory is None:
            raise DomainError("RES-0006", "Measured build provider authority unavailable", 503, True)

        with self.db.transaction(principal.tenant_id) as conn:
            prep = conn.execute(
                """SELECT * FROM inv.build_preparations
                WHERE project_id=%s AND run_id=%s AND build_id=%s FOR SHARE""",
                (project_id, run_id, build_id),
            ).fetchone()
        if not prep or prep["approval_id"] != data["approvalId"]:
            raise DomainError("RES-0004", "Build preparation was not found", 404)
        if prep["requester_id"] != principal.subject_id:
            raise DomainError("AUTH-0011", "Build preparation actor differs", 403)

        def authority_factory(conn, run, approved_decision, request):
            locked = conn.execute(
                """SELECT p.*,e.revision,e.content_hash FROM inv.build_preparations p
                JOIN LATERAL (SELECT revision,content_hash FROM inv.workspace_edits
                  WHERE checkout_id=p.checkout_id ORDER BY revision DESC LIMIT 1) e ON true
                WHERE p.project_id=%s AND p.run_id=%s AND p.build_id=%s FOR UPDATE OF p""",
                (project_id, run_id, build_id),
            ).fetchone()
            if (not locked or locked["queued_at"] is not None
                    or locked["revision"] != locked["source_revision"]
                    or locked["content_hash"] != locked["source_snapshot_sha256"]
                    or digest(request) != locked["request_sha256"]
                    or digest(_identity_decision(approved_decision)) != locked["decision_identity_sha256"]):
                raise DomainError("VERIFY-0002", "Build preparation authority drifted", 422)
            plan, evidence_id = self.plan_factory(conn, principal, locked, request, approved_decision)
            conn.execute(
                "UPDATE inv.build_preparations SET queued_at=clock_timestamp() WHERE build_id=%s",
                (build_id,),
            )
            return plan, evidence_id

        try:
            result = ApprovalStore(self.db).dispatch(
                principal, project_id, data["approvalId"], self._request_for(prep), key=f"build:{key}",
                build_authority_factory=authority_factory,
            )
        except DomainError as error:
            if error.retryable or error.code in {"RES-0006", "RES-0007"}:
                raise
            self._terminalize(principal, project_id, run_id, data["approvalId"], error.code)
            raise
        with self.db.transaction(principal.tenant_id) as conn:
            self._save_replay(conn, principal, project_id, "build.enqueue", key, result)
        return result

    def _request_for(self, prep):
        with self.db.transaction(str(prep["tenant_id"])) as conn:
            row = conn.execute(
                "SELECT workload FROM inv.approval_review_snapshots WHERE approval_id=%s",
                (prep["approval_id"],),
            ).fetchone()
            if not row:
                raise DomainError("VERIFY-0002", "Build approval snapshot unavailable", 422)
            return deepcopy(row["workload"])

    def _terminalize(self, principal, project_id, run_id, approval_id, code):
        with self.db.transaction(principal.tenant_id) as conn:
            row = conn.execute(
                "SELECT status FROM inv.approval_requests WHERE approval_id=%s FOR UPDATE",
                (approval_id,),
            ).fetchone()
            if row and row["status"] in {"pending", "approved"}:
                conn.execute("UPDATE inv.approval_requests SET status='rejected' WHERE approval_id=%s",
                             (approval_id,))
                run = conn.execute("SELECT * FROM inv.runs WHERE run_id=%s FOR UPDATE", (run_id,)).fetchone()
                if run and run["state"] == "awaiting_approval":
                    from .runs import RunStore
                    RunStore(BoundDatabase(self.db, principal.tenant_id, conn))._transition(
                        conn, principal.tenant_id, run, "failed", run["version"]
                    )
                event(conn, principal.tenant_id, run_id, "inv.build.preparation_rejected",
                      {"approvalId": approval_id, "errorCode": code,
                       "actorId": "system:build-preparation-drift"})
