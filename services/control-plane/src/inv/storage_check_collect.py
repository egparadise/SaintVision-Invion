"""The one public write surface for a signed folder check (card 266).

The pieces this needs have existed for a while and nothing drove them: the node
agent signs a sample at ``POST /v1/storage/sample``, the kernel issues the
challenge, verifies the signature and writes ``public.storage_checks``, and a read
route serves the result. What was missing was a caller-visible, idempotent way to
*start* that, and the consequence was measurable -- the AC-12 item "contributed
folders checked" came out PASS when a project had no folders, and FAIL forever
once it had one, because nothing could record a check.

Why one route and not two
------------------------
``issue()`` and ``accept()`` are **internal steps**. Exposing both would let a
caller issue and vanish, let ``accept`` be called with a different envelope, and --
worst -- create two public key spaces for one operation.

Why three phases
----------------
A kernel transaction forbids network I/O (``db.py``), so the node call cannot sit
inside one. That leaves the ledger response and the observation's writes in
danger of landing in different transactions, and because a node response carries
``observedAt`` and a signature, **two concurrent requests never hold the same
envelope**. If the response were stored after the writes, one of two racing
callers would be refused with ``IDEM-0001`` and a crash between the two commits
would turn a legitimate retry into the same refusal. So:

1. **pre-I/O transaction** -- lock the ledger row, compare the request hash,
   re-check current authority, replay if a response is already stored, otherwise
   issue the challenge and commit;
2. **node I/O** -- outside any transaction, bounded, writing nothing on failure;
3. **final transaction** -- lock the ledger row *first*, re-check current
   authority, and if a response is stored by now **discard the envelope just
   received** and replay it; only when it is absent, judge the envelope and commit
   the consumption, the check, the evidence, the event **and the ledger response
   together**.

Authority before replay
-----------------------
Both replay branches re-check authority **before** returning anything, following
``ApprovalStore.request`` and ``ModelCommit.commit``. Otherwise a subject whose
grant or folder ownership was revoked after the first success would keep
receiving that success forever, and idempotency would be a way around
authorization.

Lock order is fixed: **idempotency -> Run -> contribution**, bounded by the
kernel's lock timeout, whose exhaustion is ``RES-0007`` 503 retryable.
"""

from __future__ import annotations

import uuid

from .approvals import ApprovalStore
from .business_auth import permission as business_permission
from .errors import DomainError
from .storage_commit import StorageSampleStore

#: The ledger's ``operation``. One fixed string for this one route, so a renamed
#: path cannot silently start a new key space.
OPERATION = "storage.sample.collect"

#: The namespace the request id is derived in. **It must never change**: changing
#: it gives every retry in flight a different id, which is exactly the thing the
#: derivation exists to prevent. Generated once for this operation and written
#: here as a literal rather than computed from anything that could drift.
REQUEST_NAMESPACE = uuid.UUID("6f0b6a1e-5a3f-5d4b-9c21-7f1d2e4a8b03")

#: The tuple separator. Bare concatenation would make ("ab", "c") and ("a", "bc")
#: the same input, so the five values are joined with a byte that cannot occur in
#: any of them.
SEPARATOR = "\x1f"

#: ``issue()``'s own ceiling, repeated here so the route refuses a larger sample
#: before anything is locked rather than deep inside the protocol.
MAX_SAMPLE = 32


def derive_request_id(*, tenant_id, project_id, run_id, key) -> str:
    """The protocol's ``request_id``, derived rather than minted or stored.

    ``inv.idempotency`` has no column for it and its hash covers client-canonical
    inputs only, so a minted id could not be reproduced by a retry -- the retry's
    hash would differ and a legitimate retry would be refused. Deriving it from
    the scope and the key means every attempt recomputes the same UUID with
    nothing persisted and no state machine.
    """
    if not isinstance(key, str) or not 1 <= len(key) <= 200:
        raise DomainError("VAL-0003", "Idempotency key is required", 422)
    name = SEPARATOR.join(
        (str(tenant_id).lower(), str(project_id), str(run_id), OPERATION, key)
    )
    return str(uuid.uuid5(REQUEST_NAMESPACE, name))


class StorageCheckCollector:
    """Drive the three phases. Owns no rules the two halves already own."""

    #: Read by the route so the ceiling has one source rather than two.
    MAX_SAMPLE = MAX_SAMPLE

    def __init__(self, database, client):
        self.db = database
        self.client = client
        self.samples = StorageSampleStore(database)
        self.auth = ApprovalStore(database)

    # ------------------------------------------------------------------ authority
    def _authority(self, conn, principal, project, contribution):
        """What must hold **now**, before any answer -- stored or fresh.

        Three things, and the refusal differs by what the answer would disclose:

        * the authenticated principal is this request's, never the subject the
          ledger row remembers;
        * the project grant is read now, so a revoked ``can_request`` and an
          archived project both refuse with ``AUTH-0030`` 403 -- the caller named
          that project in the path, so nothing is disclosed by saying so;
        * the contribution must be this tenant's, in this project's reach, owned by
          this subject and active. Absent, foreign, re-owned and deactivated are
          **one** ``RES-0004`` 404, because distinguishing them would say that
          somebody else's contribution id exists.

        No Run lock: this is the question "may this subject see this answer", and a
        replay writes nothing. Whether a *new* observation may be recorded is the
        Run's question, and ``_scope`` asks it on the write path.
        """
        # The project side first: a revoked grant and an archived project are both
        # AUTH-0030 403 here, and ``_grant`` is the same check the rest of this lane
        # uses rather than a second copy of the rule.
        self.auth._grant(conn, project, principal.subject_id, "can_request")
        granted = business_permission(conn, project, principal.subject_id, "can_request")
        # Then the contribution side. One query, one answer: absent, another
        # tenant's, re-owned and deactivated are indistinguishable from here on.
        row = conn.execute(
            """SELECT status, registered_by_user_id
                 FROM public.storage_contributions
                WHERE contribution_id=%s AND tenant_id=%s""",
            (contribution, principal.tenant_id),
        ).fetchone()
        if (
            not row
            or row["status"] != "active"
            or row["registered_by_user_id"] != granted["userId"]
        ):
            raise DomainError("RES-0004", "Storage contribution not found", 404)
        return granted

    # --------------------------------------------------------------- the three phases
    def collect(self, principal, project, run_id, *, contribution, key, sample=MAX_SAMPLE):
        """One synchronous collect, idempotent on ``key``.

        Returns the stored response unchanged on a replay, so a retry is
        indistinguishable from the first success except that nothing was written.
        """
        if type(sample) is not int or not 1 <= sample <= MAX_SAMPLE:
            raise DomainError("VAL-0003", "Sample limit out of range", 422)
        request_id = derive_request_id(
            tenant_id=principal.tenant_id, project_id=project, run_id=run_id, key=key
        )
        # Client-canonical only. Nothing the server derived may enter this hash, or
        # the first retry could not reproduce it.
        payload = {
            "projectId": project,
            "runId": run_id,
            "contributionId": contribution,
            "sampleLimit": sample,
        }

        # --- 1. pre-I/O: ledger, authority, replay-or-issue, then commit.
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self._authority(conn, principal, project, contribution)
            if prior is not None:
                return prior, True
            challenge = self.samples.issue(
                principal, project, run_id, contribution, request_id=request_id, sample=sample
            )

        # --- 2. node I/O, outside every transaction. Writes nothing on failure.
        envelope, certificate = self.client.storage_sample(challenge.channel, challenge)
        envelope, response_hash = self.samples.bound_envelope(envelope, certificate)

        # --- 3. final: ledger lock, authority, then replay or one atomic write.
        with self.db.transaction(principal.tenant_id) as conn:
            prior = self.auth._ledger(conn, principal, project, OPERATION, key, payload)
            self._authority(conn, principal, project, contribution)
            if prior is not None:
                # A concurrent request already won. Its answer is the answer; the
                # envelope this call just received is dropped rather than recorded.
                return prior, True
            outcome, context = self.samples.locked_sample_authority(
                conn,
                principal,
                project,
                run_id,
                request_id,
                envelope=envelope,
                certificate_der=certificate,
                response_hash=response_hash,
            )
            if outcome == "replay":
                result = context
            else:
                result = self.samples.apply_sample(conn, principal, run_id, context)
            response = {
                "checkId": result["checkId"],
                "evidenceId": result["evidenceId"],
                "requestId": request_id,
                "contributionId": contribution,
            }
            # The response joins the five writes in **this** transaction. That is
            # the whole point of the phase: they commit together or not at all.
            self.auth._save(conn, project, OPERATION, key, response)
            return response, False


def configured_storage_sample_collector(database, configuration):
    """Build the collector from explicit, operator-supplied mTLS material.

    Fail-closed in both directions. A deployment that does not configure this gets
    no collector and the route answers ``SYS-0001`` 503, and a node agent started
    without its own ``--storage-policy`` answers 503 to the sample call -- so the
    two ends refuse independently and neither one's absence is recorded as a check.

    The three paths are read from the configuration, never guessed, and a missing
    or non-string value is a configuration error rather than a default.
    """
    if not isinstance(configuration, dict):
        raise ValueError("Storage sample configuration must be an object")
    missing = [
        name for name in ("caFile", "certificateFile", "keyFile")
        if not isinstance(configuration.get(name), str) or not configuration[name]
    ]
    if missing:
        raise ValueError("Storage sample TLS material incomplete: " + ", ".join(missing))
    from .node_transport import NodeTLSClient

    client = NodeTLSClient(
        ca_file=configuration["caFile"],
        certificate_file=configuration["certificateFile"],
        key_file=configuration["keyFile"],
    )
    return StorageCheckCollector(database, client)
