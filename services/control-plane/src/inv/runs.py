"""Durable state, attempt checkpoints, evidence and outbox transactions."""

import hashlib
import json
from uuid import uuid4
from psycopg.types.json import Jsonb
from .contracts import validate_contract
from .db import Database
from .errors import DomainError
from .ids import new_id
from .leases import lock_run, lock_resources, assert_fences
from .state import check_transition
from .storage import verify_content


def public(row):
    return {
        "runId": row["run_id"],
        "tenantId": str(row["tenant_id"]),
        "projectId": row["project_id"],
        "state": row["state"],
        "version": row["version"],
        "attempt": row["attempt"],
    }


def event(conn, tenant_id, run_id, event_type, payload):
    event_id = uuid4()
    conn.execute(
        """INSERT INTO inv.outbox(tenant_id,run_id,event_id,event_type,payload)
        VALUES (%s,%s,%s,%s,%s)""",
        (tenant_id, run_id, event_id, event_type, Jsonb(payload)),
    )
    return str(event_id)


class RunStore:
    def __init__(self, database: Database):
        self.db = database

    def create(self, tenant_id, project_id, *, run_id=None):
        run_id = run_id or new_id("run")
        with self.db.transaction(tenant_id) as conn:
            row = conn.execute(
                "INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES (%s,%s,%s) RETURNING *",
                (tenant_id, project_id, run_id),
            ).fetchone()
            event(conn, tenant_id, run_id, "inv.run.created", public(row))
            return public(row)

    def get(self, tenant_id, run_id):
        with self.db.transaction(tenant_id) as conn:
            row = conn.execute(
                "SELECT * FROM inv.runs WHERE run_id=%s", (run_id,)
            ).fetchone()
            if not row:
                raise DomainError("RES-0004", "Run not found", 404)
            return public(row)

    def _transition(
        self, conn, tenant_id, row, target, expected_version, *, evidence_ready=False
    ):
        if row["version"] != expected_version:
            raise DomainError("GRAPH-0003", "Run version changed; reload before retry")
        check_transition(row["state"], target, evidence_ready=evidence_ready)
        if row["state"] == target:
            return public(row)
        # State changes revoke execution rights, not physical reservations.
        # Release requires the authenticated Node stop acknowledgement.
        updated = conn.execute(
            """UPDATE inv.runs SET state=%s,version=version+1,
            attempt=attempt+CASE WHEN %s='running' THEN 1 ELSE 0 END
            WHERE run_id=%s RETURNING *""",
            (target, target, row["run_id"]),
        ).fetchone()
        if target == "running":
            conn.execute(
                "INSERT INTO inv.run_attempts(tenant_id,run_id,attempt) VALUES (%s,%s,%s)",
                (tenant_id, row["run_id"], updated["attempt"]),
            )
        event(conn, tenant_id, row["run_id"], "inv.run.state_changed", public(updated))
        return public(updated)

    def transition(self, tenant_id, run_id, target, *, expected_version, proofs=None):
        if target == "succeeded":
            raise DomainError("VERIFY-0001", "Use verified completion to succeed")
        with self.db.transaction(tenant_id) as conn:
            row = lock_run(conn, run_id)
            if target in {"running", "verifying"} and row["state"] != target:
                assert_fences(conn, run_id, proofs)
            if (
                target == "scheduled"
                and row["state"] == "recovering"
                and conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                    (run_id,),
                ).fetchone()
            ):
                raise DomainError(
                    "LEASE-0003", "Recovery awaits physical resource release"
                )
            return self._transition(conn, tenant_id, row, target, expected_version)

    def checkpoint(self, tenant_id, run_id, step_id, content, *, proofs):
        if not isinstance(step_id, str) or not step_id or len(step_id) > 200:
            raise DomainError("VAL-0003", "Invalid step ID", 422)
        digest = hashlib.sha256(
            json.dumps(
                content, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        with self.db.transaction(tenant_id) as conn:
            row = lock_run(conn, run_id)
            if row["state"] != "running":
                raise DomainError("GRAPH-0002", "Checkpoints require a running attempt")
            assert_fences(conn, run_id, proofs)
            conn.execute(
                """INSERT INTO inv.checkpoints(tenant_id,run_id,attempt,step_id,content_hash,checkpoint)
                VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (tenant_id, run_id, row["attempt"], step_id, digest, Jsonb(content)),
            )
            prior = conn.execute(
                "SELECT content_hash FROM inv.checkpoints WHERE run_id=%s AND attempt=%s AND step_id=%s",
                (run_id, row["attempt"], step_id),
            ).fetchone()
            if prior["content_hash"] != digest:
                raise DomainError(
                    "GRAPH-0004", "Checkpoint identity already has different content"
                )
            return {
                "runId": run_id,
                "attempt": row["attempt"],
                "stepId": step_id,
                "contentHash": digest,
            }

    def checkpoints(self, tenant_id, run_id):
        with self.db.transaction(tenant_id) as conn:
            return conn.execute(
                """SELECT attempt,step_id,content_hash,checkpoint FROM inv.checkpoints
                WHERE run_id=%s ORDER BY attempt,step_id""",
                (run_id,),
            ).fetchall()

    def complete(
        self,
        tenant_id,
        run_id,
        *,
        expected_version,
        evidence,
        artifact_path,
        expected_size,
        proofs
    ):
        # artifact_path must be resolved by a trusted Storage worker, never browser input.
        # Object publication/retention pins are a later integration; this verifies bytes now.
        validate_contract("EvidenceEnvelope", evidence)
        if (
            evidence["tenantId"] != tenant_id
            or evidence["runId"] != run_id
            or evidence["result"] != "succeeded"
        ):
            raise DomainError("VERIFY-0002", "Evidence scope or result is invalid", 422)
        verify_content(artifact_path, evidence["outputSha256"], expected_size)
        with self.db.transaction(tenant_id) as conn:
            row = lock_run(conn, run_id)
            if row["version"] != expected_version or row["state"] != "verifying":
                raise DomainError(
                    "GRAPH-0003", "Completion requires the current verifying version"
                )
            assert_fences(conn, run_id, proofs)
            conn.execute(
                "INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES (%s,%s,%s,%s)",
                (tenant_id, run_id, evidence["evidenceId"], Jsonb(evidence)),
            )
            return self._transition(
                conn, tenant_id, row, "succeeded", expected_version, evidence_ready=True
            )
