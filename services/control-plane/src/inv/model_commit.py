"""Trusted worker import -> immutable manifest, current grants and existing fences.

No public HTTP endpoint exposes the worker configuration. File I/O is outside
transactions. Replayed success is a read of a durable commitment, never a new
execution permit. Remote possession and runtime execution require their own
signed transport/admission adapters.
"""

import hashlib
import json

import psycopg
from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .business_auth import permission
from .containment import require_execution
from .errors import DomainError
from .leases import assert_fences, lock_resources, lock_run
from .model_manifest import (
    ConfiguredModelVerifier,
    LocationSnapshot,
    canonical,
    manifest_copy,
    rejected,
)
from .runs import event

OPERATION = "model.manifest.commit"


class ModelManifestStore:
    def __init__(self, database, verifier):
        if not isinstance(verifier, ConfiguredModelVerifier):
            raise ValueError("An operator-configured model verifier is required")
        self.db, self.verifier = database, verifier
        self.auth = ApprovalStore(database)

    def _capture(self, conn, principal, project, run_id, body, proofs):
        run = lock_run(conn, run_id, project)
        self.auth._grant(conn, project, principal.subject_id, "can_request")
        owner = permission(conn, project, principal.subject_id, "can_request", linked=True)
        require_execution(conn)
        if run["state"] not in {"running", "verifying"}:
            rejected()
        resources = conn.execute(
            "SELECT resource_id FROM inv.resource_leases WHERE run_id=%s AND released_at IS NULL",
            (run_id,),
        ).fetchall()
        locked = lock_resources(conn, [r["resource_id"] for r in resources])
        assert_fences(conn, run_id, proofs)
        allowed = {r["node_id"] for r in locked.values()}
        node_ids = {r["nodeId"] for r in body["replicas"]}
        if not node_ids <= allowed:
            rejected()
        for node_id in sorted(node_ids):
            node = conn.execute(
                """SELECT status='online' AND recovery_epoch=%s::uuid
                AND heartbeat_at BETWEEN clock_timestamp()-interval '15 seconds' AND clock_timestamp()
                AS available FROM inv.nodes WHERE node_id=%s""",
                (self.db.recovery_epoch, node_id),
            ).fetchone()
            public = conn.execute(
                "SELECT status FROM public.nodes WHERE node_id=%s FOR SHARE", (node_id,)
            ).fetchone()
            if not node or not node["available"] or not public or public["status"] != "active":
                rejected()
        ids = sorted(r["locationId"] for r in body["replicas"])
        hints = conn.execute(
            "SELECT location_id,contribution_id FROM public.data_locations WHERE location_id=ANY(%s)",
            (ids,),
        ).fetchall()
        if len(hints) != len(ids):
            rejected()
        roots = {}
        for root_id in sorted({r["contribution_id"] for r in hints}):
            root = conn.execute(
                """SELECT contribution_id,node_id,status,registered_by_user_id,version
                FROM public.storage_contributions WHERE contribution_id=%s FOR SHARE""",
                (root_id,),
            ).fetchone()
            if (
                not root
                or root["status"] != "active"
                or root["registered_by_user_id"] != owner["userId"]
            ):
                rejected()
            roots[root_id] = root
        replicas = {r["locationId"]: r for r in body["replicas"]}
        snapshots = []
        for location_id in ids:
            row = conn.execute(
                """SELECT location_id,contribution_id,version,relative_path,byte_size,checksum_sha256
                FROM public.data_locations WHERE location_id=%s FOR SHARE""",
                (location_id,),
            ).fetchone()
            if not row or row["contribution_id"] not in roots:
                rejected()
            root, replica = roots[row["contribution_id"]], replicas[location_id]
            shard = body["shards"][replica["shardIndex"]]
            if (
                replica["state"] != "verified"
                or root["node_id"] != replica["nodeId"]
                or row["version"] != replica["locationVersion"]
                or (row["byte_size"], row["checksum_sha256"])
                != (shard["byteLength"], shard["sha256"])
            ):
                rejected()
            snapshots.append(
                LocationSnapshot(
                    location_id,
                    row["version"],
                    row["contribution_id"],
                    root["version"],
                    root["node_id"],
                    row["relative_path"],
                    row["byte_size"],
                    row["checksum_sha256"],
                )
            )
        return (run["version"], run["attempt"]), tuple(snapshots)

    def commit(self, principal, project, run_id, manifest, proofs, *, key):
        body = manifest_copy(manifest)
        try:
            proofs = json.loads(canonical(proofs))
        except (TypeError, ValueError):
            rejected()
        payload = {"runId": run_id, "manifest": body, "fences": proofs}
        # Register the same-key request before I/O; no model is committed here.
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self.auth._grant(conn, project, principal.subject_id, "can_request")
            if prior is not None:
                return prior
            capture = self._capture(conn, principal, project, run_id, body, proofs)
        verified_hash = self.verifier.verify(body, capture[1])
        if verified_hash != hashlib.sha256(canonical(body)).hexdigest():
            rejected()
        try:
            with self.db.transaction(principal.tenant_id) as conn:
                prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
                self.auth._grant(conn, project, principal.subject_id, "can_request")
                if prior is not None:
                    return prior
                if self._capture(conn, principal, project, run_id, body, proofs) != capture:
                    rejected()
                conn.execute(
                    """INSERT INTO inv.model_manifests
                    (tenant_id,project_id,model_id,version,manifest,manifest_sha256,source_run_id,recovery_epoch)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        principal.tenant_id,
                        project,
                        body["modelId"],
                        body["version"],
                        Jsonb(body),
                        verified_hash,
                        run_id,
                        self.db.recovery_epoch,
                    ),
                )
                for replica in body["replicas"]:
                    conn.execute(
                        """INSERT INTO inv.model_shard_locations
                        (tenant_id,project_id,model_id,version,shard_index,location_id,location_version)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            principal.tenant_id,
                            project,
                            body["modelId"],
                            body["version"],
                            replica["shardIndex"],
                            replica["locationId"],
                            replica["locationVersion"],
                        ),
                    )
                result = {
                    "modelId": body["modelId"],
                    "version": body["version"],
                    "manifestHash": verified_hash,
                    "committed": True,
                    "sourceRunId": run_id,
                    "requiresExecutionRevalidation": True,
                }
                event(conn, principal.tenant_id, run_id, "inv.model.manifest_committed", result)
                # INSERT/uniqueness/trigger waits cannot outlive the execution authority.
                assert_fences(conn, run_id, proofs)
                return self.auth._save(conn, project, OPERATION, key, result)
        except psycopg.errors.UniqueViolation:
            raise DomainError("MODEL-0003", "Model version is already committed", 409) from None

    def get(self, principal, project, model_id, version):
        with self.db.transaction(principal.tenant_id) as conn:
            self.auth._grant(conn, project, principal.subject_id, "can_request")
            row = conn.execute(
                """SELECT manifest,manifest_sha256,source_run_id FROM inv.model_manifests
                WHERE project_id=%s AND model_id=%s AND version=%s""",
                (project, model_id, version),
            ).fetchone()
            if not row:
                raise DomainError("MODEL-0004", "Committed model not found", 404)
            return {
                "manifest": row["manifest"],
                "manifestHash": row["manifest_sha256"],
                "sourceRunId": row["source_run_id"],
                "committed": True,
                "requiresExecutionRevalidation": True,
            }
