"""Project-scoped browser boundary; trusted workers keep the execution authority."""

from .approvals import ApprovalStore
from .contracts import validate_contract
from .errors import DomainError
from .ids import new_id
from .leases import lock_run, lock_resources
from .reservations import reclaim_unclaimed
from .runs import RunStore, event, public


class Control:
    def __init__(self, database):
        self.db = database
        self.approvals = ApprovalStore(database)
        self.runs = RunStore(database)

    def grant(self, conn, principal, project, permission=None):
        from .business_auth import permission as business_permission

        validate_contract("ProjectId", project)
        row = conn.execute(
            "SELECT * FROM inv.project_grants WHERE project_id=%s AND subject_id=%s FOR SHARE",
            (project, principal.subject_id),
        ).fetchone()
        if (
            not row
            or not row["enabled"]
            or not (row["can_request"] or row["can_approve"])
            or (permission and not row[permission])
        ):
            raise DomainError("AUTH-0030", "Project permission is unavailable", 403)
        business = business_permission(conn, project, principal.subject_id, permission)
        effective = {
            name: bool(row[name] and (business is None or business[name]))
            for name in ("can_request", "can_approve")
        }
        if not any(effective.values()):
            raise DomainError("AUTH-0030", "Project permission is unavailable", 403)
        return effective

    def projects(self, principal):
        with self.db.transaction(principal.tenant_id) as conn:
            items = []
            for row in conn.execute(
                "SELECT project_id FROM inv.project_grants WHERE subject_id=%s AND enabled AND (can_request OR can_approve) ORDER BY project_id LIMIT 200",
                (principal.subject_id,),
            ).fetchall():
                try:
                    self.grant(conn, principal, row["project_id"])
                except DomainError as error:
                    if error.code != "AUTH-0030":
                        raise
                else:
                    items.append({"projectId": row["project_id"]})
            return {"items": items}

    def create(self, principal, project, key):
        with self.db.transaction(principal.tenant_id) as conn:
            # A new business project may not have a kernel row yet. Check its
            # current grant before the ledger's FK write, and on every replay.
            self.grant(conn, principal, project, "can_request")
            prior = self.approvals._ledger(conn, principal, project, "api.run.create", key, {})
            if prior is not None:
                validate_contract("ControlRunView", prior)
                return prior
            from .containment import require_execution

            require_execution(conn)
            row = conn.execute(
                "INSERT INTO inv.runs(tenant_id,project_id,run_id) VALUES(%s,%s,%s) RETURNING *",
                (principal.tenant_id, project, new_id("run")),
            ).fetchone()
            result = public(row)
            validate_contract("ControlRunView", result)
            event(conn, principal.tenant_id, row["run_id"], "inv.run.created", result)
            return self.approvals._save(conn, project, "api.run.create", key, result)

    def get(self, principal, project, run_id):
        validate_contract("RunId", run_id)
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            row = conn.execute(
                "SELECT * FROM inv.runs WHERE project_id=%s AND run_id=%s",
                (project, run_id),
            ).fetchone()
            if not row:
                raise DomainError("RES-0004", "Run not found", 404)
            active = conn.execute(
                """SELECT count(*) AS n FROM inv.resource_leases WHERE released_at IS NULL AND
                (run_id=%s OR run_id IN (SELECT s.run_id FROM inv.shard_commands s JOIN inv.shard_parents p USING(tenant_id,project_id,plan_id) WHERE p.run_id=%s))""",
                (run_id, run_id),
            ).fetchone()["n"]
            result = {**public(row), "resourceReleasePending": bool(active)}
            validate_contract("ControlRunDetail", result)
            return result

    def list_runs(self, principal, project, *, after=None, limit=50):
        if after:
            validate_contract("RunId", after)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise DomainError("VAL-0003", "Invalid page size", 422)
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            rows = conn.execute(
                "SELECT * FROM inv.runs WHERE project_id=%s AND (%s::text IS NULL OR run_id>%s) ORDER BY run_id LIMIT %s",
                (project, after, after, limit + 1),
            ).fetchall()
            result = {
                "items": [public(r) for r in rows[:limit]],
                "nextCursor": rows[limit - 1]["run_id"] if len(rows) > limit else None,
            }
            validate_contract("ControlRunPage", result)
            return result

    def list_approvals(self, principal, project, *, after=None, limit=50, run_id=None):
        from .approvals import view

        if after is not None:
            validate_contract("ApprovalId", after)
        if run_id is not None:
            validate_contract("RunId", run_id)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise DomainError("VAL-0003", "Invalid page size", 422)
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            rows = conn.execute(
                """SELECT * FROM inv.approval_requests WHERE project_id=%s
                AND (%s::text IS NULL OR approval_id>%s)
                AND (%s::text IS NULL OR run_id=%s)
                ORDER BY approval_id LIMIT %s""",
                (project, after, after, run_id, run_id, limit + 1),
            ).fetchall()
            result = {
                "items": [view(row) for row in rows[:limit]],
                "nextCursor": rows[limit - 1]["approval_id"] if len(rows) > limit else None,
            }
            validate_contract("ApprovalPage", result)
            return result

    def get_approval(self, principal, project, approval_id):
        from .approvals import view

        validate_contract("ApprovalId", approval_id)
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            row = conn.execute(
                "SELECT * FROM inv.approval_requests WHERE project_id=%s AND approval_id=%s",
                (project, approval_id),
            ).fetchone()
            if not row:
                raise DomainError("RES-0004", "Approval not found", 404)
            return view(row)

    def shards(self, principal, project, run_id):
        from .shards import ShardRuntime

        validate_contract("RunId", run_id)
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            link = conn.execute(
                "SELECT plan_id FROM inv.shard_parents WHERE project_id=%s AND run_id=%s",
                (project, run_id),
            ).fetchone()
            if not link:
                raise DomainError("RES-0004", "Shard parent not found", 404)
            return ShardRuntime._status(conn, project, link["plan_id"])

    def cancel(self, principal, project, run_id, expected_version, key):
        validate_contract("RunId", run_id)
        if type(expected_version) is not int or not 1 <= expected_version <= 9007199254740991:
            raise DomainError("VAL-0003", "Current integer Run version required", 422)
        with self.db.transaction(principal.tenant_id) as conn:
            parent = conn.execute(
                "SELECT plan_id FROM inv.shard_parents WHERE project_id=%s AND run_id=%s",
                (project, run_id),
            ).fetchone()
        if parent:
            from .shards import ShardRuntime

            result = ShardRuntime(self.db, None).cancel(
                principal,
                project,
                parent["plan_id"],
                key=key,
                expected_parent_version=expected_version,
            )
            parent_result = result["parentRun"]
            validate_contract("ControlRunDetail", parent_result)
            return parent_result
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.approvals._ledger(
                conn,
                principal,
                project,
                "api.run.cancel",
                key,
                {"runId": run_id, "version": expected_version},
            )
            row = lock_run(conn, run_id, project)
            resources = conn.execute(
                "SELECT resource_id FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                (run_id,),
            ).fetchall()
            lock_resources(conn, [r["resource_id"] for r in resources])
            self.grant(conn, principal, project, "can_request")
            if prior is not None:
                validate_contract("ControlRunDetail", prior)
                return prior
            changed = self.runs._transition(
                conn, principal.tenant_id, row, "cancelled", expected_version
            )
            reclaim_unclaimed(
                conn,
                principal.tenant_id,
                {**row, "state": "cancelled"},
                self.db.recovery_epoch,
                reason="cancelled_before_claim",
            )
            if row["state"] != "cancelled":
                event(
                    conn,
                    principal.tenant_id,
                    run_id,
                    "inv.run.cancel_requested",
                    {"runId": run_id, "version": changed["version"]},
                )
            result = {
                **changed,
                "resourceReleasePending": bool(
                    conn.execute(
                        "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
                        (run_id,),
                    ).fetchone()
                ),
            }
            validate_contract("ControlRunDetail", result)
            return self.approvals._save(conn, project, "api.run.cancel", key, result)

    def nodes(self, principal, project):
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            rows = conn.execute(
                "SELECT n.node_id,n.status,n.heartbeat_at FROM inv.nodes n JOIN inv.project_nodes p USING(tenant_id,node_id) WHERE p.project_id=%s AND p.enabled ORDER BY n.node_id LIMIT 200",
                (project,),
            ).fetchall()
            return {
                "items": [
                    {
                        "nodeId": r["node_id"],
                        "status": r["status"],
                        "lastHeartbeatAt": r["heartbeat_at"].isoformat(),
                    }
                    for r in rows
                ]
            }

    def capacity(self, principal, project):
        from .capacity import project_capacity

        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            return project_capacity(conn, project, self.db.recovery_epoch)

    def events(self, principal, project, run_id, cursor=None):
        validate_contract("RunId", run_id)
        prefix = self.db.recovery_epoch + ":" + run_id + ":"
        sequence = 0
        if cursor is not None:
            if (
                not isinstance(cursor, str)
                or not cursor.startswith(prefix)
                or not cursor[len(prefix) :].isascii()
                or not cursor[len(prefix) :].isdigit()
                or len(cursor[len(prefix) :]) > 16
            ):
                raise DomainError("STREAM-0001", "Event cursor scope differs", 409)
            sequence = int(cursor[len(prefix) :])
        with self.db.transaction(principal.tenant_id) as conn:
            self.grant(conn, principal, project)
            row = conn.execute(
                "SELECT event_sequence FROM inv.runs WHERE project_id=%s AND run_id=%s",
                (project, run_id),
            ).fetchone()
            if not row:
                raise DomainError("RES-0004", "Run not found", 404)
            if sequence > row["event_sequence"]:
                raise DomainError("STREAM-0001", "Event cursor is ahead of this Run", 409)
            rows = conn.execute(
                "SELECT event_id,event_type,sequence FROM inv.outbox WHERE run_id=%s AND sequence>%s ORDER BY sequence LIMIT 200",
                (run_id, sequence),
            ).fetchall()
            # No raw outbox payload: it can contain permits, private argv, or data.
            return [
                {
                    "id": prefix + str(r["sequence"]),
                    "eventId": str(r["event_id"]),
                    "eventType": r["event_type"],
                    "runId": run_id,
                    "sequence": r["sequence"],
                }
                for r in rows
            ]
