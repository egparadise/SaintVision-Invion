"""Trusted Workspace service adapter: capture, pin and recover actual files.

Only a recovering Run with physical leases released may publish a new restore.
Storage bytes and generation fsync precede DB receipt, so a failed commit can be
retried against the same immutable generation. This does not resume a process,
restore PTY state or grant permission to mount arbitrary host directories.
"""

import hashlib
from psycopg.types.json import Jsonb
from uuid import UUID, uuid5
from .approvals import digest
from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .leases import lock_run
from .object_store import PART_BYTES
from .runs import event
from .snapshots import identity, object_key


def restore_view(run_id, restore_id, workspace_id, generation, sha256, replayed):
    result = {
        "runId": run_id,
        "restoreId": restore_id,
        "workspaceId": workspace_id,
        "generation": generation,
        "sha256": sha256,
        "replayed": replayed,
    }
    validate_contract("WorkspaceRestoreView", result)
    return result


def checkout_view(
    run_id,
    restore_id,
    checkout_id,
    workspace_id,
    generation,
    step_id,
    source_attempt,
    checkpoint_attempt,
    sha256,
    replayed,
):
    result = {
        "runId": run_id,
        "restoreId": restore_id,
        "checkoutId": checkout_id,
        "workspaceId": workspace_id,
        "generation": generation,
        "stepId": step_id,
        "sourceAttempt": source_attempt,
        "checkpointAttempt": checkpoint_attempt,
        "sha256": sha256,
        "replayed": replayed,
    }
    validate_contract("WorkspaceCheckoutView", result)
    return result


class WorkspaceRecovery:
    def __init__(self, snapshots, generations):
        self.snapshots, self.generations = snapshots, generations
        self.db = snapshots.db

    def checkpoint(
        self, tenant, project, run_id, workspace_id, step_id, source, *, proofs, object_id=None
    ):
        # source is an already authorized private directory, never a browser path.
        raw = source.capture(workspace_id)
        object_id = identity(
            object_id
            or uuid5(
                UUID(tenant),
                digest(
                    {
                        "project": project,
                        "run": run_id,
                        "workspace": workspace_id,
                        "step": step_id,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                    }
                ),
            )
        )
        self.snapshots.begin(tenant, project, object_id, hashlib.sha256(raw).hexdigest(), len(raw))
        status = self.snapshots.status(tenant, project, object_id)
        if status["state"] == "uploading":
            for i, offset in enumerate(range(0, len(raw), PART_BYTES)):
                self.snapshots.put_part(
                    tenant, project, object_id, i, raw[offset : offset + PART_BYTES]
                )
        self.snapshots.finalize(tenant, project, object_id)
        # Check project scope explicitly before the existing fenced pin operation.
        with self.db.transaction(tenant) as conn:
            lock_run(conn, run_id, project)
        return self.snapshots.checkpoint(tenant, run_id, step_id, object_id, proofs=proofs)

    def restore(
        self,
        tenant,
        project,
        run_id,
        workspace_id,
        source_attempt,
        step_id,
        restore_id,
        *,
        expected_version,
        authorize=None,
    ):
        restore_id = identity(restore_id)
        validate_contract("WorkspaceId", workspace_id)
        if (
            type(source_attempt) is not int
            or source_attempt < 1
            or not isinstance(step_id, str)
            or not 1 <= len(step_id) <= 200
        ):
            raise DomainError("VAL-0003", "Invalid checkpoint identity", 422)
        request_hash = digest(
            {
                "project": project,
                "run": run_id,
                "workspace": workspace_id,
                "attempt": source_attempt,
                "step": step_id,
                "version": expected_version,
                "epoch": self.db.recovery_epoch,
                "root": [str(self.generations.root), *self.generations.identity],
            }
        )
        with (
            self.generations.locked() as root_fd,
            self.snapshots.provider.locked() as files,
            self.db.transaction(tenant) as conn,
        ):
            run = lock_run(conn, run_id, project)
            if authorize is not None:
                authorize(conn)
            stored = conn.execute(
                "SELECT * FROM inv.workspace_restores WHERE restore_id=%s",
                (restore_id,),
            ).fetchone()
            if stored and stored["request_hash"] != request_hash:
                raise DomainError("IDEM-0001", "Restore identity already differs")
            prior = None
            if stored:
                prior = restore_view(
                    run_id,
                    restore_id,
                    stored["workspace_id"],
                    stored["generation"],
                    stored["content_hash"],
                    True,
                )
            if prior is not None:
                validate_contract("WorkspaceRestoreView", prior)
            if stored is None:
                if (
                    run["state"] != "recovering"
                    or run["version"] != expected_version
                    or source_attempt > run["attempt"]
                ):
                    raise DomainError(
                        "GRAPH-0003", "Restore requires current recovering Run version"
                    )
                if conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                    (run_id,),
                ).fetchone():
                    raise DomainError("LEASE-0003", "Restore awaits physical resource release")
            pin = conn.execute(
                "SELECT object_id FROM inv.checkpoint_objects WHERE project_id=%s AND run_id=%s AND attempt=%s AND step_id=%s",
                (project, run_id, source_attempt, step_id),
            ).fetchone()
            if not pin:
                raise DomainError("RES-0004", "Workspace checkpoint not found", 404)
            obj = self.snapshots._row(conn, project, pin["object_id"])
            if obj["state"] != "ready":
                raise DomainError("STORE-0005", "Workspace checkpoint unavailable")
            raw = files.read(object_key(obj["object_id"]), obj["content_hash"], obj["size_bytes"])
            generation = self.generations.publish(
                root_fd, restore_id, raw, workspace_id, allow_create=stored is None
            )
            if stored is None:
                conn.execute(
                    """INSERT INTO inv.workspace_restores
                    (tenant_id,project_id,run_id,restore_id,workspace_id,source_attempt,step_id,request_hash,generation,content_hash,recovery_epoch)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        tenant,
                        project,
                        run_id,
                        restore_id,
                        workspace_id,
                        source_attempt,
                        step_id,
                        request_hash,
                        generation,
                        obj["content_hash"],
                        self.db.recovery_epoch,
                    ),
                )
                event(
                    conn,
                    tenant,
                    run_id,
                    "inv.workspace.restored",
                    {
                        "restoreId": restore_id,
                        "workspaceId": workspace_id,
                        "sourceAttempt": source_attempt,
                        "stepId": step_id,
                        "sha256": obj["content_hash"],
                    },
                )
            if prior is not None:
                return prior
            return restore_view(
                run_id,
                restore_id,
                workspace_id,
                generation,
                obj["content_hash"],
                False,
            )

    def checkout(
        self,
        tenant,
        project,
        run_id,
        restore_id,
        checkout_id,
        working,
        *,
        expected_version,
        authorize=None,
    ):
        """Prepare writable files and resume cursor; does not grant OS execution.

        The caller must be a project-authorized Workspace adapter. Node mounting,
        fresh command approval, PTY attachment and Git processes use a separate
        admission boundary and cannot infer authority from this receipt.
        """
        restore_id, checkout_id = identity(restore_id), identity(checkout_id)
        if working.identity == self.generations.identity:
            raise DomainError("SEC-0021", "Working and immutable restore roots must differ")
        fingerprint = digest(
            {
                "project": project,
                "run": run_id,
                "restore": restore_id,
                "version": expected_version,
                "epoch": self.db.recovery_epoch,
                "root": [str(working.root), *working.identity],
            }
        )
        with (
            working.locked() as work_fd,
            self.generations.locked() as restored_fd,
            self.snapshots.provider.locked() as files,
            self.db.transaction(tenant) as conn,
        ):
            run = lock_run(conn, run_id, project)
            if authorize is not None:
                authorize(conn)
            stored = conn.execute(
                "SELECT * FROM inv.workspace_checkouts WHERE checkout_id=%s", (checkout_id,)
            ).fetchone()
            if stored and stored["request_hash"] != fingerprint:
                raise DomainError("IDEM-0001", "Checkout identity already differs")
            restored = conn.execute(
                "SELECT * FROM inv.workspace_restores WHERE restore_id=%s AND project_id=%s AND run_id=%s",
                (restore_id, project, run_id),
            ).fetchone()
            if not restored or str(restored["recovery_epoch"]) != self.db.recovery_epoch:
                raise DomainError("STORE-0022", "Current-epoch restore required")
            prior = None
            if stored:
                prior = checkout_view(
                    run_id,
                    restore_id,
                    checkout_id,
                    restored["workspace_id"],
                    stored["generation"],
                    restored["step_id"],
                    stored["source_attempt"],
                    stored["checkpoint_attempt"] or stored["source_attempt"],
                    stored["content_hash"],
                    True,
                )
            if prior is not None:
                validate_contract("WorkspaceCheckoutView", prior)
            if stored is None and (
                run["state"] != "recovering"
                or run["version"] != expected_version
                or restored["source_attempt"] > run["attempt"]
            ):
                raise DomainError("GRAPH-0003", "Checkout requires current recovering attempt")
            if (
                stored is None
                and conn.execute(
                    "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                    (run_id,),
                ).fetchone()
            ):
                raise DomainError("LEASE-0003", "Checkout awaits physical resource release")
            if prior:
                working.inspect_committed(
                    work_fd,
                    stored["generation"],
                    restored["workspace_id"],
                    stored["content_hash"],
                    stored["filesystem_identity"],
                )
                return prior
            pin = conn.execute(
                "SELECT object_id FROM inv.checkpoint_objects WHERE run_id=%s AND attempt=%s AND step_id=%s",
                (run_id, restored["source_attempt"], restored["step_id"]),
            ).fetchone()
            obj = self.snapshots._row(conn, project, pin["object_id"])
            if obj["state"] != "ready" or obj["content_hash"] != restored["content_hash"]:
                raise DomainError("VERIFY-0023", "Restore source content changed")
            raw = files.read(object_key(obj["object_id"]), obj["content_hash"], obj["size_bytes"])
            self.generations.publish(
                restored_fd, restore_id, raw, restored["workspace_id"], allow_create=False
            )
            generation = working.publish(work_fd, checkout_id, raw, restored["workspace_id"])
            filesystem_identity = working.inspect_committed(
                work_fd, generation, restored["workspace_id"], restored["content_hash"]
            )
            conn.execute(
                """INSERT INTO inv.workspace_checkouts(tenant_id,project_id,run_id,checkout_id,restore_id,workspace_id,source_attempt,step_id,recovery_epoch,request_hash,generation,filesystem_identity,content_hash,checkpoint_attempt)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    tenant,
                    project,
                    run_id,
                    checkout_id,
                    restore_id,
                    restored["workspace_id"],
                    run["attempt"],
                    restored["step_id"],
                    self.db.recovery_epoch,
                    fingerprint,
                    generation,
                    Jsonb(filesystem_identity),
                    restored["content_hash"],
                    restored["source_attempt"],
                ),
            )
            event(
                conn,
                tenant,
                run_id,
                "inv.workspace.checkout_prepared",
                {
                    "checkoutId": checkout_id,
                    "workspaceId": restored["workspace_id"],
                    "stepId": restored["step_id"],
                    "sourceAttempt": run["attempt"],
                    "checkpointAttempt": restored["source_attempt"],
                    "sha256": restored["content_hash"],
                },
            )
            return checkout_view(
                run_id,
                restore_id,
                checkout_id,
                restored["workspace_id"],
                generation,
                restored["step_id"],
                run["attempt"],
                restored["source_attempt"],
                restored["content_hash"],
                False,
            )


class WorkspaceRecoveryService:
    """Project-authorized HTTP boundary over the trusted snapshot reader."""

    def __init__(self, recovery, working):
        self.recovery, self.working = recovery, working
        self.control = Control(recovery.db)

    def _authorize(self, principal, project):
        return lambda conn: self.control.grant(conn, principal, project, "can_request")

    def restore(self, principal, project, run_id, restore_id, data):
        validate_contract("WorkspaceRestoreInput", data)
        return self.recovery.restore(
            principal.tenant_id,
            project,
            run_id,
            data["workspaceId"],
            data["sourceAttempt"],
            data["stepId"],
            restore_id,
            expected_version=data["expectedVersion"],
            authorize=self._authorize(principal, project),
        )

    def checkout(self, principal, project, run_id, restore_id, checkout_id, data):
        validate_contract("WorkspaceCheckoutInput", data)
        return self.recovery.checkout(
            principal.tenant_id,
            project,
            run_id,
            restore_id,
            checkout_id,
            self.working,
            expected_version=data["expectedVersion"],
            authorize=self._authorize(principal, project),
        )
