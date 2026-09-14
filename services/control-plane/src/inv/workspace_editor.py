"""Versioned, bounded editor snapshots; freeze the exact bytes before approval.

An edit appends immutable bytes in PostgreSQL. It never rewrites a user's source
or a committed generation. The next approved Node Step materializes these bytes.
All writers share working-root -> tenant gate -> Run ordering with prepare.
"""

import base64
import binascii
import hashlib
import json
from copy import deepcopy

from .approvals import ApprovalStore
from .containment import require_execution
from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .leases import lock_run
from .runs import event
from .snapshots import identity
from .workspace_files import PrivateTree, canonical, decode_snapshot, portable_path


def checkout_snapshot(conn, working, root_fd, checkout):
    """Caller holds the root and Run locks; all callers see the same editor head."""
    working.inspect_committed(
        root_fd,
        checkout["generation"],
        checkout["workspace_id"],
        checkout["content_hash"],
        checkout["filesystem_identity"],
    )
    row = conn.execute(
        "SELECT * FROM inv.workspace_edits WHERE checkout_id=%s ORDER BY revision DESC LIMIT 1",
        (checkout["checkout_id"],),
    ).fetchone()
    if row:
        if (
            str(row["recovery_epoch"]) != str(checkout["recovery_epoch"])
            or row["project_id"] != checkout["project_id"]
            or row["run_id"] != checkout["run_id"]
        ):
            raise DomainError("AUTH-0011", "Editor snapshot scope differs", 403)
        raw = bytes(row["snapshot"])
        if hashlib.sha256(raw).hexdigest() != row["content_hash"]:
            raise DomainError("VERIFY-0023", "Editor snapshot checksum differs")
        revision = row["revision"]
    else:
        source = PrivateTree(working.root / checkout["generation"] / "files")
        if source.identity != (working.identity[0], checkout["filesystem_identity"][-1]):
            raise DomainError("STORE-0022", "Checkout files were replaced")
        raw, revision = source.capture(checkout["workspace_id"]), 0
    from .workspace_resume import bounded_snapshot

    bounded_snapshot(raw, checkout["workspace_id"])
    return raw, revision


def edited_snapshot(raw, workspace_id, changes):
    manifest, _ = decode_snapshot(raw, workspace_id)
    manifest = deepcopy(manifest)
    files = {f["path"]: f for f in manifest["files"]}
    directories = set(manifest["directories"])
    seen = set()
    for edit in changes:
        path = edit["path"]
        parts = portable_path(path)
        if path.casefold() in seen:
            raise DomainError("VAL-0003", "A path may be edited only once per request", 422)
        seen.add(path.casefold())
        prior = files.get(path)
        if (prior["sha256"] if prior else None) != edit["expectedSha256"]:
            raise DomainError("GRAPH-0003", "File changed; reload before editing")
        if edit["dataBase64"] is None:
            if prior is None:
                raise DomainError("RES-0004", "File to delete is unavailable", 404)
            del files[path]
            continue
        try:
            data = base64.b64decode(edit["dataBase64"], validate=True)
            if base64.b64encode(data).decode() != edit["dataBase64"]:
                raise ValueError()
        except (ValueError, binascii.Error):
            raise DomainError("VAL-0003", "Canonical file bytes required", 422) from None
        files[path] = {
            "path": path,
            "sha256": hashlib.sha256(data).hexdigest(),
            "sizeBytes": len(data),
            "dataBase64": edit["dataBase64"],
            "executable": edit["executable"],
        }
        directories.update("/".join(parts[:n]) for n in range(1, len(parts)))
    manifest["files"] = sorted(files.values(), key=lambda f: f["path"])
    manifest["directories"] = sorted(directories)
    result = canonical(manifest)
    from .workspace_resume import bounded_snapshot

    bounded_snapshot(result, workspace_id)  # Also checks file/dir and case collisions.
    return result


class WorkspaceEditor:
    def __init__(self, workspace):
        self.workspace, self.db = workspace, workspace.db
        self.ledger = ApprovalStore(self.db)

    def _scope(self, conn, principal, project, run_id, checkout_id, *, writing=False):
        run = lock_run(conn, run_id, project)
        required = "can_request" if writing else None
        Control(self.db).grant(conn, principal, project, required)
        business = conn.execute(
            "SELECT 1 FROM inv.business_runs WHERE run_id=%s", (run_id,)
        ).fetchone()
        if business:
            from .business_handoff import scope

            _, _, current = scope(conn, self.db, principal, project, run_id, required)
            if writing and current["status"] != "ready":
                raise DomainError("GRAPH-0003", "Ready Workspace required for editing")
        checkout = conn.execute(
            "SELECT * FROM inv.workspace_checkouts WHERE checkout_id=%s AND project_id=%s AND run_id=%s",
            (identity(checkout_id), project, run_id),
        ).fetchone()
        if not checkout or str(checkout["recovery_epoch"]) != self.db.recovery_epoch:
            raise DomainError("STORE-0022", "Current Workspace checkout required", 404)
        if writing:
            require_execution(conn)
            if run["state"] != "recovering" or run["attempt"] != checkout["source_attempt"]:
                raise DomainError("GRAPH-0003", "Only a stopped recovering checkout is editable")
            if conn.execute(
                "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (run_id,),
            ).fetchone():
                raise DomainError("LEASE-0003", "Editing awaits physical resource release")
            if conn.execute(
                "SELECT 1 FROM public.workspace_edit_locks WHERE workspace_id=%s AND released_at IS NULL",
                (checkout["workspace_id"],),
            ).fetchone():
                raise DomainError("GRAPH-0003", "Workspace editing is stopped for approval")
            if conn.execute(
                "SELECT 1 FROM inv.workspace_resumptions WHERE checkout_id=%s",
                (checkout["checkout_id"],),
            ).fetchone():
                raise DomainError("GRAPH-0003", "Checkout is already frozen for a Step")
        return checkout

    @staticmethod
    def _view(checkout_id, revision, raw):
        result = {
            "checkoutId": str(checkout_id),
            "revision": revision,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "snapshot": json.loads(raw),
        }
        validate_contract("WorkspaceEditView", result)
        return result

    def get(self, principal, project, run_id, checkout_id):
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            checkout = self._scope(conn, principal, project, run_id, checkout_id)
            raw, revision = checkout_snapshot(conn, self.workspace.working, root_fd, checkout)
            return self._view(checkout_id, revision, raw)

    def edit(self, principal, project, run_id, checkout_id, data, key):
        validate_contract("WorkspaceEditInput", data)
        with (
            self.workspace.working.locked() as root_fd,
            self.db.transaction(principal.tenant_id) as conn,
        ):
            prior = self.ledger._ledger(
                conn,
                principal,
                project,
                "workspace.edit",
                key,
                {"runId": run_id, "checkoutId": checkout_id, **data},
            )
            checkout = self._scope(
                conn, principal, project, run_id, checkout_id, writing=prior is None
            )
            # Replays still need current write authority, even after freezing.
            Control(self.db).grant(conn, principal, project, "can_request")
            if prior is not None:
                if conn.execute(
                    "SELECT 1 FROM inv.business_runs WHERE run_id=%s", (run_id,)
                ).fetchone():
                    from .business_handoff import scope

                    scope(conn, self.db, principal, project, run_id, "can_request")
                return prior
            raw, revision = checkout_snapshot(conn, self.workspace.working, root_fd, checkout)
            if (
                revision != data["expectedRevision"]
                or hashlib.sha256(raw).hexdigest() != data["expectedSha256"]
            ):
                raise DomainError("GRAPH-0003", "Editor revision changed; reload before editing")
            raw = edited_snapshot(raw, checkout["workspace_id"], data["changes"])
            result = self._view(checkout_id, revision + 1, raw)
            conn.execute(
                """INSERT INTO inv.workspace_edits(tenant_id,project_id,run_id,checkout_id,revision,subject_id,recovery_epoch,content_hash,snapshot)
                         VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    principal.tenant_id,
                    project,
                    run_id,
                    checkout["checkout_id"],
                    revision + 1,
                    principal.subject_id,
                    self.db.recovery_epoch,
                    result["sha256"],
                    raw,
                ),
            )
            event(
                conn,
                principal.tenant_id,
                run_id,
                "inv.workspace.edited",
                {"checkoutId": checkout_id, "revision": revision + 1, "sha256": result["sha256"]},
            )
            return self.ledger._save(conn, project, "workspace.edit", key, result)
