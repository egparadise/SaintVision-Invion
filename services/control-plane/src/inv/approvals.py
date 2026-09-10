"""Trusted service boundary; callers obtain Principal from verified identity.

Lock order: idempotency -> Run -> Approval -> sorted grant subjects -> nonce.
Identity projection writers lock sorted grants only and never acquire Run locks.
No browser endpoint or external command executor is exposed by this module.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4
import hashlib
import hmac
import json
import secrets
from psycopg.types.json import Jsonb
from .contracts import validate_contract
from .db import Database
from .errors import DomainError
from .ids import new_id
from .leases import lock_run
from .policy import action_digest
from .runs import RunStore, event


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    subject_id: str

    def __post_init__(self):
        if (
            str(UUID(self.tenant_id)) != self.tenant_id
            or not isinstance(self.subject_id, str)
            or not 1 <= len(self.subject_id) <= 200
        ):
            raise ValueError("Canonical verified identity required")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def view(row):
    return {
        "approvalId": row["approval_id"],
        "runId": row["run_id"],
        "projectId": row["project_id"],
        "requesterId": row["requester_id"],
        "actionDigest": row["action_digest"],
        "policyVersion": row["policy_version"],
        "requiredApprovals": row["required_approvals"],
        "status": row["status"],
        "expiresAt": row["expires_at"].isoformat(),
        "runVersion": row["bound_run_version"],
    }


class ApprovalStore:
    def __init__(self, database: Database):
        self.db = database
        self.runs = RunStore(database)

    def _grant(self, conn, project_id, subject_id, permission):
        from .business_auth import permission as business_permission
        row = conn.execute(
            "SELECT * FROM inv.project_grants WHERE project_id=%s AND subject_id=%s FOR SHARE",
            (project_id, subject_id),
        ).fetchone()
        if not row or not row["enabled"] or not row[permission]:
            raise DomainError("AUTH-0030", "Project permission is unavailable", 403)
        business_permission(conn, project_id, subject_id, permission)

    def _ledger(self, conn, principal, project_id, operation, key, payload):
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise DomainError("VAL-0003", "Idempotency key is required", 422)
        request_hash = digest(
            {
                "subject": principal.subject_id,
                "epoch": self.db.recovery_epoch,
                "payload": payload,
            }
        )
        conn.execute(
            """INSERT INTO inv.idempotency(tenant_id,project_id,operation,key,request_hash)
            VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (principal.tenant_id, project_id, operation, key, request_hash),
        )
        row = conn.execute(
            "SELECT request_hash,response FROM inv.idempotency WHERE project_id=%s AND operation=%s AND key=%s FOR UPDATE",
            (project_id, operation, key),
        ).fetchone()
        if row["request_hash"] != request_hash:
            raise DomainError("IDEM-0001", "Idempotency key has different request content")
        return row["response"]

    def _save(self, conn, project_id, operation, key, response):
        conn.execute(
            "UPDATE inv.idempotency SET response=%s WHERE project_id=%s AND operation=%s AND key=%s",
            (Jsonb(response), project_id, operation, key),
        )
        return response

    def _locked(self, conn, approval_id, project_id):
        candidate = conn.execute(
            "SELECT run_id FROM inv.approval_requests WHERE approval_id=%s AND project_id=%s",
            (approval_id, project_id),
        ).fetchone()
        if not candidate:
            raise DomainError("RES-0004", "Approval not found", 404)
        run = lock_run(conn, candidate["run_id"], project_id)
        row = conn.execute(
            "SELECT * FROM inv.approval_requests WHERE approval_id=%s FOR UPDATE",
            (approval_id,),
        ).fetchone()
        return run, row

    def _current(self, conn, run, row, states):
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if (
            row["status"] not in states
            or row["expires_at"] <= now
            or str(row["recovery_epoch"]) != self.db.recovery_epoch
        ):
            raise DomainError("AUTH-0031", "Approval is expired, stale, or unavailable", 403)
        if run["state"] != "awaiting_approval" or run["version"] != row["bound_run_version"]:
            raise DomainError("AUTH-0032", "Run changed after approval was requested")

    def _audit(self, conn, principal, row, phase):
        record = {
            "actionDigest": row["action_digest"],
            "policyVersion": row["policy_version"],
            "status": row["status"],
        }
        conn.execute(
            """INSERT INTO inv.approval_audit(tenant_id,approval_id,event_id,actor_id,phase,record)
            VALUES(%s,%s,%s,%s,%s,%s)""",
            (
                principal.tenant_id,
                row["approval_id"],
                uuid4(),
                principal.subject_id,
                phase,
                Jsonb(record),
            ),
        )
        event(
            conn,
            principal.tenant_id,
            row["run_id"],
            "inv.approval." + phase,
            {"approvalId": row["approval_id"], **record},
        )

    def request(
        self,
        principal: Principal,
        run_id,
        workload,
        policy,
        *,
        policy_version,
        expected_version,
        key,
    ):
        validate_contract("WorkloadSpec", workload)
        validate_contract("PolicyDecision", policy)
        if type(expected_version) is not int or not 1 <= expected_version <= 9007199254740991:
            raise DomainError("VAL-0003", "Current integer Run version is required", 422)
        if not isinstance(policy_version, str) or not 1 <= len(policy_version) <= 200:
            raise DomainError("VAL-0003", "Policy version is required", 422)
        project_id = workload["projectId"]
        action_hash = action_digest(workload)
        if workload["tenantId"] != principal.tenant_id or any(
            policy[k] != v
            for k, v in {
                "tenantId": principal.tenant_id,
                "projectId": project_id,
                "subjectId": principal.subject_id,
                "actionDigest": action_hash,
            }.items()
        ):
            raise DomainError("AUTH-0011", "Policy and action scope do not match", 403)
        if (
            policy["riskLevel"] == "L3"
            or policy["effect"] != "require_approval"
            or policy["approvedBy"]
            or (policy["riskLevel"] == "L2" and policy["requiredApprovals"] != 2)
        ):
            raise DomainError("AUTH-0013", "Policy cannot be used to create an approval", 403)
        expires = datetime.fromisoformat(policy["expiresAt"].replace("Z", "+00:00"))
        payload = {
            "run": run_id,
            "actionDigest": action_hash,
            "policy": policy,
            "policyVersion": policy_version,
            "version": expected_version,
        }
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self._ledger(conn, principal, project_id, "approval.request", key, payload)
            if prior is not None:
                self._grant(conn, project_id, principal.subject_id, "can_request")
                return prior
            run = lock_run(conn, run_id, project_id)
            self._grant(conn, project_id, principal.subject_id, "can_request")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if not now < expires or (expires - now).total_seconds() > 3600:
                raise DomainError("AUTH-0031", "Approval expiry must be within one hour", 403)
            if run["state"] not in {"planned", "recovering"} or run["version"] != expected_version:
                raise DomainError(
                    "GRAPH-0003", "Approval requires the current planned or recovering Run"
                )
            if run["state"] == "recovering" or "workspaceResume" in workload:
                from .workspace_resume import approved_resume

                approved_resume(conn, run, workload, self.db.recovery_epoch)
                if conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                    (run_id,),
                ).fetchone():
                    raise DomainError(
                        "LEASE-0003", "Recovery approval awaits physical resource release"
                    )
            changed = self.runs._transition(
                conn, principal.tenant_id, run, "awaiting_approval", expected_version
            )
            row = conn.execute(
                """INSERT INTO inv.approval_requests(tenant_id,project_id,run_id,approval_id,requester_id,
                action_digest,policy_decision_id,policy_version,recovery_epoch,bound_run_version,required_approvals,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    principal.tenant_id,
                    project_id,
                    run_id,
                    new_id("apr"),
                    principal.subject_id,
                    action_hash,
                    policy["decisionId"],
                    policy_version,
                    self.db.recovery_epoch,
                    changed["version"],
                    policy["requiredApprovals"],
                    expires,
                ),
            ).fetchone()
            self._audit(conn, principal, row, "requested")
            return self._save(conn, project_id, "approval.request", key, view(row))

    def challenge(self, principal, project_id, approval_id):
        with self.db.transaction(principal.tenant_id) as conn:
            run, row = self._locked(conn, approval_id, project_id)
            self._grant(conn, project_id, principal.subject_id, "can_approve")
            self._current(conn, run, row, {"pending"})
            if (
                row["requester_id"] == principal.subject_id
                or conn.execute(
                    "SELECT 1 FROM inv.approval_votes WHERE approval_id=%s AND actor_id=%s",
                    (approval_id, principal.subject_id),
                ).fetchone()
            ):
                raise DomainError("AUTH-0033", "A distinct approver is required", 403)
            nonce = secrets.token_urlsafe(32)
            nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
            result = conn.execute(
                """INSERT INTO inv.approval_nonces(tenant_id,approval_id,actor_id,nonce_hash,expires_at)
                VALUES(%s,%s,%s,%s,least(%s,clock_timestamp()+interval '30 seconds'))
                ON CONFLICT(tenant_id,approval_id,actor_id) DO UPDATE SET nonce_hash=excluded.nonce_hash,expires_at=excluded.expires_at,consumed_at=NULL
                RETURNING expires_at""",
                (
                    principal.tenant_id,
                    approval_id,
                    principal.subject_id,
                    nonce_hash,
                    row["expires_at"],
                ),
            ).fetchone()
            return {
                "approvalId": approval_id,
                "nonce": nonce,
                "expiresAt": result["expires_at"].isoformat(),
            }

    def decide(self, principal, project_id, approval_id, decision, nonce, *, action_digest, key):
        validate_contract(
            "ApprovalDecisionInput",
            {"decision": decision, "nonce": nonce, "actionDigest": action_digest},
        )
        nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
        payload = {
            "approval": approval_id,
            "decision": decision,
            "nonceHash": nonce_hash,
            "actionDigest": action_digest,
        }
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self._ledger(conn, principal, project_id, "approval.decide", key, payload)
            run, row = self._locked(conn, approval_id, project_id)
            self._grant(conn, project_id, principal.subject_id, "can_approve")
            if prior is not None:
                return prior
            self._current(conn, run, row, {"pending"})
            if principal.subject_id == row["requester_id"] or action_digest != row["action_digest"]:
                raise DomainError("AUTH-0033", "Approval actor or action digest is invalid", 403)
            if conn.execute(
                "SELECT 1 FROM inv.approval_votes WHERE approval_id=%s AND actor_id=%s",
                (approval_id, principal.subject_id),
            ).fetchone():
                raise DomainError("AUTH-0033", "Actor has already decided", 403)
            challenge = conn.execute(
                """SELECT *,expires_at>clock_timestamp() AS fresh FROM inv.approval_nonces
                WHERE approval_id=%s AND actor_id=%s FOR UPDATE""",
                (approval_id, principal.subject_id),
            ).fetchone()
            if (
                not challenge
                or not challenge["fresh"]
                or challenge["consumed_at"] is not None
                or not hmac.compare_digest(challenge["nonce_hash"], nonce_hash)
            ):
                raise DomainError("AUTH-0034", "Approval challenge is invalid or expired", 403)
            conn.execute(
                "UPDATE inv.approval_nonces SET consumed_at=clock_timestamp() WHERE approval_id=%s AND actor_id=%s",
                (approval_id, principal.subject_id),
            )
            conn.execute(
                "INSERT INTO inv.approval_votes(tenant_id,approval_id,actor_id,decision,nonce_hash) VALUES(%s,%s,%s,%s,%s)",
                (
                    principal.tenant_id,
                    approval_id,
                    principal.subject_id,
                    decision,
                    nonce_hash,
                ),
            )
            votes = conn.execute(
                "SELECT count(*) AS count FROM inv.approval_votes WHERE approval_id=%s AND decision='approve'",
                (approval_id,),
            ).fetchone()["count"]
            status = (
                "rejected"
                if decision == "reject"
                else ("approved" if votes >= row["required_approvals"] else "pending")
            )
            row = conn.execute(
                "UPDATE inv.approval_requests SET status=%s WHERE approval_id=%s RETURNING *",
                (status, approval_id),
            ).fetchone()
            self._audit(conn, principal, row, "rejected" if decision == "reject" else "approved")
            if decision == "reject":
                self.runs._transition(conn, principal.tenant_id, run, "failed", run["version"])
            return self._save(conn, project_id, "approval.decide", key, view(row))

    def dispatch(self, principal, project_id, approval_id, workload, *, key):
        validate_contract("WorkloadSpec", workload)
        if workload["tenantId"] != principal.tenant_id or workload["projectId"] != project_id:
            raise DomainError("AUTH-0011", "Action scope differs", 403)
        action_hash = action_digest(workload)
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self._ledger(
                conn,
                principal,
                project_id,
                "approval.dispatch",
                key,
                {"approval": approval_id, "actionDigest": action_hash},
            )
            run, row = self._locked(conn, approval_id, project_id)
            from .shard_recovery import require_recovery_admission

            require_recovery_admission(conn, self.db, run["run_id"])
            from .business_handoff import require_handoff

            require_handoff(conn, self.db, run["run_id"])
            voters = conn.execute(
                "SELECT actor_id FROM inv.approval_votes WHERE approval_id=%s AND decision='approve' ORDER BY actor_id",
                (approval_id,),
            ).fetchall()
            for subject in sorted({principal.subject_id} | {v["actor_id"] for v in voters}):
                self._grant(
                    conn,
                    project_id,
                    subject,
                    "can_request" if subject == principal.subject_id else "can_approve",
                )
            if principal.subject_id != row["requester_id"] or action_hash != row["action_digest"]:
                raise DomainError("AUTH-0011", "Approval and action do not match", 403)
            if prior is not None:
                return prior
            self._current(conn, run, row, {"approved"})
            if len(voters) < row["required_approvals"] or any(
                v["actor_id"] == principal.subject_id for v in voters
            ):
                raise DomainError("AUTH-0033", "Distinct approval quorum is missing", 403)
            command_id = str(uuid4())
            conn.execute(
                "INSERT INTO inv.approval_dispatches(tenant_id,approval_id,command_id) VALUES(%s,%s,%s)",
                (principal.tenant_id, approval_id, command_id),
            )
            row = conn.execute(
                "UPDATE inv.approval_requests SET status='dispatched' WHERE approval_id=%s RETURNING *",
                (approval_id,),
            ).fetchone()
            result = {
                "commandId": command_id,
                "approvalId": approval_id,
                "runId": run["run_id"],
                "tenantId": principal.tenant_id,
                "projectId": project_id,
                "actionDigest": action_hash,
                "policyVersion": row["policy_version"],
                "recoveryEpoch": self.db.recovery_epoch,
                "expiresAt": row["expires_at"].isoformat(),
            }
            event(
                conn,
                principal.tenant_id,
                run["run_id"],
                "inv.command.authorized",
                result,
            )
            self._audit(conn, principal, row, "dispatched")
            self.runs._transition(conn, principal.tenant_id, run, "scheduled", run["version"])
            return self._save(conn, project_id, "approval.dispatch", key, result)

    def expire(self, tenant_id, project_id, approval_id):
        # Deterministic reconciler, no user-authored effect or privilege change.
        with self.db.transaction(tenant_id) as conn:
            run, row = self._locked(conn, approval_id, project_id)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if row["status"] not in {"pending", "approved"} or row["expires_at"] > now:
                return False
            row = conn.execute(
                "UPDATE inv.approval_requests SET status='expired' WHERE approval_id=%s RETURNING *",
                (approval_id,),
            ).fetchone()
            self._audit(conn, Principal(tenant_id, "system:approval-expiry"), row, "expired")
            if run["state"] == "awaiting_approval":
                self.runs._transition(conn, tenant_id, run, "failed", run["version"])
            return True
