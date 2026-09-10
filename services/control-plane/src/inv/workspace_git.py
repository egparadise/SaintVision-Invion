"""Two-person, immutable Git intents; at-most-once remote mutation admission.

No network I/O holds database/root locks. Once a publication is dispatched,
kill/revocation cannot recall it at GitHub; it can only prevent later dispatches.
A crash or lost response leaves 'dispatched' until read-only reconciliation.
"""

import hashlib
import json
from datetime import timedelta
from uuid import uuid4
from psycopg.types.json import Jsonb

from .approvals import Principal, digest
from .contracts import validate_contract
from .containment import require_execution
from .control import Control
from .errors import DomainError
from .leases import lock_run
from .remote_git import GitHubRepository, export_snapshot
from .runs import event
from .snapshots import identity
from .workspace_editor import WorkspaceEditor, checkout_snapshot


class WorkspaceGit:
    def __init__(self, workspace):
        self.workspace, self.db = workspace, workspace.db
        self.editor = WorkspaceEditor(workspace)

    def _repository(self, alias, project, fingerprint=None):
        repo = getattr(self.workspace, "git_repositories", {}).get(alias)
        if not repo or repo.project != project or (fingerprint and repo.fingerprint != fingerprint):
            raise DomainError(
                "AUTH-0071", "Current operator-configured Git repository required", 403
            )
        return repo

    def _actor(self, conn, principal, project, *, voting=False):
        row = conn.execute(
            "SELECT * FROM inv.operator_grants WHERE subject_id=%s FOR SHARE",
            (principal.subject_id,),
        ).fetchone()
        if (
            not row
            or not row["enabled"]
            or row["person_id"] is None
            or not row["can_approve" if voting else "can_git"]
        ):
            raise DomainError("AUTH-0071", "Verified current Git operator permission required", 403)
        Control(self.db).grant(conn, principal, project, "can_approve" if voting else "can_request")
        return row

    def _locked(self, conn, principal, project, operation_id):
        row = conn.execute(
            "SELECT * FROM inv.git_operations WHERE operation_id=%s AND project_id=%s",
            (identity(operation_id), project),
        ).fetchone()
        if not row:
            raise DomainError("RES-0004", "Git operation unavailable", 404)
        lock_run(conn, row["run_id"], project)
        row = conn.execute(
            "SELECT * FROM inv.git_operations WHERE operation_id=%s FOR UPDATE",
            (identity(operation_id),),
        ).fetchone()
        self._actor(conn, principal, project, voting=row["requester_id"] != principal.subject_id)
        if conn.execute(
            "SELECT 1 FROM inv.business_runs WHERE run_id=%s", (row["run_id"],)
        ).fetchone():
            from .business_handoff import scope

            scope(
                conn,
                self.db,
                principal,
                project,
                row["run_id"],
                "can_request" if row["requester_id"] == principal.subject_id else "can_approve",
            )
        return row

    def _fresh(self, conn, row):
        gate = conn.execute("SELECT * FROM inv.tenant_controls").fetchone()
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        require_execution(conn)
        if (
            row["phase"] != "pending"
            or row["expires_at"] <= now
            or str(row["recovery_epoch"]) != self.db.recovery_epoch
            or gate["version"] != row["gate_version"]
        ):
            raise DomainError("AUTH-0071", "Git proposal expired, dispatched or superseded", 403)
        payload = row["payload"]
        if (
            hashlib.sha256(bytes(row["snapshot"])).hexdigest() != payload["snapshotSha256"]
            or digest(payload) != row["content_digest"]
        ):
            raise DomainError("VERIFY-0024", "Git proposal integrity differs")
        return self._repository(
            payload["alias"], row["project_id"], payload["repositoryFingerprint"]
        )

    def _view(self, conn, row):
        votes = conn.execute(
            "SELECT actor_id,person_id,decision FROM inv.git_votes WHERE operation_id=%s ORDER BY actor_id",
            (row["operation_id"],),
        ).fetchall()
        result = {
            "operationId": str(row["operation_id"]),
            "projectId": row["project_id"],
            "runId": row["run_id"],
            "phase": row["phase"],
            "contentDigest": row["content_digest"],
            "expiresAt": row["expires_at"].isoformat(),
            "requiredApprovals": 2,
            "votes": [{"actorId": v["actor_id"], "decision": v["decision"]} for v in votes],
            "proposal": row["payload"],
            "snapshot": json.loads(bytes(row["snapshot"])),
            "result": row["result"],
        }
        validate_contract("RemoteGitView", result)
        return result

    def get(self, principal, project, operation_id):
        with self.db.transaction(principal.tenant_id) as conn:
            return self._view(conn, self._locked(conn, principal, project, operation_id))

    def propose(self, principal, project, run_id, checkout_id, data, key):
        validate_contract("RemoteGitProposalInput", data)
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise DomainError("VAL-0003", "Idempotency-Key required", 422)
        request_hash = digest(
            {
                "actor": principal.subject_id,
                "run": run_id,
                "checkout": checkout_id,
                "epoch": self.db.recovery_epoch,
                **data,
            }
        )
        repo = self._repository(data["alias"], project)
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            lock_run(conn, run_id, project)
            actor = self._actor(conn, principal, project)
            prior = conn.execute(
                "SELECT * FROM inv.git_operations WHERE project_id=%s AND requester_id=%s AND key=%s",
                (project, principal.subject_id, key),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise DomainError("IDEM-0001", "Git proposal key has different content")
                return self._view(conn, prior)
            checkout = self.editor._scope(
                conn, principal, project, run_id, checkout_id, writing=True
            )
            current, revision = checkout_snapshot(conn, self.workspace.working, root_fd, checkout)
            if (
                revision != data["expectedRevision"]
                or hashlib.sha256(current).hexdigest() != data["expectedSha256"]
            ):
                raise DomainError("GRAPH-0003", "Workspace changed before Git proposal")
        # Read pinned objects, outside all locks. No remote mutation at proposal time.
        base, _ = repo.snapshot(data["commit"], checkout["workspace_id"])
        raw = base if data["mode"] == "pull" else export_snapshot(current, checkout["workspace_id"])
        changes = (
            GitHubRepository.changes(base, raw, checkout["workspace_id"])
            if data["mode"] == "push"
            else None
        )
        if data["mode"] == "push" and not any(changes.values()):
            raise DomainError("VAL-0003", "Git proposal contains no file changes", 422)
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            checkout = self.editor._scope(
                conn, principal, project, run_id, checkout_id, writing=True
            )
            actor = self._actor(conn, principal, project)
            self._repository(data["alias"], project, repo.fingerprint)
            observed, current_revision = checkout_snapshot(
                conn, self.workspace.working, root_fd, checkout
            )
            if current_revision != revision or observed != current:
                raise DomainError("GRAPH-0003", "Workspace changed during remote observation")
            prior = conn.execute(
                "SELECT * FROM inv.git_operations WHERE project_id=%s AND requester_id=%s AND key=%s",
                (project, principal.subject_id, key),
            ).fetchone()
            if prior:
                if prior["request_hash"] != request_hash:
                    raise DomainError("IDEM-0001", "Git proposal key has different content")
                return self._view(conn, prior)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            operation_id = str(uuid4())
            gate_version = conn.execute("SELECT version FROM inv.tenant_controls").fetchone()[
                "version"
            ]
            payload = {
                **data,
                "repository": repo.repository,
                "branch": repo.branch,
                "repositoryFingerprint": repo.fingerprint,
                "workspaceId": checkout["workspace_id"],
                "snapshotSha256": hashlib.sha256(raw).hexdigest(),
                "changes": changes,
                "operationId": operation_id,
                "requesterId": principal.subject_id,
                "requesterPersonId": str(actor["person_id"]),
                "projectId": project,
                "runId": run_id,
                "checkoutId": checkout_id,
                "recoveryEpoch": self.db.recovery_epoch,
                "gateVersion": gate_version,
                "expiresAt": (now + timedelta(minutes=5)).isoformat(),
            }
            row = conn.execute(
                """INSERT INTO inv.git_operations(tenant_id,operation_id,project_id,run_id,checkout_id,key,requester_id,requester_person_id,recovery_epoch,gate_version,request_hash,content_digest,payload,snapshot,created_at,expires_at,remote_scope)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    principal.tenant_id,
                    operation_id,
                    project,
                    run_id,
                    checkout_id,
                    key,
                    principal.subject_id,
                    actor["person_id"],
                    self.db.recovery_epoch,
                    gate_version,
                    request_hash,
                    digest(payload),
                    Jsonb(payload),
                    raw,
                    now,
                    now + timedelta(minutes=5),
                    digest({"repository": repo.repository.lower(), "branch": repo.branch}),
                ),
            ).fetchone()
            event(
                conn,
                principal.tenant_id,
                run_id,
                "inv.git.proposed",
                {"operationId": operation_id, "contentDigest": row["content_digest"]},
            )
            return self._view(conn, row)

    def vote(self, principal, project, operation_id, data):
        validate_contract("RemoteGitVoteInput", data)
        with self.db.transaction(principal.tenant_id) as conn:
            row = self._locked(conn, principal, project, operation_id)
            actor = self._actor(conn, principal, project, voting=True)
            if (
                actor["person_id"] == row["requester_person_id"]
                or data["contentDigest"] != row["content_digest"]
            ):
                raise DomainError(
                    "AUTH-0071", "Independent person and exact Git digest required", 403
                )
            prior = conn.execute(
                "SELECT * FROM inv.git_votes WHERE operation_id=%s AND actor_id=%s",
                (row["operation_id"], principal.subject_id),
            ).fetchone()
            if prior:
                if (
                    prior["decision"] != data["decision"]
                    or prior["content_digest"] != data["contentDigest"]
                ):
                    raise DomainError("IDEM-0001", "Git vote is immutable")
                return self._view(conn, row)
            self._fresh(conn, row)
            if (
                conn.execute(
                    "SELECT count(*) AS n FROM inv.git_votes WHERE operation_id=%s",
                    (row["operation_id"],),
                ).fetchone()["n"]
                >= 32
            ):
                raise DomainError("RES-0007", "Git vote capacity reached", 409)
            conn.execute(
                "INSERT INTO inv.git_votes(tenant_id,operation_id,actor_id,person_id,decision,content_digest) VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    principal.tenant_id,
                    row["operation_id"],
                    principal.subject_id,
                    actor["person_id"],
                    data["decision"],
                    data["contentDigest"],
                ),
            )
            if data["decision"] == "reject":
                row = conn.execute(
                    "UPDATE inv.git_operations SET phase='rejected' WHERE operation_id=%s RETURNING *",
                    (row["operation_id"],),
                ).fetchone()
            event(
                conn,
                principal.tenant_id,
                row["run_id"],
                "inv.git.voted",
                {
                    "operationId": operation_id,
                    "decision": data["decision"],
                    "actorId": principal.subject_id,
                },
            )
            return self._view(conn, row)

    def apply(self, principal, project, operation_id):
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            row = self._locked(conn, principal, project, operation_id)
            if row["requester_id"] != principal.subject_id:
                raise DomainError("AUTH-0071", "Original Git requester required", 403)
            if row["phase"] in {"dispatched", "completed"}:
                return self._view(conn, row)  # Never resend an ambiguous publication.
            repo = self._fresh(conn, row)
            checkout = self.editor._scope(
                conn, principal, project, row["run_id"], str(row["checkout_id"]), writing=True
            )
            current, revision = checkout_snapshot(conn, self.workspace.working, root_fd, checkout)
            payload = row["payload"]
            if (
                revision != payload["expectedRevision"]
                or hashlib.sha256(current).hexdigest() != payload["expectedSha256"]
            ):
                raise DomainError("GRAPH-0003", "Workspace changed after Git approval")
            votes = conn.execute(
                "SELECT * FROM inv.git_votes WHERE operation_id=%s ORDER BY actor_id",
                (row["operation_id"],),
            ).fetchall()
            people = set()
            for vote in votes:
                person = self._actor(
                    conn, Principal(principal.tenant_id, vote["actor_id"]), project, voting=True
                )
                if (
                    vote["decision"] != "approve"
                    or vote["content_digest"] != row["content_digest"]
                    or person["person_id"] != vote["person_id"]
                    or person["person_id"] == row["requester_person_id"]
                ):
                    raise DomainError(
                        "AUTH-0071", "Current independent Git approvals required", 403
                    )
                people.add(person["person_id"])
            if len(people) < 2:
                raise DomainError("AUTH-0071", "Two distinct current Git approvals required", 403)
            if payload["mode"] == "pull":
                conn.execute(
                    """INSERT INTO inv.workspace_edits(tenant_id,project_id,run_id,checkout_id,revision,subject_id,recovery_epoch,content_hash,snapshot)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        principal.tenant_id,
                        project,
                        row["run_id"],
                        row["checkout_id"],
                        revision + 1,
                        principal.subject_id,
                        self.db.recovery_epoch,
                        payload["snapshotSha256"],
                        bytes(row["snapshot"]),
                    ),
                )
                return self._complete(
                    conn,
                    row,
                    {
                        "commit": payload["commit"],
                        "revision": revision + 1,
                        "sha256": payload["snapshotSha256"],
                    },
                )
            if conn.execute(
                "SELECT 1 FROM inv.git_operations WHERE remote_scope=%s AND phase='dispatched'",
                (row["remote_scope"],),
            ).fetchone():
                raise DomainError(
                    "GRAPH-0003", "Earlier remote publication requires reconciliation"
                )
            conn.execute(
                "UPDATE inv.git_operations SET phase='dispatched' WHERE operation_id=%s",
                (row["operation_id"],),
            )
            event(
                conn,
                principal.tenant_id,
                row["run_id"],
                "inv.git.dispatched",
                {"operationId": operation_id, "contentDigest": row["content_digest"]},
            )
        # Exactly one caller reaches here. No retries even on a known rejection.
        try:
            candidate = repo.publish(operation_id, payload["commit"], payload["changes"])
            candidate = repo.reconcile(
                operation_id,
                payload["commit"],
                bytes(row["snapshot"]),
                payload["workspaceId"],
                candidate,
            )
        except Exception:
            return self.get(
                principal, project, operation_id
            )  # phase remains visibly uncertain/dispatched.
        return self._observed(principal, project, operation_id, candidate)

    def reconcile(self, principal, project, operation_id):
        with self.db.transaction(principal.tenant_id) as conn:
            row = self._locked(conn, principal, project, operation_id)
            if row["phase"] == "completed":
                return self._view(conn, row)
            if row["phase"] != "dispatched":
                raise DomainError(
                    "GRAPH-0003", "Only a dispatched Git publication can be reconciled"
                )
            payload = row["payload"]
            repo = self._repository(payload["alias"], project, payload["repositoryFingerprint"])
        candidate = repo.reconcile(
            operation_id, payload["commit"], bytes(row["snapshot"]), payload["workspaceId"]
        )
        return self._observed(principal, project, operation_id, candidate)

    def _observed(self, principal, project, operation_id, candidate):
        with self.db.transaction(principal.tenant_id) as conn:
            row = self._locked(conn, principal, project, operation_id)
            if row["phase"] == "completed":
                return self._view(conn, row)
            if row["phase"] != "dispatched":
                raise DomainError("GRAPH-0003", "Git dispatch state differs")
            # Observation is permitted after kill/expiry. It does not dispatch work.
            return self._complete(
                conn, row, {"commit": candidate, "sha256": row["payload"]["snapshotSha256"]}
            )

    def _complete(self, conn, row, result):
        row = conn.execute(
            "UPDATE inv.git_operations SET phase='completed',result=%s WHERE operation_id=%s RETURNING *",
            (Jsonb(result), row["operation_id"]),
        ).fetchone()
        event(
            conn,
            str(row["tenant_id"]),
            row["run_id"],
            "inv.git.completed",
            {"operationId": str(row["operation_id"]), **result},
        )
        return self._view(conn, row)
