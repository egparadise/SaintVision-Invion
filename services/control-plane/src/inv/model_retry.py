"""Failed + physically released Run -> fresh measured reservation, at most 3 Runs.

Never transfers a permit or overrides cancellation. Each child needs a new frozen
input, current policy, independent approval and Node admission. Existing placement
and Run locks make creation/lineage/Leases/outbox a single atomic commit.
"""

from dataclasses import asdict
from decimal import Decimal

from .approvals import ApprovalStore, digest
from .containment import require_execution
from .db import BoundDatabase
from .errors import DomainError
from .leases import lock_run
from .model_locality import ModelLocalityStore
from .model_runtime import bound_input
from .placement import PlacementStore
from .runs import RunStore, event
from .scheduler import Request

OPERATION = "model.retry.prepare"


class ModelRetryStore:
    def __init__(self, database, verifier):
        self.db = database
        self.locality = ModelLocalityStore(database, verifier)
        self.auth = ApprovalStore(database)

    def _scope(self, conn, principal, project, parent):
        lineage = conn.execute(
            "SELECT * FROM inv.model_retry_lineage WHERE child_run_id=%s", (parent,)
        ).fetchone()
        root = lineage["root_run_id"] if lineage else parent
        lock_run(conn, root, project)
        run = lock_run(conn, parent, project)
        self.auth._grant(conn, project, principal.subject_id, "can_request")
        require_execution(conn)
        generation = lineage["generation"] + 1 if lineage else 2
        if run["state"] != "failed" or generation > 3:
            raise DomainError(
                "MODEL-0007", "Only failed model Runs within the retry budget may retry", 409
            )
        if conn.execute(
            "SELECT 1 FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL", (parent,)
        ).fetchone():
            raise DomainError("LEASE-0003", "Model retry awaits physical resource release", 409)
        if conn.execute(
            "SELECT 1 FROM inv.model_retry_lineage WHERE parent_run_id=%s", (parent,)
        ).fetchone():
            raise DomainError("MODEL-0003", "Parent already has a model retry", 409)
        binding = bound_input(conn, project, parent)
        if any(
            not l["fencingToken"].startswith(self.db.recovery_epoch + ":")
            for l in binding["input"]["leases"]
        ):
            raise DomainError("LEASE-0004", "Model retry requires epoch reconciliation", 503)
        return run["version"], root, generation, binding

    def prepare(
        self,
        principal,
        project,
        parent,
        request,
        *,
        key,
        policy_version,
        node_ids=None,
        ttl_seconds=30,
    ):
        if not isinstance(request, Request) or not isinstance(request.max_host_load, Decimal):
            raise DomainError("VAL-0003", "Typed measured model request required", 422)
        if node_ids is not None:
            if (
                not isinstance(node_ids, (list, tuple))
                or not 1 <= len(node_ids) <= 32
                or not all(isinstance(n, str) for n in node_ids)
                or len(set(node_ids)) != len(node_ids)
            ):
                raise DomainError("VAL-0003", "Bounded unique model Node set required", 422)
            node_ids = sorted(node_ids)
        # Reject an out-of-scope tenant/project at the authorization boundary
        # before attempting to create an idempotency row for an invisible
        # project.  The main transactions still re-check this grant after the
        # ledger lock, so revocation cannot race this preflight into authority.
        with self.db.transaction(principal.tenant_id) as conn:
            self.auth._grant(conn, project, principal.subject_id, "can_request")
        payload = {
            "parent": parent,
            "request": {**asdict(request), "max_host_load": str(request.max_host_load)},
            "policy": policy_version,
            "nodes": node_ids,
            "ttl": ttl_seconds,
        }
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self.auth._grant(conn, project, principal.subject_id, "can_request")
            if prior is not None:
                return prior
            captured = self._scope(conn, principal, project, parent)
        binding = captured[3]
        observation = self.locality.observe(
            principal, project, binding["model_id"], binding["model_version"]
        )
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self.auth._grant(conn, project, principal.subject_id, "can_request")
            if prior is not None:
                return prior
            if self._scope(conn, principal, project, parent) != captured:
                raise DomainError("MODEL-0007", "Parent model retry authority changed", 409)
            bound = BoundDatabase(self.db, principal.tenant_id, conn)
            runs = RunStore(bound)
            child = runs.create(principal.tenant_id, project)
            for state in ("validated", "planned"):
                child = runs.transition(
                    principal.tenant_id, child["runId"], state, expected_version=child["version"]
                )
            reserved = PlacementStore(bound).reserve(
                principal,
                project,
                child["runId"],
                request,
                key="model-retry:" + digest({"parent": parent, "key": key}),
                policy_version=policy_version,
                node_ids=node_ids,
                ttl_seconds=ttl_seconds,
                model_observation=observation,
            )
            conn.execute(
                """INSERT INTO inv.model_retry_lineage
                (tenant_id,project_id,root_run_id,parent_run_id,child_run_id,generation)
                VALUES(%s,%s,%s,%s,%s,%s)""",
                (principal.tenant_id, project, captured[1], parent, child["runId"], captured[2]),
            )
            result = {
                "rootRunId": captured[1],
                "parentRunId": parent,
                "generation": captured[2],
                "run": child,
                "reservation": reserved,
                "requiresFrozenInputAndApproval": True,
            }
            event(conn, principal.tenant_id, child["runId"], "inv.model.retry_prepared", result)
            return self.auth._save(conn, project, OPERATION, key, result)
