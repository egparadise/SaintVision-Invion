"""Current project CPU/RAM observations -> weighted Explain -> atomic Leases.

This is the canonical reservation adapter, not pool CRUD or locality metadata.
Pool adapters may narrow project_nodes; they cannot introduce unauthorized nodes.
Unmeasured GPU and transfer/locality workloads fail closed until their measured
providers are connected. Explicit project ceilings are required before use.
"""

from dataclasses import asdict
from decimal import Decimal
from .approvals import ApprovalStore, digest
from .capacity import project_capacity
from .contracts import validate_contract
from .control import Control
from .errors import DomainError
from .leases import Allocation, LeaseStore, active_total, lock_resources, lock_run
from .runs import event
from .scheduler import Candidate, Request, place


class PlacementStore:
    def __init__(self, database):
        self.db = database

    def reserve(
        self,
        principal,
        project,
        run_id,
        request,
        *,
        key,
        policy_version,
        node_ids=None,
        pool_version="project-nodes:1",
        ttl_seconds=30
    ):
        if not isinstance(request, Request) or not isinstance(
            request.max_host_load, Decimal
        ):
            raise DomainError("VAL-0003", "Typed placement request required", 422)
        if request.gpu_count or request.min_vram_bytes or request.required_bytes:
            raise DomainError(
                "RES-0008",
                "Measured GPU and locality providers are not configured",
                422,
            )
        if (
            not isinstance(policy_version, str)
            or not 1 <= len(policy_version) <= 200
            or not isinstance(pool_version, str)
            or not 1 <= len(pool_version) <= 200
            or type(ttl_seconds) is not int
            or not 1 <= ttl_seconds <= 300
        ):
            raise DomainError(
                "VAL-0003", "Versioned placement configuration required", 422
            )
        if node_ids is not None:
            if (
                not isinstance(node_ids, (list, tuple))
                or not 1 <= len(node_ids) <= 32
                or not all(isinstance(n, str) for n in node_ids)
                or len(set(node_ids)) != len(node_ids)
            ):
                raise DomainError(
                    "VAL-0003", "Bounded unique pool node set required", 422
                )
            for node in node_ids:
                validate_contract("NodeId", node)
            node_ids = sorted(node_ids)
        material = {
            "run": run_id,
            "request": {**asdict(request), "max_host_load": str(request.max_host_load)},
            "nodes": node_ids,
            "policy": policy_version,
            "pool": pool_version,
            "ttl": ttl_seconds,
        }
        approvals = ApprovalStore(self.db)
        # Early authorization closes before acquiring mutation locks. Recheck
        # below at commit scope in the canonical Node -> grant lock order.
        with self.db.transaction(principal.tenant_id) as conn:
            Control(self.db).grant(conn, principal, project, "can_request")
        with self.db.transaction(principal.tenant_id) as conn:
            prior = approvals._ledger(
                conn, principal, project, "placement.reserve", key, material
            )
            lock_run(conn, run_id, project)
            if prior is not None:
                Control(self.db).grant(conn, principal, project, "can_request")
                return prior
            conn.execute(
                "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE",
                (project,),
            ).fetchone()
            limits = conn.execute(
                "SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE",
                (project,),
            ).fetchone()
            if not limits:
                raise DomainError(
                    "RES-0008", "Provisioned project resource ceilings required", 403
                )
            permitted = [
                r["node_id"]
                for r in conn.execute(
                    "SELECT node_id FROM inv.project_nodes WHERE project_id=%s AND enabled ORDER BY node_id LIMIT 33",
                    (project,),
                ).fetchall()
            ]
            if not permitted or len(permitted) > 32:
                raise DomainError("RES-0003", "Bounded authorized node set unavailable")
            selected_pool = node_ids if node_ids is not None else permitted
            if not set(selected_pool) <= set(permitted):
                raise DomainError(
                    "AUTH-0030", "Pool contains unauthorized project nodes", 403
                )
            resource_ids = [
                r["resource_id"]
                for r in conn.execute(
                    "SELECT resource_id FROM inv.resources WHERE node_id=ANY(%s) AND kind IN ('cpu','memory') ORDER BY resource_id LIMIT 129",
                    (selected_pool,),
                ).fetchall()
            ]
            if not resource_ids or len(resource_ids) > 128:
                raise DomainError(
                    "RES-0003", "Bounded measured resource set unavailable"
                )
            resources = lock_resources(conn, resource_ids)
            # Recheck membership under a row lock after discovering/locking Nodes.
            authorized = [
                r["node_id"]
                for r in conn.execute(
                    "SELECT node_id FROM inv.project_nodes WHERE project_id=%s AND node_id=ANY(%s) AND enabled ORDER BY node_id FOR SHARE",
                    (project, selected_pool),
                ).fetchall()
            ]
            if authorized != sorted(selected_pool):
                raise DomainError("AUTH-0030", "Project node membership changed", 403)
            Control(self.db).grant(conn, principal, project, "can_request")
            capacity = project_capacity(conn, project, self.db.recovery_epoch)
            measured = {
                n["nodeId"]: n
                for n in capacity["nodes"]
                if n["nodeId"] in selected_pool and n["measured"]
            }
            rows = conn.execute(
                """SELECT n.node_id,n.clock_skew_seconds,s.received_at,s.snapshot FROM inv.nodes n
                JOIN inv.node_resource_snapshots s USING(tenant_id,node_id) WHERE n.node_id=ANY(%s) ORDER BY n.node_id""",
                (selected_pool,),
            ).fetchall()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            candidates = []
            for row in rows:
                node = measured.get(row["node_id"])
                if not node:
                    continue
                snapshot = row["snapshot"]
                if snapshot["cpuCapacityMillis"] <= 0:
                    continue
                candidates.append(
                    Candidate(
                        row["node_id"],
                        "online",
                        row["received_at"],
                        node["spare"]["cpuMillis"],
                        node["spare"]["memoryBytes"],
                        (),
                        0,
                        None,
                        Decimal(snapshot["cpuBusyMillis"])
                        / Decimal(snapshot["cpuCapacityMillis"]),
                        clock_skew_seconds=row["clock_skew_seconds"],
                    )
                )
            snapshot_id = digest(
                {
                    "pool": selected_pool,
                    "limitsVersion": limits["version"],
                    "capacity": [measured[n] for n in sorted(measured)],
                    "observations": [
                        {
                            "node": r["node_id"],
                            "receivedAt": r["received_at"].isoformat(),
                            "snapshot": r["snapshot"],
                        }
                        for r in rows
                    ],
                }
            )
            explain = place(
                request,
                candidates,
                now=now,
                snapshot_id=snapshot_id,
                policy_version=policy_version,
            )
            explain["poolVersion"] = pool_version
            explain["projectLimitsVersion"] = limits["version"]
            for node in selected_pool:
                if node not in {c.node_id for c in candidates}:
                    explain["rejected"][node] = [
                        "current_authorized_measurement_unavailable"
                    ]
            allocations = []
            for kind, need in [
                ("cpu", request.cpu_millis),
                ("memory", request.memory_bytes),
            ]:
                for rid in sorted(resources):
                    resource = resources[rid]
                    if (
                        resource["node_id"] != explain["nodeId"]
                        or resource["kind"] != kind
                    ):
                        continue
                    amount = min(
                        need, max(0, resource["offered"] - int(active_total(conn, rid)))
                    )
                    if amount:
                        allocations.append(Allocation(rid, amount))
                        need -= amount
                if need:
                    raise DomainError(
                        "RES-0001", "Measured placement no longer fits offered slices"
                    )
            leases = LeaseStore(self.db)._reserve_locked(
                conn,
                principal.tenant_id,
                project,
                run_id,
                sorted(allocations),
                ttl_seconds,
            )
            result = {"runId": run_id, "placement": explain, "leases": leases}
            event(
                conn, principal.tenant_id, run_id, "inv.run.placement_reserved", result
            )
            return approvals._save(conn, project, "placement.reserve", key, result)
