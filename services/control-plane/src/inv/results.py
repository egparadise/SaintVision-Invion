"""Fenced immutable outputs followed by receipt-bound, atomic completion.

Trusted application verifier API, not an unauthenticated upload endpoint. The
caller must authorize project access and verify application semantics before
preparing Evidence. Actual bytes are rehashed here under the provider lock.
Prepare while execution rights remain valid; complete after the physical receipt.
No expired/recovered execution may introduce new output or change a sealed one.
"""

from copy import deepcopy
from datetime import datetime
from uuid import UUID
from psycopg.types.json import Jsonb
from .approvals import digest
from .contracts import validate_contract
from .errors import DomainError
from .leases import assert_fences, lock_run
from .runs import RunStore, event, public
from .snapshots import SnapshotStore, identity, object_key


class ResultStore:
    def __init__(self, database, provider):
        self.db, self.provider = database, provider

    @staticmethod
    def _execution(conn, run, command):
        row = conn.execute(
            """SELECT a.*,c.recovery_epoch,c.not_after,c.action_digest,c.policy_decision_id
            FROM inv.execution_attempts a JOIN inv.tool_claims c USING(tenant_id,command_id)
            WHERE a.command_id=%s AND a.run_id=%s AND a.attempt=%s""",
            (command, run["run_id"], run["attempt"]),
        ).fetchone()
        if not row:
            raise DomainError("VERIFY-0020", "Current managed execution required")
        return row

    def prepare(
        self, tenant, project, run_id, command_id, object_id, evidence, *, proofs
    ):
        command_id, object_id = str(UUID(command_id)), identity(object_id)
        evidence, proofs = deepcopy(evidence), deepcopy(proofs)
        validate_contract("EvidenceEnvelope", evidence)
        if (evidence["tenantId"], evidence["runId"], evidence["result"]) != (
            tenant,
            run_id,
            "succeeded",
        ):
            raise DomainError("VERIFY-0002", "Evidence scope or result differs", 422)
        fingerprint = digest(
            {"command": command_id, "object": object_id, "evidence": evidence}
        )
        # Provider before Run before Node/resources before object, matching
        # checkpoint publication. GC never acquires Run after holding an object.
        with self.provider.locked() as files, self.db.transaction(tenant) as conn:
            run = lock_run(conn, run_id, project)
            execution = self._execution(conn, run, command_id)
            if str(execution["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("LEASE-0004", "Result belongs to an old epoch")
            prior = conn.execute(
                "SELECT content_hash FROM inv.result_commitments WHERE command_id=%s",
                (command_id,),
            ).fetchone()
            if prior:
                if prior["content_hash"] != fingerprint:
                    raise DomainError("IDEM-0001", "Execution result already differs")
                # A replay observes an immutable prior seal, even after expiry.
                return {
                    "commandId": command_id,
                    "evidenceId": evidence["evidenceId"],
                    "replayed": True,
                }
            if run["state"] not in {"running", "verifying"}:
                raise DomainError(
                    "GRAPH-0002", "Result requires a current running attempt"
                )
            assert_fences(conn, run_id, proofs)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            if execution["not_after"] <= now or proofs != execution["proofs"]:
                raise DomainError("LEASE-0002", "Output authority expired or differs")
            if (
                evidence["inputSha256"] != execution["action_digest"]
                or evidence["policyDecisionId"] != execution["policy_decision_id"]
                or datetime.fromisoformat(evidence["timestamp"].replace("Z", "+00:00"))
                > now
            ):
                raise DomainError(
                    "VERIFY-0002",
                    "Evidence does not bind admitted input and policy",
                    422,
                )
            obj = SnapshotStore._row(conn, project, object_id)
            if (
                obj["state"] != "ready"
                or evidence["outputSha256"] != obj["content_hash"]
            ):
                raise DomainError(
                    "VERIFY-0010", "Result object is not verified and ready", 422
                )
            files.read(object_key(object_id), obj["content_hash"], obj["size_bytes"])
            conn.execute(
                """INSERT INTO inv.result_commitments
                (tenant_id,project_id,run_id,attempt,command_id,object_id,evidence_id,envelope,content_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    tenant,
                    project,
                    run_id,
                    run["attempt"],
                    command_id,
                    object_id,
                    evidence["evidenceId"],
                    Jsonb(evidence),
                    fingerprint,
                ),
            )
            event(
                conn,
                tenant,
                run_id,
                "inv.run.result_prepared",
                {
                    "commandId": command_id,
                    "attempt": run["attempt"],
                    "objectId": object_id,
                    "evidenceId": evidence["evidenceId"],
                },
            )
            return {
                "commandId": command_id,
                "evidenceId": evidence["evidenceId"],
                "replayed": False,
            }

    def complete(self, tenant, project, run_id, command_id, *, expected_version):
        command_id = str(UUID(command_id))
        with self.provider.locked() as files, self.db.transaction(tenant) as conn:
            run = lock_run(conn, run_id, project)
            execution = self._execution(conn, run, command_id)
            if str(execution["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("LEASE-0004", "Result belongs to an old epoch")
            if conn.execute(
                "SELECT 1 FROM inv.result_completions WHERE command_id=%s",
                (command_id,),
            ).fetchone():
                return public(run)
            if (
                run["state"] not in {"running", "verifying"}
                or run["version"] != expected_version
            ):
                raise DomainError(
                    "GRAPH-0003", "Completion requires current active attempt version"
                )
            result = conn.execute(
                "SELECT * FROM inv.result_commitments WHERE command_id=%s",
                (command_id,),
            ).fetchone()
            stop = conn.execute(
                "SELECT envelope FROM inv.node_stop_receipts WHERE command_id=%s",
                (command_id,),
            ).fetchone()
            if not result or not stop:
                raise DomainError(
                    "VERIFY-0021",
                    "Prepared output and authenticated stop receipt required",
                )
            receipt = stop["envelope"]
            if (
                not receipt["processStarted"]
                or receipt["exitCode"] != 0
                or receipt["reason"] != "exited"
                or {
                    a["lease"]["leaseId"]: a["lease"]["fencingToken"]
                    for a in receipt["allocations"]
                }
                != execution["proofs"]
            ):
                raise DomainError(
                    "VERIFY-0022", "Physical outcome does not support success"
                )
            if conn.execute(
                "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (run_id,),
            ).fetchone():
                raise DomainError(
                    "LEASE-0003", "Completion awaits physical resource release"
                )
            obj = SnapshotStore._row(conn, project, result["object_id"])
            if obj["state"] != "ready":
                raise DomainError("STORE-0005", "Prepared output unavailable")
            files.read(
                object_key(obj["object_id"]), obj["content_hash"], obj["size_bytes"]
            )
            conn.execute(
                "INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES(%s,%s,%s,%s)",
                (tenant, run_id, result["evidence_id"], Jsonb(result["envelope"])),
            )
            conn.execute(
                "INSERT INTO inv.result_completions(tenant_id,run_id,attempt,command_id,evidence_id) VALUES(%s,%s,%s,%s,%s)",
                (tenant, run_id, run["attempt"], command_id, result["evidence_id"]),
            )
            store = RunStore(self.db)
            if run["state"] == "running":
                store._transition(conn, tenant, run, "verifying", run["version"])
                run = lock_run(conn, run_id, project)
            completed = store._transition(
                conn, tenant, run, "succeeded", run["version"], evidence_ready=True
            )
            event(
                conn,
                tenant,
                run_id,
                "inv.run.result_committed",
                {
                    "commandId": command_id,
                    "attempt": run["attempt"],
                    "evidenceId": result["evidence_id"],
                },
            )
            return completed
