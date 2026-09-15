"""Receipt-bound process outputs, crash recovery and three bounded publications.

This verifies process exit and captured bytes. Application-specific quality,
model accuracy and SLO acceptance need their own verifier and Evidence.
"""

import base64
from datetime import datetime
import hashlib
from uuid import uuid4, uuid5, NAMESPACE_URL
from .errors import DomainError
from .ids import ALPHABET
from .leases import lock_run
from .node_transport import strict_json
from .results import ResultStore
from .runs import RunStore, event
from .snapshots import SnapshotStore


def output_bytes(receipt):
    value = receipt["output"]
    try:
        data = base64.b64decode(value["data"], validate=True)
        if (
            len(data) != value["sizeBytes"]
            or not 1 <= len(data) <= 300000
            or hashlib.sha256(data).hexdigest() != value["sha256"]
        ):
            raise ValueError()
        artifact = strict_json(data)
        if (
            set(artifact)
            not in (
                {"stdout", "stderr", "truncated"},
                {"stdout", "stderr", "truncated", "workspace"},
            )
            or artifact["truncated"] is not False
        ):
            raise ValueError()
        for key in ("stdout", "stderr"):
            if (
                not isinstance(artifact[key], str)
                or len(base64.b64decode(artifact[key], validate=True)) > 65536
            ):
                raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, DomainError):
        raise DomainError("VERIFY-0023", "Output bytes or bounded stream artifact differ") from None


def evidence_id(command):
    value = int.from_bytes(hashlib.sha256(("inv.output:" + command).encode()).digest()[:16], "big")
    result = ""
    for _ in range(26):
        result = ALPHABET[value & 31] + result
        value >>= 5
    return "evd_" + result


class OutputIngestion:
    def __init__(self, database, provider):
        self.db, self.provider = database, provider

    def once(self, tenant, *, command_id=None):
        with self.db.transaction(tenant) as conn:
            # Candidate selection is advisory. The Run mutex and task token below
            # serialize concurrent workers, cancellation and recovery epochs.
            candidate = conn.execute(
                """SELECT r.run_id,r.project_id,a.attempt,s.command_id,s.envelope,s.recorded_at
                FROM inv.node_stop_receipts s JOIN inv.execution_attempts a USING(tenant_id,command_id)
                JOIN inv.runs r ON (a.tenant_id,a.run_id,a.attempt)=(r.tenant_id,r.run_id,r.attempt)
                LEFT JOIN inv.output_ingestions j ON (j.tenant_id,j.command_id)=(s.tenant_id,s.command_id)
                WHERE r.state IN ('running','verifying') AND (%s::uuid IS NULL OR s.command_id=%s)
                AND s.envelope->>'recoveryEpoch'=%s
                AND (NOT (s.envelope->>'processStarted')::boolean OR (s.envelope->>'exitCode')::integer<>0
                     OR s.envelope->>'reason'<>'exited' OR s.envelope ? 'output')
                AND (j.command_id IS NULL OR (NOT j.finished AND j.next_attempt_at<=clock_timestamp()))
                ORDER BY s.recorded_at,s.command_id LIMIT 1""",
                (command_id, command_id, self.db.recovery_epoch),
            ).fetchone()
            if not candidate:
                return "idle"
            run = lock_run(conn, candidate["run_id"], candidate["project_id"])
            receipt = candidate["envelope"]
            if (
                run["state"] not in {"running", "verifying"}
                or run["attempt"] != candidate["attempt"]
                or receipt["recoveryEpoch"] != self.db.recovery_epoch
            ):
                return "idle"
            command = str(candidate["command_id"])
            conn.execute(
                "INSERT INTO inv.output_ingestions(tenant_id,command_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
                (tenant, command),
            )
            job = conn.execute(
                "SELECT *,next_attempt_at<=clock_timestamp() AS due FROM inv.output_ingestions WHERE command_id=%s FOR UPDATE",
                (command,),
            ).fetchone()
            if job["finished"] or not job["due"]:
                return "idle"
            if (
                not receipt["processStarted"]
                or receipt["exitCode"] != 0
                or receipt["reason"] != "exited"
                or job["attempts"] >= 3
            ):
                RunStore(self.db)._transition(conn, tenant, run, "failed", run["version"])
                conn.execute(
                    "UPDATE inv.output_ingestions SET finished=true,token=NULL WHERE command_id=%s",
                    (command,),
                )
                event(
                    conn,
                    tenant,
                    run["run_id"],
                    "inv.execution.failed",
                    {
                        "commandId": command,
                        "reason": (
                            "physical_failure"
                            if job["attempts"] < 3
                            else "output_retries_exhausted"
                        ),
                    },
                )
                return "failed"
            if self.provider is None:
                return "idle"
            token = str(uuid4())
            conn.execute(
                "UPDATE inv.output_ingestions SET attempts=attempts+1,token=%s,next_attempt_at=clock_timestamp()+interval '30 seconds' WHERE command_id=%s",
                (token, command),
            )
            execution = ResultStore._execution(conn, run, command)
            delivery = conn.execute(
                "SELECT envelope FROM inv.execution_deliveries WHERE command_id=%s", (command,)
            ).fetchone()
            launch = (
                strict_json(base64.b64decode(delivery["envelope"]["payload"]))["launch"]
                if delivery
                else {}
            )
        error = None
        try:
            data = output_bytes(receipt)
            oid = str(uuid5(NAMESPACE_URL, "inv.output:" + tenant + ":" + command))
            store = SnapshotStore(self.db, self.provider)
            store.begin(tenant, run["project_id"], oid, receipt["output"]["sha256"], len(data))
            if store.status(tenant, run["project_id"], oid)["state"] == "uploading":
                store.put_part(tenant, run["project_id"], oid, 0, data)
            store.finalize(tenant, run["project_id"], oid)
            from .workspace_resume import workspace_output

            workspace = workspace_output(strict_json(data), launch)
            if workspace is not None:
                wid = str(uuid5(NAMESPACE_URL, "inv.workspace-output:" + tenant + ":" + command))
                store.begin(
                    tenant,
                    run["project_id"],
                    wid,
                    hashlib.sha256(workspace).hexdigest(),
                    len(workspace),
                )
                if store.status(tenant, run["project_id"], wid)["state"] == "uploading":
                    store.put_part(tenant, run["project_id"], wid, 0, workspace)
                store.finalize(tenant, run["project_id"], wid)
            evidence = {
                "evidenceId": evidence_id(command),
                "tenantId": tenant,
                "runId": run["run_id"],
                "traceId": hashlib.sha256(("inv.trace:" + command).encode()).hexdigest()[:32],
                "timestamp": candidate["recorded_at"].isoformat(),
                "actorId": "node-output-verifier:v1",
                "action": "verify-process-output",
                "policyDecisionId": execution["policy_decision_id"],
                "inputSha256": execution["action_digest"],
                "outputSha256": receipt["output"]["sha256"],
                "result": "succeeded",
            }
            results = ResultStore(self.db, self.provider)
            results.prepare(
                tenant,
                run["project_id"],
                run["run_id"],
                command,
                oid,
                evidence,
                proofs=execution["proofs"],
                receipt_bound=True,
            )
            results.complete(
                tenant, run["project_id"], run["run_id"], command, expected_version=run["version"]
            )
        except Exception as exc:
            error = exc.code if isinstance(exc, DomainError) else "SYS-0001"
        with self.db.transaction(tenant) as conn:
            current = lock_run(conn, run["run_id"], run["project_id"])
            job = conn.execute(
                "SELECT * FROM inv.output_ingestions WHERE command_id=%s FOR UPDATE", (command,)
            ).fetchone()
            if str(job["token"]) != token:
                return "superseded"
            terminal = current["state"] not in {"running", "verifying"}
            if error and not terminal and job["attempts"] >= 3:
                RunStore(self.db)._transition(conn, tenant, current, "failed", current["version"])
                terminal = True
                event(
                    conn,
                    tenant,
                    current["run_id"],
                    "inv.execution.failed",
                    {"commandId": command, "reason": "output_retries_exhausted"},
                )
            conn.execute(
                "UPDATE inv.output_ingestions SET token=NULL,last_error=%s,finished=%s,next_attempt_at=clock_timestamp()+interval '2 seconds' WHERE command_id=%s",
                (error, error is None or terminal, command),
            )
        return "completed" if error is None else ("failed" if terminal else "retry")
