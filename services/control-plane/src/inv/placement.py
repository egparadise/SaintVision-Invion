"""Current project CPU/RAM observations -> weighted Explain -> atomic Leases.

This is the canonical reservation adapter, not pool CRUD or locality metadata.
Pool adapters may narrow project_nodes; they cannot introduce unauthorized nodes.
Unmeasured GPU and transfer/locality workloads fail closed until their measured
providers are connected. Explicit project ceilings are required before use.
"""

from dataclasses import asdict
from decimal import Decimal
from time import perf_counter_ns
from .approvals import ApprovalStore, digest
from .capacity import project_capacity
from .contracts import validate_contract
from .control import Control
from .db import mark_statement_phase, record_placement_metric
from .errors import DomainError
from .leases import Allocation, LeaseStore, active_total, lock_resources, lock_run
from .runs import event
from .scheduler import Candidate, Request, place


class _StalePlacement(Exception):
    """Internal optimistic-validation signal; never crosses the API boundary."""


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
        ttl_seconds=30,
        model_observation=None,
    ):
        if not isinstance(request, Request) or not isinstance(request.max_host_load, Decimal):
            raise DomainError("VAL-0003", "Typed placement request required", 422)
        from .model_locality import LocalModelObservation

        if model_observation is not None and not isinstance(
            model_observation, LocalModelObservation
        ):
            raise DomainError("VAL-0003", "Trusted model observation required", 422)
        if (
            request.gpu_count
            or request.min_vram_bytes
            or (request.required_bytes and model_observation is None)
        ):
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
            raise DomainError("VAL-0003", "Versioned placement configuration required", 422)
        if node_ids is not None:
            if (
                not isinstance(node_ids, (list, tuple))
                or not 1 <= len(node_ids) <= 32
                or not all(isinstance(n, str) for n in node_ids)
                or len(set(node_ids)) != len(node_ids)
            ):
                raise DomainError("VAL-0003", "Bounded unique pool node set required", 422)
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
        if model_observation is not None:
            material["modelInput"] = model_observation.reference
        approvals = ApprovalStore(self.db)
        lease_store = LeaseStore(self.db)
        # Early authorization closes before acquiring mutation locks. Recheck
        # below at commit scope in the canonical Node -> grant lock order.
        with self.db.transaction(principal.tenant_id) as conn:
            Control(self.db).grant(conn, principal, project, "can_request")
        if getattr(self.db, "placement_short_commit", False):
            return self._reserve_short_commit(
                principal,
                project,
                run_id,
                request,
                key=key,
                policy_version=policy_version,
                node_ids=node_ids,
                pool_version=pool_version,
                ttl_seconds=ttl_seconds,
                model_observation=model_observation,
                material=material,
                approvals=approvals,
                lease_store=lease_store,
            )
        with self.db.transaction(principal.tenant_id) as conn:
            prior = approvals._ledger(conn, principal, project, "placement.reserve", key, material)
            run = lock_run(conn, run_id, project)
            if prior is not None:
                Control(self.db).grant(conn, principal, project, "can_request")
                return prior
            if conn.execute(
                "SELECT 1 FROM inv.model_run_inputs WHERE run_id=%s", (run_id,)
            ).fetchone():
                raise DomainError("MODEL-0003", "Run already has a model input reservation", 409)
            lease_store._admit_locked(conn, project, run_id, run=run)
            mark_statement_phase("placement-legacy-lock-scope")
            conn.execute(
                "SELECT project_id FROM inv.projects WHERE project_id=%s FOR NO KEY UPDATE",
                (project,),
            ).fetchone()
            limits = conn.execute(
                "SELECT * FROM inv.project_resource_limits WHERE project_id=%s FOR UPDATE",
                (project,),
            ).fetchone()
            if not limits:
                raise DomainError("RES-0008", "Provisioned project resource ceilings required", 403)
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
                raise DomainError("AUTH-0030", "Pool contains unauthorized project nodes", 403)
            resource_ids = [
                r["resource_id"]
                for r in conn.execute(
                    "SELECT resource_id FROM inv.resources WHERE node_id=ANY(%s) AND kind IN ('cpu','memory') ORDER BY resource_id LIMIT 129",
                    (selected_pool,),
                ).fetchall()
            ]
            if not resource_ids or len(resource_ids) > 128:
                raise DomainError("RES-0003", "Bounded measured resource set unavailable")
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
            locality = {}
            if model_observation is not None:
                locality = model_observation.revalidate(
                    conn, self.db, principal, project, now, request.required_bytes, selected_pool
                )
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
                        locality.get(row["node_id"], 0),
                        None,
                        Decimal(snapshot["cpuBusyMillis"]) / Decimal(snapshot["cpuCapacityMillis"]),
                        clock_skew_seconds=row["clock_skew_seconds"],
                    )
                )
            snapshot_id = digest(
                {
                    "pool": selected_pool,
                    "modelLocality": (
                        None
                        if model_observation is None
                        else {
                            **model_observation.reference,
                            "observedAt": model_observation.observed_at.isoformat(),
                            "localBytes": locality,
                        }
                    ),
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
            if model_observation is not None:
                explain["modelInput"] = {
                    **model_observation.reference,
                    "observedAt": model_observation.observed_at.isoformat(),
                    "requiresExecutionRevalidation": True,
                    "unavailableReplicas": dict(model_observation.rejected_nodes),
                }
            explain["poolVersion"] = pool_version
            explain["projectLimitsVersion"] = limits["version"]
            for node in selected_pool:
                if node not in {c.node_id for c in candidates}:
                    explain["rejected"][node] = ["current_authorized_measurement_unavailable"]
            allocations = []
            for kind, need in [
                ("cpu", request.cpu_millis),
                ("memory", request.memory_bytes),
            ]:
                for rid in sorted(resources):
                    resource = resources[rid]
                    if resource["node_id"] != explain["nodeId"] or resource["kind"] != kind:
                        continue
                    amount = min(need, max(0, resource["offered"] - int(active_total(conn, rid))))
                    if amount:
                        allocations.append(Allocation(rid, amount))
                        need -= amount
                if need:
                    raise DomainError(
                        "RES-0001", "Measured placement no longer fits offered slices"
                    )
            locked_allocations = {
                allocation.resource_id: resources[allocation.resource_id]
                for allocation in allocations
            }
            leases = lease_store._reserve_prepared_locked(
                conn, principal.tenant_id, project, run_id, sorted(allocations), ttl_seconds,
                run=run, limits=limits, resources=locked_allocations,
            )
            result = {"runId": run_id, "placement": explain, "leases": leases}
            if model_observation is not None:
                model_observation.bind(conn, principal, project, run_id, result)
            event(conn, principal.tenant_id, run_id, "inv.run.placement_reserved", result)
            return approvals._save(conn, project, "placement.reserve", key, result)

    def _selected_guard(
        self,
        conn,
        project,
        limits,
        resource_ids,
        *,
        lock_membership=False,
        include_active=False,
    ):
        """Digest final mutable inputs for the selected node/resource set only.

        Active totals are validated by recomputing fit under resource locks.  They
        are optional here so a still-valid winner does not become stale merely
        because another reservation committed between speculation and commit.
        """

        membership_sql = """SELECT p.node_id,p.enabled FROM inv.project_nodes p
            JOIN inv.resources r USING(tenant_id,node_id)
            WHERE p.project_id=%s AND r.resource_id=ANY(%s)
            ORDER BY p.node_id"""
        if lock_membership:
            membership_sql += " FOR SHARE OF p"
        memberships = conn.execute(
            membership_sql,
            (project, sorted(resource_ids)),
        ).fetchall()
        rows = conn.execute(
            """SELECT r.resource_id,r.node_id,r.kind,r.capacity,r.offered,
            coalesce((SELECT sum(l.amount) FROM inv.resource_leases l
              WHERE l.resource_id=r.resource_id AND l.released_at IS NULL),0) AS active,
            n.status,n.heartbeat_at,n.clock_skew_seconds,n.recovery_epoch AS node_epoch,
            s.received_at,s.recovery_epoch AS snapshot_epoch,s.channel_version,s.snapshot,
            c.version AS current_channel_version,c.enabled AS channel_enabled,
            c.certificate_not_after,c.recovery_epoch AS channel_epoch
            FROM inv.resources r JOIN inv.nodes n USING(tenant_id,node_id)
            LEFT JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
            LEFT JOIN inv.node_channels c USING(tenant_id,node_id)
            WHERE r.resource_id=ANY(%s) ORDER BY r.resource_id""",
            (sorted(resource_ids),),
        ).fetchall()

        def scalar(value):
            return value.isoformat() if hasattr(value, "isoformat") else str(value)

        return digest(
            {
                "limits": (
                    None
                    if limits is None
                    else {
                        "version": limits["version"],
                        "cpu": limits["cpu_millis"],
                        "memory": limits["memory_bytes"],
                    }
                ),
                "membership": [
                    [row["node_id"], bool(row["enabled"])] for row in memberships
                ],
                "resources": [
                    {
                        key: (
                            row[key]
                            if row[key] is None or isinstance(row[key], (str, int, bool, dict))
                            else scalar(row[key])
                        )
                        for key in row.keys()
                        if include_active or key != "active"
                    }
                    for row in rows
                ],
            }
        )

    @staticmethod
    def _locked_fit(conn, resources, node_id, request):
        """Recompute exact active fit after selected Node/Resource locks."""

        allocations = []
        for kind, requested in (
            ("cpu", request.cpu_millis),
            ("memory", request.memory_bytes),
        ):
            need = requested
            for resource_id in sorted(resources):
                resource = resources[resource_id]
                if resource["node_id"] != node_id or resource["kind"] != kind:
                    continue
                amount = min(
                    need,
                    max(
                        0,
                        resource["offered"] - int(active_total(conn, resource_id)),
                    ),
                )
                if amount:
                    allocations.append(Allocation(resource_id, amount))
                    need -= amount
            if need:
                raise _StalePlacement()
        return sorted(allocations)

    def _speculate(
        self,
        principal,
        project,
        request,
        *,
        node_ids,
        policy_version,
        pool_version,
        model_observation,
    ):
        """Read and score without writer locks; returns no durable side effects."""

        with self.db.transaction(principal.tenant_id) as conn:
            Control(self.db).grant(conn, principal, project, "can_request")
            limits = conn.execute(
                "SELECT * FROM inv.project_resource_limits WHERE project_id=%s",
                (project,),
            ).fetchone()
            if not limits:
                raise DomainError("RES-0008", "Provisioned project resource ceilings required", 403)
            permitted = [
                row["node_id"]
                for row in conn.execute(
                    "SELECT node_id FROM inv.project_nodes WHERE project_id=%s AND enabled ORDER BY node_id LIMIT 33",
                    (project,),
                ).fetchall()
            ]
            if not permitted or len(permitted) > 32:
                raise DomainError("RES-0003", "Bounded authorized node set unavailable")
            selected_pool = node_ids if node_ids is not None else permitted
            if not set(selected_pool) <= set(permitted):
                raise DomainError("AUTH-0030", "Pool contains unauthorized project nodes", 403)
            resource_rows = conn.execute(
                """SELECT * FROM inv.resources WHERE node_id=ANY(%s)
                AND kind IN ('cpu','memory') ORDER BY resource_id LIMIT 129""",
                (selected_pool,),
            ).fetchall()
            if not resource_rows or len(resource_rows) > 128:
                raise DomainError("RES-0003", "Bounded measured resource set unavailable")
            resources = {row["resource_id"]: row for row in resource_rows}
            capacity = project_capacity(conn, project, self.db.recovery_epoch)
            measured = {
                node["nodeId"]: node
                for node in capacity["nodes"]
                if node["nodeId"] in selected_pool and node["measured"]
            }
            rows = conn.execute(
                """SELECT n.node_id,n.clock_skew_seconds,s.received_at,s.snapshot
                FROM inv.nodes n JOIN inv.node_resource_snapshots s USING(tenant_id,node_id)
                WHERE n.node_id=ANY(%s) ORDER BY n.node_id""",
                (selected_pool,),
            ).fetchall()
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            locality = {}
            if model_observation is not None:
                locality = model_observation.revalidate(
                    conn,
                    self.db,
                    principal,
                    project,
                    now,
                    request.required_bytes,
                    selected_pool,
                )
            candidates = []
            for row in rows:
                node = measured.get(row["node_id"])
                if not node or row["snapshot"]["cpuCapacityMillis"] <= 0:
                    continue
                snapshot = row["snapshot"]
                candidates.append(
                    Candidate(
                        row["node_id"],
                        "online",
                        row["received_at"],
                        node["spare"]["cpuMillis"],
                        node["spare"]["memoryBytes"],
                        (),
                        locality.get(row["node_id"], 0),
                        None,
                        Decimal(snapshot["cpuBusyMillis"])
                        / Decimal(snapshot["cpuCapacityMillis"]),
                        clock_skew_seconds=row["clock_skew_seconds"],
                    )
                )
            snapshot_id = digest(
                {
                    "pool": selected_pool,
                    "modelLocality": (
                        None
                        if model_observation is None
                        else {
                            **model_observation.reference,
                            "observedAt": model_observation.observed_at.isoformat(),
                            "localBytes": locality,
                        }
                    ),
                    "limitsVersion": limits["version"],
                    "capacity": [measured[node] for node in sorted(measured)],
                    "observations": [
                        {
                            "node": row["node_id"],
                            "receivedAt": row["received_at"].isoformat(),
                            "snapshot": row["snapshot"],
                        }
                        for row in rows
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
            if model_observation is not None:
                explain["modelInput"] = {
                    **model_observation.reference,
                    "observedAt": model_observation.observed_at.isoformat(),
                    "requiresExecutionRevalidation": True,
                    "unavailableReplicas": dict(model_observation.rejected_nodes),
                }
            explain["poolVersion"] = pool_version
            explain["projectLimitsVersion"] = limits["version"]
            for node in selected_pool:
                if node not in {candidate.node_id for candidate in candidates}:
                    explain["rejected"][node] = ["current_authorized_measurement_unavailable"]
            allocations = []
            for kind, need in (("cpu", request.cpu_millis), ("memory", request.memory_bytes)):
                for resource_id in sorted(resources):
                    resource = resources[resource_id]
                    if resource["node_id"] != explain["nodeId"] or resource["kind"] != kind:
                        continue
                    amount = min(
                        need,
                        max(0, resource["offered"] - int(active_total(conn, resource_id))),
                    )
                    if amount:
                        allocations.append(Allocation(resource_id, amount))
                        need -= amount
                if need:
                    raise DomainError("RES-0001", "Measured placement no longer fits offered slices")
            resource_ids = [
                resource_id
                for resource_id, resource in resources.items()
                if resource["node_id"] == explain["nodeId"]
                and resource["kind"] in {"cpu", "memory"}
            ]
            return {
                "explain": explain,
                "allocations": sorted(allocations),
                "resourceIds": sorted(resource_ids),
                "guard": self._selected_guard(conn, project, limits, resource_ids),
                "locality": locality,
            }

    def _reserve_short_commit(
        self,
        principal,
        project,
        run_id,
        request,
        *,
        key,
        policy_version,
        node_ids,
        pool_version,
        ttl_seconds,
        model_observation,
        material,
        approvals,
        lease_store,
    ):
        """Optimistic placement with a bounded, selected-resource commit section.

        Stale speculative decisions may be recomputed locally.  Database
        contention is deliberately fail-fast so the existing RES-0007 response
        reaches the caller without multiplying pressure on the limit row.
        """

        for attempt in range(1, 4):
            try:
                speculative = self._speculate(
                    principal,
                    project,
                    request,
                    node_ids=node_ids,
                    policy_version=policy_version,
                    pool_version=pool_version,
                    model_observation=model_observation,
                )
                allocations = speculative["allocations"]
                with self.db.transaction(principal.tenant_id) as conn:
                    # A PlacementStore can be bound to a caller-owned transaction
                    # (for example ModelRetryStore).  The savepoint makes a stale
                    # speculative winner release its locks and ledger insert before
                    # the next attempt instead of accumulating them until the outer
                    # transaction finishes.
                    with conn.transaction():
                        prior = approvals._ledger(
                            conn, principal, project, "placement.reserve", key, material
                        )
                        run = lock_run(conn, run_id, project)
                        if prior is not None:
                            Control(self.db).grant(
                                conn, principal, project, "can_request"
                            )
                            return prior
                        if conn.execute(
                            "SELECT 1 FROM inv.model_run_inputs WHERE run_id=%s", (run_id,)
                        ).fetchone():
                            raise DomainError(
                                "MODEL-0003", "Run already has a model input reservation", 409
                            )
                        lease_store._admit_locked(conn, project, run_id, run=run)
                        wait_started = perf_counter_ns()
                        try:
                            limits = conn.execute(
                                "SELECT * FROM inv.project_resource_limits "
                                "WHERE project_id=%s FOR UPDATE",
                                (project,),
                            ).fetchone()
                        except Exception as error:
                            record_placement_metric(
                                self.db,
                                {
                                    "mode": "placement-limit-row-wait",
                                    "attempt": attempt,
                                    "waitMs": round(
                                        (perf_counter_ns() - wait_started) / 1_000_000,
                                        3,
                                    ),
                                    "outcome": "timeout",
                                    "sqlState": getattr(error, "sqlstate", None),
                                },
                            )
                            raise
                        record_placement_metric(
                            self.db,
                            {
                                "mode": "placement-limit-row-wait",
                                "attempt": attempt,
                                "waitMs": round(
                                    (perf_counter_ns() - wait_started) / 1_000_000,
                                    3,
                                ),
                                "outcome": "acquired",
                                "sqlState": None,
                            },
                        )
                        # Measure lock ownership, not the preceding wait to
                        # acquire the project ceiling row. SQL diagnostics
                        # retain any 55P03/57014 acquisition failure separately.
                        mark_statement_phase("placement-short-commit", attempt=attempt)
                        resources = lock_resources(
                            conn, speculative["resourceIds"]
                        )
                        Control(self.db).grant(conn, principal, project, "can_request")
                        if self._selected_guard(
                            conn,
                            project,
                            limits,
                            list(resources),
                            lock_membership=True,
                        ) != speculative["guard"]:
                            raise _StalePlacement()
                        allocations = self._locked_fit(
                            conn,
                            resources,
                            speculative["explain"]["nodeId"],
                            request,
                        )
                        if model_observation is not None:
                            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
                            locality = model_observation.revalidate(
                                conn,
                                self.db,
                                principal,
                                project,
                                now,
                                request.required_bytes,
                                [speculative["explain"]["nodeId"]],
                            )
                            if locality != {
                                candidate: value
                                for candidate, value in speculative["locality"].items()
                                if candidate == speculative["explain"]["nodeId"]
                            }:
                                raise _StalePlacement()
                        leases = lease_store._reserve_prepared_locked(
                            conn,
                            principal.tenant_id,
                            project,
                            run_id,
                            allocations,
                            ttl_seconds,
                            run=run,
                            limits=limits,
                            resources={
                                allocation.resource_id: resources[allocation.resource_id]
                                for allocation in allocations
                            },
                        )
                        result = {
                            "runId": run_id,
                            "placement": speculative["explain"],
                            "leases": leases,
                        }
                        if model_observation is not None:
                            model_observation.bind(
                                conn, principal, project, run_id, result
                            )
                        event(
                            conn,
                            principal.tenant_id,
                            run_id,
                            "inv.run.placement_reserved",
                            result,
                        )
                        return approvals._save(
                            conn, project, "placement.reserve", key, result
                        )
            except _StalePlacement:
                continue
        raise DomainError(
            "RES-0007",
            "Transaction contention; retry with the same key",
            503,
            retryable=True,
        )
