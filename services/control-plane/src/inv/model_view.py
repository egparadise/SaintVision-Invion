"""Current project authority over historical immutable model commitments."""

import hashlib
import re

from .approvals import ApprovalStore
from .business_auth import permission
from .contracts import validate_contract
from .errors import DomainError
from .model_manifest import canonical, manifest_copy


def _validate_identity(model_id, version):
    validate_contract("ModelId", model_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version) or version in {
        "latest", "current", "head"
    }:
        raise DomainError("VAL-0002", "Immutable model version required", 422)


def _checked_manifest(row, model_id, version):
    try:
        body = manifest_copy(row["manifest"])
        if (body["modelId"], body["version"]) != (model_id, version) or (
            hashlib.sha256(canonical(body)).hexdigest() != row["manifest_sha256"]
        ):
            raise ValueError("inconsistent commitment")
        return body
    except (DomainError, ValueError, TypeError, KeyError):
        raise DomainError("MODEL-0001", "Stored model commitment is inconsistent", 409) from None


class ModelCommitObservation:
    def __init__(self, database):
        self.db = database

    def get(self, principal, project, model_id, version):
        _validate_identity(model_id, version)
        with self.db.transaction(principal.tenant_id) as conn:
            # The same grant/business lock order used for model commitment.
            # Keep these SHARE locks until the observation has been validated.
            ApprovalStore(self.db)._grant(conn, project, principal.subject_id, "can_request")
            permission(conn, project, principal.subject_id, "can_request", linked=True)
            row = conn.execute(
                """SELECT manifest,manifest_sha256,source_run_id,committed_at,recovery_epoch
                FROM inv.model_manifests
                WHERE tenant_id=%s AND project_id=%s AND model_id=%s AND version=%s""",
                (principal.tenant_id, project, model_id, version),
            ).fetchone()
            if row is None:
                raise DomainError("MODEL-0004", "Committed model not found", 404)
            body = _checked_manifest(row, model_id, version)
            result = {
                "projectId": project, "modelId": model_id, "version": version,
                "manifestHash": row["manifest_sha256"],
                "sourceRunId": row["source_run_id"],
                "committedAt": row["committed_at"].isoformat(),
                "commitRecoveryEpoch": str(row["recovery_epoch"]),
                "format": body["format"], "totalBytes": body["totalBytes"],
                "shardCount": len(body["shards"]),
                "licensePolicy": body["licensePolicy"], "classification": body["classification"],
                "committed": True, "currentAvailability": "unknown",
                "requiresExecutionRevalidation": True,
            }
            validate_contract("ModelCommitObservation", result)
            return result


class ModelExecutionManifestObservation:
    """Expose the minimum manifest/location projection after current project authorization.

    This is an observation for a business resolver, never an execution permit.  A
    ready replica is reported only when the immutable location version still
    matches the current catalogue and that catalogue has a verified ready copy.
    """

    def __init__(self, database):
        self.db = database

    def get(self, principal, project, model_id, version):
        _validate_identity(model_id, version)
        with self.db.transaction(principal.tenant_id) as conn:
            ApprovalStore(self.db)._grant(conn, project, principal.subject_id, "can_request")
            permission(conn, project, principal.subject_id, "can_request", linked=True)
            row = conn.execute(
                """SELECT manifest,manifest_sha256
                FROM inv.model_manifests
                WHERE tenant_id=%s AND project_id=%s AND model_id=%s AND version=%s""",
                (principal.tenant_id, project, model_id, version),
            ).fetchone()
            if row is None:
                raise DomainError("MODEL-0004", "Committed model not found", 404)
            body = _checked_manifest(row, model_id, version)
            rows = conn.execute(
                """SELECT sl.shard_index,sl.location_id,sl.location_version
                FROM inv.model_shard_locations sl
                WHERE sl.tenant_id=%s AND sl.project_id=%s
                  AND sl.model_id=%s AND sl.version=%s
                ORDER BY sl.shard_index,sl.location_id""",
                (principal.tenant_id, project, model_id, version),
            ).fetchall()
            location_ids = sorted({str(item["location_id"]) for item in rows})
            readiness = {
                item["location_id"]: item
                for item in conn.execute(
                    "SELECT * FROM public.model_location_readiness(%s)",
                    (location_ids,),
                ).fetchall()
            }
            observed_at = conn.execute(
                "SELECT clock_timestamp() AS observed_at"
            ).fetchone()["observed_at"]

            stored = {}
            for item in rows:
                current = readiness.get(str(item["location_id"]))
                identity = (
                    int(item["shard_index"]),
                    str(item["location_id"]),
                    int(item["location_version"]),
                )
                stored[identity] = {
                    "current": None if current is None else int(current["current_version"]),
                    "ready": set() if current is None else set(current["ready_nodes"]),
                }

            manifest_locations = {
                (int(replica["shardIndex"]), replica["locationId"], int(replica["locationVersion"])):
                replica["state"]
                for replica in body["replicas"]
            }
            if set(stored) != set(manifest_locations):
                raise DomainError(
                    "MODEL-0001", "Stored model shard mapping is inconsistent", 409
                )

            locations = []
            materialisable_shards = set()
            for identity in sorted(stored):
                shard_index, location_id, location_version = identity
                current = stored[identity]["current"]
                usable = (
                    manifest_locations[identity] == "verified"
                    and current == location_version
                )
                ready_nodes = sorted(stored[identity]["ready"]) if usable else []
                materialisable = bool(ready_nodes)
                if materialisable:
                    materialisable_shards.add(shard_index)
                locations.append(
                    {
                        "shardIndex": shard_index,
                        "locationId": location_id,
                        "locationVersion": location_version,
                        "readyNodes": ready_nodes,
                        "materialisable": materialisable,
                    }
                )

            shard_indexes = {int(shard["index"]) for shard in body["shards"]}
            if not locations or {location["shardIndex"] for location in locations} != shard_indexes:
                raise DomainError(
                    "MODEL-0001", "Stored model shard mapping is inconsistent", 409
                )
            result = {
                "projectId": project,
                "modelId": model_id,
                "version": version,
                "manifestHash": row["manifest_sha256"],
                "observedAt": observed_at.isoformat(),
                "shards": body["shards"],
                "shardLocations": locations,
                "licensePolicy": body["licensePolicy"],
                "classification": body["classification"],
                "materialisable": materialisable_shards == shard_indexes,
                "executionAuthorized": False,
                "requiresExecutionRevalidation": True,
            }
            validate_contract("ModelExecutionManifestObservation", result)
            return result
