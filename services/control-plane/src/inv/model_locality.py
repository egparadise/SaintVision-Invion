"""Trusted local worker observations, never caller-supplied possession flags.

Reads happen outside database transactions. Reservations bind immutable model
inputs but do not authorize execution. The runtime must revalidate physical bytes
and consume the existing approved/fenced dispatch; no network rates are inferred.
"""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .business_auth import permission
from .containment import require_execution
from .errors import DomainError
from .model_commit import ModelManifestStore, capture_locations
from .model_manifest import ConfiguredModelVerifier, canonical, manifest_copy, rejected


def require_model_admission(conn, run_id):
    if conn.execute("SELECT 1 FROM inv.model_run_inputs WHERE run_id=%s", (run_id,)).fetchone():
        raise DomainError("MODEL-0006", "Model runtime admission is not configured", 422)


def _capture(conn, db, principal, project, body):
    require_execution(conn)
    nodes = sorted({r["nodeId"] for r in body["replicas"]})
    for node in nodes:
        row = conn.execute(
            """SELECT status='online' AND recovery_epoch=%s::uuid
            AND heartbeat_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()
            AS available FROM inv.nodes WHERE node_id=%s FOR SHARE""",
            (db.recovery_epoch, node),
        ).fetchone()
        member = conn.execute(
            "SELECT enabled FROM inv.project_nodes WHERE project_id=%s AND node_id=%s FOR SHARE",
            (project, node),
        ).fetchone()
        public = conn.execute(
            "SELECT status FROM public.nodes WHERE node_id=%s FOR SHARE", (node,)
        ).fetchone()
        if (
            not row
            or not row["available"]
            or not member
            or not member["enabled"]
            or not public
            or public["status"] != "active"
        ):
            rejected()
    ApprovalStore(db)._grant(conn, project, principal.subject_id, "can_request")
    owner = permission(conn, project, principal.subject_id, "can_request", linked=True)
    return capture_locations(conn, owner, body)


@dataclass(frozen=True)
class LocalModelObservation:
    """Internal provider result, not an HTTP input contract or execution permit."""

    tenant: str
    project: str
    subject: str
    epoch: str
    manifest_json: bytes
    manifest_hash: str
    observed_at: datetime
    snapshots: tuple
    verified_nodes: tuple
    rejected_nodes: tuple

    @property
    def reference(self):
        body = json.loads(self.manifest_json)
        return {
            "modelId": body["modelId"],
            "version": body["version"],
            "manifestHash": self.manifest_hash,
            "adapter": "python-files",
            "adapterVersion": "1",
            "mode": "single-node",
        }

    @property
    def total_bytes(self):
        return json.loads(self.manifest_json)["totalBytes"]

    def revalidate(self, conn, db, principal, project, now, required_bytes, selected_pool):
        if (str(principal.tenant_id), project, principal.subject_id, db.recovery_epoch) != (
            self.tenant,
            self.project,
            self.subject,
            self.epoch,
        ) or required_bytes != self.total_bytes:
            raise DomainError("AUTH-0011", "Model observation scope differs", 403)
        if not 0 <= (now - self.observed_at).total_seconds() <= 15:
            raise DomainError("MODEL-0005", "Fresh model locality observation required", 409)
        body = manifest_copy(json.loads(self.manifest_json))
        row = conn.execute(
            "SELECT manifest_sha256 FROM inv.model_manifests WHERE project_id=%s AND model_id=%s AND version=%s",
            (project, body["modelId"], body["version"]),
        ).fetchone()
        if (
            not row
            or row["manifest_sha256"] != self.manifest_hash
            or hashlib.sha256(self.manifest_json).hexdigest() != self.manifest_hash
        ):
            rejected()
        # Only lock Nodes already locked by PlacementStore, preserving its lock order.
        usable = set(self.verified_nodes) & set(selected_pool)
        if not usable:
            rejected()
        body["replicas"] = [r for r in body["replicas"] if r["nodeId"] in usable]
        current = _capture(conn, db, principal, project, body)
        if current != tuple(s for s in self.snapshots if s.node_id in usable):
            rejected()
        return {node: self.total_bytes for node in usable}

    def bind(self, conn, principal, project, run_id, result):
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        if not 0 <= (now - self.observed_at).total_seconds() <= 15:
            raise DomainError("MODEL-0005", "Model observation expired during reservation", 409)
        conn.execute(
            """INSERT INTO inv.model_run_inputs
            (tenant_id,project_id,run_id,model_id,model_version,manifest_sha256,node_id,input)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                principal.tenant_id,
                project,
                run_id,
                self.reference["modelId"],
                self.reference["version"],
                self.manifest_hash,
                result["placement"]["nodeId"],
                Jsonb(
                    {
                        **self.reference,
                        "observedAt": self.observed_at.isoformat(),
                        "leases": result["leases"],
                        "requiresExecutionRevalidation": True,
                    }
                ),
            ),
        )


class ModelLocalityStore:
    def __init__(self, database, verifier):
        if not isinstance(verifier, ConfiguredModelVerifier):
            raise ValueError("Operator-configured full-byte verifier required")
        self.db, self.verifier = database, verifier

    def observe(
        self,
        principal,
        project,
        model_id,
        version,
        *,
        adapter="python-files",
        adapter_version="1",
        mode="single-node",
    ):
        if (adapter, adapter_version, mode) != ("python-files", "1", "single-node"):
            raise DomainError("MODEL-0002", "Measured model execution mode is unavailable", 422)
        committed = ModelManifestStore(self.db, self.verifier).get(
            principal, project, model_id, version
        )
        body = manifest_copy(committed["manifest"])
        if not any(
            r["adapter"] == adapter and r["version"] == adapter_version and mode in r["modes"]
            for r in body["runtimeCompatibility"]
        ):
            rejected()
        snapshots, verified, failures = [], [], []
        # One cumulative budget across all replicas, including failed reads.
        budget = self.verifier.max_read_bytes
        with self.db.transaction(principal.tenant_id) as conn:
            started = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        for node in sorted({r["nodeId"] for r in body["replicas"]}):
            subset = {**body, "replicas": [r for r in body["replicas"] if r["nodeId"] == node]}
            if {r["shardIndex"] for r in subset["replicas"]} != set(range(len(body["shards"]))):
                failures.append((node, "complete_local_copy_unavailable"))
                continue
            if body["totalBytes"] > budget:
                failures.append((node, "verification_budget_exhausted"))
                continue
            budget -= body["totalBytes"]
            try:
                with self.db.transaction(principal.tenant_id) as conn:
                    captured = _capture(conn, self.db, principal, project, subset)
                self.verifier.verify(subset, captured)
                snapshots.extend(captured)
                verified.append(node)
            except DomainError:
                failures.append((node, "current_verified_local_copy_unavailable"))
        if not verified:
            rejected()
        return LocalModelObservation(
            str(principal.tenant_id),
            project,
            principal.subject_id,
            self.db.recovery_epoch,
            canonical(body),
            committed["manifestHash"],
            started,
            tuple(sorted(snapshots, key=lambda s: s.location_id)),
            tuple(verified),
            tuple(failures),
        )
