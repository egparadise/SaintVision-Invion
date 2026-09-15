"""Current project authority over historical immutable model commitments."""

import hashlib
import re

from .approvals import ApprovalStore
from .business_auth import permission
from .contracts import validate_contract
from .errors import DomainError
from .model_manifest import canonical, manifest_copy


class ModelCommitObservation:
    def __init__(self, database):
        self.db = database

    def get(self, principal, project, model_id, version):
        validate_contract("ModelId", model_id)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", version) or version in {
            "latest", "current", "head"
        }:
            raise DomainError("VAL-0002", "Immutable model version required", 422)
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
            try:
                body = manifest_copy(row["manifest"])
                if (body["modelId"], body["version"]) != (model_id, version) or (
                    hashlib.sha256(canonical(body)).hexdigest() != row["manifest_sha256"]
                ):
                    raise ValueError("inconsistent commitment")
            except (DomainError, ValueError, TypeError, KeyError):
                raise DomainError("MODEL-0001", "Stored model commitment is inconsistent", 409) from None
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
