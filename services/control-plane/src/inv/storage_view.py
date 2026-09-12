"""Authorized historical sample view; GET never collects or declares current health."""

import base64
import hashlib
from datetime import timezone
from uuid import UUID

from .approvals import ApprovalStore
from .business_auth import permission
from .contracts import validate_contract
from .errors import DomainError
from .storage_commit import decode_challenge
from .storage_sampling import canonical, verify_sample


def invalid():
    raise DomainError("VERIFY-0032", "Stored storage observation is inconsistent", 409)


class StorageObservationView:
    def __init__(self, database):
        self.db = database

    def result(self, principal, project, run_id, request_id):
        try:
            request_id = str(UUID(request_id))
        except (ValueError, TypeError, AttributeError):
            raise DomainError("REQ-0001", "Invalid storage request ID", 400) from None
        with self.db.transaction(principal.tenant_id) as conn:
            # Same lock order as issue/accept. SHARE also prevents observing a
            # request halfway through its accept transaction.
            run = conn.execute(
                "SELECT run_id FROM inv.runs WHERE run_id=%s AND project_id=%s FOR SHARE",
                (run_id, project),
            ).fetchone()
            ApprovalStore(self.db)._grant(conn, project, principal.subject_id, "can_request")
            owner = permission(conn, project, principal.subject_id, "can_request", linked=True)
            pending = conn.execute(
                "SELECT * FROM inv.storage_sample_requests WHERE request_id=%s", (request_id,)
            ).fetchone()
            if (
                not run
                or not pending
                or (pending["project_id"], pending["run_id"], pending["subject_id"])
                != (project, run_id, principal.subject_id)
            ):
                raise DomainError("RES-0004", "Storage request not found", 404)
            root = conn.execute(
                "SELECT registered_by_user_id FROM public.storage_contributions WHERE contribution_id=%s FOR SHARE",
                (pending["contribution_id"],),
            ).fetchone()
            if not root or root["registered_by_user_id"] != owner["userId"]:
                raise DomainError("AUTH-0030", "Storage observation permission unavailable", 403)
            try:
                challenge = decode_challenge(pending["challenge"])
                challenge.validate(challenge.issued_at)
            except DomainError:
                invalid()
            if challenge.digest() != pending["challenge_sha256"] or (
                challenge.channel.tenant_id,
                challenge.project_id,
                challenge.run_id,
                challenge.contribution_id,
            ) != (principal.tenant_id, project, run_id, pending["contribution_id"]):
                invalid()
            now = int(
                conn.execute("SELECT extract(epoch FROM clock_timestamp()) AS now").fetchone()[
                    "now"
                ]
            )
            if challenge.issued_at > now:
                invalid()
            row = conn.execute(
                """SELECT s.response_sha256,s.evidence_id,s.check_id,
                e.run_id AS evidence_run,e.envelope,c.contribution_id,c.checked_at,
                c.healthy,c.reachable,c.sampled_count,c.mismatch_count,c.detail
                FROM inv.storage_sample_consumptions s
                LEFT JOIN inv.evidence e ON (e.tenant_id,e.evidence_id)=(s.tenant_id,s.evidence_id)
                LEFT JOIN public.storage_checks c ON (c.tenant_id,c.check_id)=(s.tenant_id,s.check_id)
                WHERE s.request_id=%s""",
                (request_id,),
            ).fetchone()
            observation = None
            if row:
                observation = self._verified(principal, pending, challenge, row, now)
            result = {
                "requestId": request_id,
                "tenantId": principal.tenant_id,
                "projectId": project,
                "runId": run_id,
                "contributionId": pending["contribution_id"],
                "status": (
                    "recorded" if row else ("expired" if now > challenge.expires_at else "pending")
                ),
                "createdAt": pending["created_at"].isoformat(),
                "expiresAt": challenge.expires_at,
                "currentHealth": "unknown",
                "operationalAcceptanceAssessed": False,
                "observation": observation,
            }
            validate_contract("StorageObservationView", result)
            return result

    @staticmethod
    def _verified(principal, pending, challenge, row, now):
        try:
            detail = row["detail"]
            if any(
                type(detail[k]) is not int
                for k in ("unverifiable", "examined", "unsampled", "cataloguedAtIssue")
            ):
                invalid()
            encoded = detail["certificateDer"]
            if type(encoded) is not str or not 1 <= len(encoded) <= 21848:
                invalid()
            certificate = base64.b64decode(encoded, validate=True)
            if (
                not 1 <= len(certificate) <= 16384
                or base64.b64encode(certificate).decode() != encoded
            ):
                invalid()
            observed = int(row["checked_at"].timestamp())
            if observed > now or row["checked_at"].microsecond:
                invalid()
            verified = verify_sample(
                challenge, detail["envelope"], certificate_der=certificate, now=observed
            )
            response_hash = hashlib.sha256(
                canonical({"envelope": detail["envelope"], "certificate": encoded})
            ).hexdigest()
            evidence = row["envelope"]
            validate_contract("EvidenceEnvelope", evidence)
            if (
                response_hash != row["response_sha256"]
                or row["evidence_run"] != pending["run_id"]
                or row["contribution_id"] != pending["contribution_id"]
                or detail["scope"] != "node-storage-sample-v1"
                or detail["requestId"] != str(pending["request_id"])
                or detail["evidenceId"] != row["evidence_id"]
                or canonical(detail["challenge"]) != canonical(pending["challenge"])
                or detail["operationalAcceptanceAssessed"] is not False
                or row["reachable"] is not True
                or row["healthy"] is not verified.sample_healthy
                or (
                    row["sampled_count"],
                    row["mismatch_count"],
                    detail["unverifiable"],
                    detail["examined"],
                    detail["unsampled"],
                    detail["cataloguedAtIssue"],
                )
                != (
                    verified.sampled,
                    verified.mismatches,
                    verified.unverifiable,
                    verified.examined,
                    verified.unsampled,
                    challenge.catalogued,
                )
                or verified.observed_at != observed
            ):
                invalid()
            expected = {
                "evidenceId": row["evidence_id"],
                "tenantId": principal.tenant_id,
                "runId": pending["run_id"],
                "actorId": pending["subject_id"],
                "action": "verify-storage-sample",
                "policyDecisionId": "storage-owner-v1:" + str(pending["request_id"]),
                "inputSha256": challenge.digest(),
                "outputSha256": verified.payload_sha256,
                "result": "succeeded" if verified.sample_healthy else "failed",
                "traceId": hashlib.sha256(
                    ("storage:" + str(pending["request_id"])).encode()
                ).hexdigest()[:32],
                "timestamp": row["checked_at"].astimezone(timezone.utc).isoformat(),
            }
            if evidence != expected:
                invalid()
            return {
                "evidenceId": row["evidence_id"],
                "checkId": row["check_id"],
                "observedAt": observed,
                "integrityVerified": True,
                "sampleHealthy": verified.sample_healthy,
                "sampled": verified.sampled,
                "mismatches": verified.mismatches,
                "unverifiable": verified.unverifiable,
                "examined": verified.examined,
                "unsampled": verified.unsampled,
            }
        except (KeyError, TypeError, ValueError, AttributeError, DomainError):
            invalid()
