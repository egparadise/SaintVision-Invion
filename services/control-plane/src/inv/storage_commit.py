"""Owner-authorized read observations, never Run completion or execution approval.

Network and file I/O occur between issue and accept transactions. Existing Run
Evidence is the ledger; requests/consumptions only hold protocol state/references.
"""

import base64
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from uuid import UUID

from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .business_auth import permission
from .contracts import validate_contract
from .errors import DomainError
from .ids import new_id
from .leases import lock_run
from .node_channels import ChannelProof, assert_channel, proof
from .runs import event
from .state import TERMINAL
from .storage_sampling import Challenge, SampleItem, canonical, new_challenge, verify_sample


def refused():
    raise DomainError("VERIFY-0031", "Storage observation authority or catalog changed", 409)


def decode_challenge(value):
    validate_contract("NodeStorageChallenge", value)
    return Challenge(
        **{
            **value,
            "channel": ChannelProof(**value["channel"]),
            "items": tuple(SampleItem(**v) for v in value["items"]),
        }
    )


class StorageSampleStore:
    def __init__(self, database):
        self.db = database

    def _scope(self, conn, principal, project, run_id, contribution):
        run = lock_run(conn, run_id, project)
        ApprovalStore(self.db)._grant(conn, project, principal.subject_id, "can_request")
        owner = permission(conn, project, principal.subject_id, "can_request", linked=True)
        hint = conn.execute(
            "SELECT node_id FROM public.storage_contributions WHERE contribution_id=%s",
            (contribution,),
        ).fetchone()
        if not hint:
            refused()
        node = conn.execute(
            "SELECT * FROM inv.nodes WHERE node_id=%s FOR UPDATE", (hint["node_id"],)
        ).fetchone()
        public = conn.execute(
            "SELECT status FROM public.nodes WHERE node_id=%s FOR SHARE", (hint["node_id"],)
        ).fetchone()
        row = conn.execute(
            """SELECT contribution_id,node_id,status,registered_by_user_id,normalized_path,version
            FROM public.storage_contributions WHERE contribution_id=%s FOR UPDATE""",
            (contribution,),
        ).fetchone()
        if (
            not node
            or str(node["recovery_epoch"]) != self.db.recovery_epoch
            or not public
            or public["status"] != "active"
            or not row
            or row["status"] != "active"
            or row["node_id"] != hint["node_id"]
            or row["registered_by_user_id"] != owner["userId"]
        ):
            refused()
        channel = conn.execute(
            "SELECT * FROM inv.node_channels WHERE node_id=%s", (row["node_id"],)
        ).fetchone()
        if not channel:
            refused()
        binding = proof(channel)
        if binding.recovery_epoch != self.db.recovery_epoch:
            refused()
        assert_channel(conn, binding)
        return run, row, binding

    @staticmethod
    def _items(conn, contribution, limit):
        rows = conn.execute(
            """SELECT location_id,version,relative_path,byte_size,checksum_sha256
          FROM public.data_locations WHERE contribution_id=%s ORDER BY location_id LIMIT %s FOR SHARE""",
            (contribution, limit),
        ).fetchall()
        return tuple(SampleItem(**row) for row in rows)

    def issue(self, principal, project, run_id, contribution, *, request_id, sample=32):
        request_id = str(UUID(request_id))
        if type(sample) is not int or not 1 <= sample <= 32:
            refused()
        with self.db.transaction(principal.tenant_id) as conn:
            run, root, channel = self._scope(conn, principal, project, run_id, contribution)
            previous = conn.execute(
                "SELECT * FROM inv.storage_sample_requests WHERE request_id=%s", (request_id,)
            ).fetchone()
            if previous:
                if previous["sample_limit"] != sample:
                    refused()
                if (
                    previous["run_id"],
                    previous["project_id"],
                    previous["subject_id"],
                    previous["contribution_id"],
                ) != (run_id, project, principal.subject_id, contribution):
                    refused()
                challenge = decode_challenge(previous["challenge"])
                # Never silently renew or change an existing request's nonce.
                self._current(conn, previous, run, root, channel, challenge)
                return challenge
            if run["state"] in TERMINAL or run["state"] == "recovering":
                refused()
            items = self._items(conn, contribution, sample)
            # The count describes the issue snapshot, not a hash of unsampled files.
            count = conn.execute(
                "SELECT count(*) AS n FROM public.data_locations WHERE contribution_id=%s",
                (contribution,),
            ).fetchone()["n"]
            now = int(
                conn.execute("SELECT extract(epoch FROM clock_timestamp()) AS now").fetchone()[
                    "now"
                ]
            )
            challenge = new_challenge(
                channel=channel,
                project_id=project,
                run_id=run_id,
                contribution_id=contribution,
                root_version=root["version"],
                catalogued=count,
                items=items,
                now=now,
            )
            created = conn.execute(
                """INSERT INTO inv.storage_sample_requests
              (tenant_id,request_id,project_id,run_id,subject_id,contribution_id,run_version,attempt,root_path,sample_limit,challenge,challenge_sha256)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING request_id""",
                (
                    principal.tenant_id,
                    request_id,
                    project,
                    run_id,
                    principal.subject_id,
                    contribution,
                    run["version"],
                    run["attempt"],
                    root["normalized_path"],
                    sample,
                    Jsonb(asdict(challenge)),
                    challenge.digest(),
                ),
            ).fetchone()
            if not created:
                refused()
            return challenge

    def _current(self, conn, pending, run, root, channel, challenge):
        if (
            run["state"] in TERMINAL
            or run["state"] == "recovering"
            or (run["version"], run["attempt"]) != (pending["run_version"], pending["attempt"])
            or root["normalized_path"] != pending["root_path"]
            or root["version"] != challenge.root_version
            or channel != challenge.channel
            or challenge.digest() != pending["challenge_sha256"]
            or self._items(conn, pending["contribution_id"], len(challenge.items))
            != challenge.items
        ):
            refused()
        now = int(
            conn.execute("SELECT extract(epoch FROM clock_timestamp()) AS now").fetchone()["now"]
        )
        challenge.validate(now)
        return now

    def accept(self, principal, project, run_id, request_id, envelope, certificate_der):
        request_id = str(UUID(request_id))
        # Bound and copy caller-controlled bytes before entering the write transaction.
        envelope = deepcopy(envelope)
        validate_contract("NodeStorageSignedSample", envelope)
        if type(certificate_der) is not bytes or not 1 <= len(certificate_der) <= 16384:
            refused()
        response_hash = hashlib.sha256(
            canonical(
                {"envelope": envelope, "certificate": base64.b64encode(certificate_der).decode()}
            )
        ).hexdigest()
        with self.db.transaction(principal.tenant_id) as conn:
            # Advisory lookup has no side effects; Run lock serializes all accepts.
            pending = conn.execute(
                "SELECT * FROM inv.storage_sample_requests WHERE request_id=%s", (request_id,)
            ).fetchone()
            if not pending or (pending["project_id"], pending["run_id"], pending["subject_id"]) != (
                project,
                run_id,
                principal.subject_id,
            ):
                refused()
            run, root, channel = self._scope(
                conn, principal, project, run_id, pending["contribution_id"]
            )
            prior = conn.execute(
                "SELECT * FROM inv.storage_sample_consumptions WHERE request_id=%s", (request_id,)
            ).fetchone()
            if prior:
                if prior["response_sha256"] != response_hash:
                    raise DomainError("IDEM-0001", "Storage sample response already differs", 409)
                return {
                    "evidenceId": prior["evidence_id"],
                    "checkId": prior["check_id"],
                    "replayed": True,
                }
            challenge = decode_challenge(pending["challenge"])
            now = self._current(conn, pending, run, root, channel, challenge)
            verified = verify_sample(challenge, envelope, certificate_der=certificate_der, now=now)
            evidence_id, check_id = new_id("evd"), new_id("chk")
            observed = datetime.fromtimestamp(verified.observed_at, timezone.utc)
            evidence = {
                "evidenceId": evidence_id,
                "tenantId": principal.tenant_id,
                "runId": run_id,
                "traceId": hashlib.sha256(("storage:" + request_id).encode()).hexdigest()[:32],
                "timestamp": observed.isoformat(),
                "actorId": principal.subject_id,
                "action": "verify-storage-sample",
                "policyDecisionId": "storage-owner-v1:" + request_id,
                "inputSha256": challenge.digest(),
                "outputSha256": verified.payload_sha256,
                "result": "succeeded" if verified.sample_healthy else "failed",
            }
            validate_contract("EvidenceEnvelope", evidence)
            detail = {
                "scope": "node-storage-sample-v1",
                "requestId": request_id,
                "evidenceId": evidence_id,
                "challenge": pending["challenge"],
                "envelope": envelope,
                "certificateDer": base64.b64encode(certificate_der).decode(),
                "unverifiable": verified.unverifiable,
                "examined": verified.examined,
                "unsampled": verified.unsampled,
                "cataloguedAtIssue": challenge.catalogued,
                "operationalAcceptanceAssessed": False,
            }
            conn.execute(
                "INSERT INTO inv.evidence(tenant_id,run_id,evidence_id,envelope) VALUES(%s,%s,%s,%s)",
                (principal.tenant_id, run_id, evidence_id, Jsonb(evidence)),
            )
            conn.execute(
                """INSERT INTO public.storage_checks(check_id,tenant_id,contribution_id,reachable,sampled_count,mismatch_count,healthy,checked_at,detail)
              VALUES(%s,%s,%s,true,%s,%s,%s,%s,%s)""",
                (
                    check_id,
                    principal.tenant_id,
                    pending["contribution_id"],
                    verified.sampled,
                    verified.mismatches,
                    verified.sample_healthy,
                    observed,
                    Jsonb(detail),
                ),
            )
            conn.execute(
                "INSERT INTO inv.storage_sample_consumptions(tenant_id,request_id,response_sha256,evidence_id,check_id) VALUES(%s,%s,%s,%s,%s)",
                (principal.tenant_id, request_id, response_hash, evidence_id, check_id),
            )
            event(
                conn,
                principal.tenant_id,
                run_id,
                "inv.storage.sample_recorded",
                {
                    "requestId": request_id,
                    "evidenceId": evidence_id,
                    "checkId": check_id,
                    "sampleHealthy": verified.sample_healthy,
                },
            )
            # Check freshness again after any INSERT/trigger wait, while all
            # current authority and catalog locks are still held.
            final_now = int(
                conn.execute("SELECT extract(epoch FROM clock_timestamp()) AS now").fetchone()[
                    "now"
                ]
            )
            verify_sample(challenge, envelope, certificate_der=certificate_der, now=final_now)
            return {"evidenceId": evidence_id, "checkId": check_id, "replayed": False}

    def collect(self, principal, project, run_id, contribution, *, request_id, client, sample=32):
        challenge = self.issue(
            principal, project, run_id, contribution, request_id=request_id, sample=sample
        )
        envelope, certificate = client.storage_sample(challenge.channel, challenge)
        return self.accept(principal, project, run_id, request_id, envelope, certificate)
