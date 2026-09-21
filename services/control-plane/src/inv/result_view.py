"""Read current kernel evidence and bounded bytes under the current project grant.

Public business Run records are not a projection of inv.runs. Read the canonical
attempt, authenticated receipt and committed Evidence here, without broadening
the business DB role. No state transition or output ingestion happens on a GET.
"""

import base64
import hashlib

from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .leases import lock_run
from .node_transport import strict_json
from .output_ingestion import output_bytes
from .workspace_files import decode_snapshot, portable_path
from .workspace_resume import workspace_output


def _time(value):
    return value.isoformat() if value else None


def _checked(name, value):
    validate_contract(name, value)
    return value


class ResultView:
    def __init__(self, database):
        self.db = database

    def _scope(self, conn, principal, project, run_id):
        validate_contract("RunId", run_id)
        if project is not None:
            validate_contract("ProjectId", project)
        if project is None:
            row = conn.execute(
                "SELECT project_id FROM inv.runs WHERE run_id=%s", (run_id,)
            ).fetchone()
            if not row:
                raise DomainError("AUTH-0030", "Project permission is unavailable", 403)
            project = row["project_id"]
        # Match execution writers: Run before current grant. Both locks remain
        # held through serialization/hash checking, so revocation cannot interleave.
        run = lock_run(conn, run_id, project)
        Control(self.db).grant(conn, principal, project)
        return run

    @staticmethod
    def _current(conn, run):
        row = conn.execute(
            """SELECT a.command_id, a.node_id, a.attempt,
          s.receipt_id, s.envelope AS receipt, c.evidence_id, c.completed_at,
          e.envelope AS evidence, p.envelope AS commitment,
          o.content_hash, o.size_bytes, o.state AS object_state, d.envelope AS delivery
          FROM inv.execution_attempts a
          LEFT JOIN inv.node_stop_receipts s USING(tenant_id,command_id)
          LEFT JOIN inv.result_completions c USING(tenant_id,command_id)
          LEFT JOIN inv.result_commitments p USING(tenant_id,command_id)
          LEFT JOIN inv.evidence e ON (e.tenant_id,e.run_id,e.evidence_id)=(c.tenant_id,c.run_id,c.evidence_id)
          LEFT JOIN inv.storage_objects o ON (o.tenant_id,o.project_id,o.object_id)=(p.tenant_id,p.project_id,p.object_id)
          LEFT JOIN inv.execution_deliveries d ON (d.tenant_id,d.command_id)=(a.tenant_id,a.command_id)
          WHERE a.run_id=%s AND a.attempt=%s""",
            (run["run_id"], run["attempt"]),
        ).fetchone()
        if row or run["attempt"] != 0:
            return row
        # Cancellation can produce a physical tombstone before an attempt is
        # started. Show that actual receipt without inventing an attempt.
        return conn.execute(
            """SELECT d.command_id,d.node_id,s.receipt_id,s.envelope AS receipt,
          NULL AS evidence_id,NULL AS completed_at,NULL AS evidence,NULL AS commitment,
          NULL AS content_hash,NULL AS size_bytes,NULL AS object_state,d.envelope AS delivery
          FROM inv.execution_deliveries d LEFT JOIN inv.node_stop_receipts s USING(tenant_id,command_id)
          WHERE d.run_id=%s ORDER BY d.created_at DESC,d.command_id DESC LIMIT 1""",
            (run["run_id"],),
        ).fetchone()

    @staticmethod
    def _output(row):
        if not row or not row["evidence_id"]:
            return None
        if (
            not row["receipt"]
            or row["object_state"] != "ready"
            or row["evidence"] != row["commitment"]
        ):
            raise DomainError("VERIFY-0023", "Committed output evidence is inconsistent")
        raw = output_bytes(row["receipt"])
        if (
            len(raw) != row["size_bytes"]
            or hashlib.sha256(raw).hexdigest() != row["content_hash"]
            or row["evidence"]["outputSha256"] != row["content_hash"]
        ):
            raise DomainError("VERIFY-0023", "Committed output bytes differ")
        return strict_json(raw)

    @staticmethod
    def _files(row, artifact):
        if artifact is None or row["delivery"] is None:
            return None
        launch = strict_json(base64.b64decode(row["delivery"]["payload"], validate=True))["launch"]
        raw = workspace_output(artifact, launch)
        return decode_snapshot(raw, launch["workspaceId"]) if raw is not None else None

    def result(self, principal, run_id, project=None):
        with self.db.transaction(principal.tenant_id) as conn:
            run = self._scope(conn, principal, project, run_id)
            row = self._current(conn, run)
            artifact = self._output(row)
            receipt = row["receipt"] if row else None
            # A nonzero exit or missing receipt never becomes success Evidence.
            return _checked(
                "RunResultView",
                {
                    "source": "execution-kernel",
                    "runId": run_id,
                    "projectId": run["project_id"],
                    "state": run["state"],
                    "version": run["version"],
                    "attemptCount": run["attempt"],
                    # Durable state-change time, not the time this HTTP read ran.
                    "stateUpdatedAt": _time(run["updated_at"]),
                    "sealed": artifact is not None,
                    "executionConfirmed": bool(receipt and receipt["processStarted"]),
                    "commandId": str(row["command_id"]) if row else None,
                    "nodeId": row["node_id"] if row else None,
                    "stopReceipt": (
                        {
                            "receiptId": str(row["receipt_id"]),
                            "processStarted": receipt["processStarted"],
                            "exitCode": receipt["exitCode"],
                            "reason": receipt["reason"],
                            "finishedAt": receipt["finishedAt"],
                        }
                        if receipt
                        else None
                    ),
                    "evidence": row["evidence"] if artifact is not None else None,
                    "completedAt": _time(row["completed_at"]) if row else None,
                    "output": (
                        {
                            "sha256": row["content_hash"],
                            "sizeBytes": row["size_bytes"],
                            "verified": True,
                        }
                        if artifact is not None
                        else None
                    ),
                    "outputAbsentReason": (
                        None if artifact is not None else "No committed output for this attempt"
                    ),
                    "resourceReleasePending": bool(
                        conn.execute(
                            """SELECT 1 FROM inv.resource_leases WHERE released_at IS NULL AND
                    (run_id=%s OR run_id IN (SELECT s.run_id FROM inv.shard_commands s
                     JOIN inv.shard_parents p USING(tenant_id,project_id,plan_id) WHERE p.run_id=%s)) LIMIT 1""",
                            (run_id, run_id),
                        ).fetchone()
                    ),
                },
            )

    def artifacts(self, principal, run_id, project=None):
        with self.db.transaction(principal.tenant_id) as conn:
            run = self._scope(conn, principal, project, run_id)
            row = self._current(conn, run)
            files = self._files(row, self._output(row))
            items = (
                []
                if files is None
                else [
                    {
                        "path": f["path"],
                        "checksumSha256": f["sha256"],
                        "byteSize": f["sizeBytes"],
                        "verified": True,
                        "evidenceId": row["evidence_id"],
                    }
                    for f in files[0]["files"]
                ]
            )
            return _checked(
                "RunArtifactList",
                {
                    "source": "execution-kernel",
                    "runId": run_id,
                    "completedAt": _time(row["completed_at"]) if row else None,
                    "artifacts": items,
                    "count": len(items),
                    "verifiedCount": len(items),
                    "absentReason": (
                        "No committed Workspace output for this attempt" if files is None else None
                    ),
                },
            )

    def download(self, principal, run_id, path, project=None):
        with self.db.transaction(principal.tenant_id) as conn:
            run = self._scope(conn, principal, project, run_id)
            portable_path(path)
            row = self._current(conn, run)
            files = self._files(row, self._output(row))
            if files is None or path not in files[1]:
                raise DomainError("RES-0004", "Committed output file unavailable", 404)
            file = next(item for item in files[0]["files"] if item["path"] == path)
            content = files[1][path]
            if (
                len(content) != file["sizeBytes"]
                or hashlib.sha256(content).hexdigest() != file["sha256"]
            ):
                raise DomainError("VERIFY-0023", "Committed artifact bytes differ")
            return {
                "content": content,
                "artifact": {
                    "path": file["path"],
                    "checksumSha256": file["sha256"],
                    "byteSize": file["sizeBytes"],
                    "verified": True,
                    "evidenceId": str(row["evidence_id"]),
                },
            }

    def logs(self, principal, run_id, project=None):
        from saintvision.adapters.reference import redact_text

        with self.db.transaction(principal.tenant_id) as conn:
            run = self._scope(conn, principal, project, run_id)
            row = self._current(conn, run)
            artifact = self._output(row)
            result = {
                "source": "execution-kernel",
                "runId": run_id,
                "completedAt": _time(row["completed_at"]) if row else None,
                "stdout": None,
                "stderr": None,
                "redacted": False,
                "truncated": None,
                "absentReason": "No committed process output for this attempt",
            }
            if artifact is not None:
                for name in ("stdout", "stderr"):
                    result[name], changed = redact_text(
                        base64.b64decode(artifact[name], validate=True).decode(
                            "utf-8", errors="replace"
                        )
                    )
                    result["redacted"] |= changed
                result.update(truncated=artifact["truncated"], absentReason=None)
            return _checked("RunLogView", result)

    def attempts(self, principal, run_id, project=None, *, after=0, limit=50):
        if (
            type(after) is not int
            or not 0 <= after <= 9007199254740991
            or type(limit) is not int
            or not 1 <= limit <= 200
        ):
            raise DomainError("VAL-0003", "Invalid attempt page", 422)
        with self.db.transaction(principal.tenant_id) as conn:
            self._scope(conn, principal, project, run_id)
            rows = conn.execute(
                """SELECT a.attempt,a.started_at,x.command_id,x.node_id,
              s.receipt_id,s.envelope,c.evidence_id FROM inv.run_attempts a
              LEFT JOIN inv.execution_attempts x USING(tenant_id,run_id,attempt)
              LEFT JOIN inv.node_stop_receipts s ON (s.tenant_id,s.command_id)=(x.tenant_id,x.command_id)
              LEFT JOIN inv.result_completions c ON (c.tenant_id,c.command_id)=(x.tenant_id,x.command_id)
              WHERE a.run_id=%s AND a.attempt>%s ORDER BY a.attempt LIMIT %s""",
                (run_id, after, limit + 1),
            ).fetchall()
            items = [
                {
                    "attemptNumber": r["attempt"],
                    "startedAt": _time(r["started_at"]),
                    "nodeId": r["node_id"],
                    "commandId": str(r["command_id"]) if r["command_id"] else None,
                    "stopReceiptId": str(r["receipt_id"]) if r["receipt_id"] else None,
                    "exitCode": r["envelope"]["exitCode"] if r["envelope"] else None,
                    "reason": r["envelope"]["reason"] if r["envelope"] else None,
                    "evidenceId": r["evidence_id"],
                }
                for r in rows[:limit]
            ]
            return _checked(
                "RunAttemptList",
                {
                    "source": "execution-kernel",
                    "runId": run_id,
                    "attempts": items,
                    "count": len(items),
                    "nextCursor": items[-1]["attemptNumber"] if len(rows) > limit else None,
                },
            )
