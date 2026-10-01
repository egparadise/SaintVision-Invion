"""Recording a release acceptance: two people, in this order (S12-BE, #282 §3, §4, §8).

The order is the security property. §4 fixes it for every write route, and the reason
each step is where it is matters more than the list:

0. **the prerequisite gate, before anything else.** Not enabled, or a prerequisite
   missing, and the request is refused with ``SYS-0003`` having touched nothing -- no
   ledger receipt, no proposal, no audit row. The gate is first precisely so a disabled
   surface cannot be probed for whether a key, a release or a proposal exists (§0-1.5),
   and it covers the two GETs as well, which have no ledger to reserve;
1. **identity, freshness and permission, from the token and the live rows.** Before the
   ledger, because a replay must be re-authorised too: a receipt is not a capability,
   and a key whose first use was permitted does not stay permitted after the grant is
   revoked;
2. **the idempotency lock and ledger, keyed on the path IDs as well as the endpoint.**
   Reusing one key against another release or proposal is a conflict, not a replay;
3. **the manifest row, locked**, and its digest compared with what the caller claims;
4. **the coordination slot**, which is where two simultaneous proposals become one;
5. **the references**, re-resolved against the authoritative registries;
6. **the rows and the audit event in the same transaction**, then the receipt.

**Why writes remain closed by default.** Card 188 supplies verified fresh-auth claims and
card 194 binds the target/Evidence resolver, but neither card flips the deployment-owned
``INV_RELEASE_ACCEPTANCE_WRITE_ENABLED`` flag. The implementation can therefore be tested
at its real seams while a deployment still refuses every write until its operator has
installed all prerequisites and deliberately enables it.

The resolver is a seam rather than caller-value comparison: production now holds
``DatabaseReferenceResolver`` and tests can still inject ``UnboundReferenceResolver`` to
prove the independent half of the gate. Nothing below treats caller refs as authority.
"""

from __future__ import annotations

import base64
import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session

from ..db.models import (
    AcceptanceRecord,
    ReleaseAcceptanceLifecycleEvent,
    ReleaseAcceptanceProposal,
    ReleaseAcceptanceSlot,
    ReleaseAcceptanceVote,
    ReleaseAcceptanceWithdrawal,
    ReleaseManifest,
)
from ..db.session import actor_scope
from ..errors import (
    AUTH_PROJECT_SCOPE,
    GRAPH_INVALID_TRANSITION,
    RES_RELEASE_NOT_FOUND,
    VAL_SCHEMA,
    InvError,
)
from ..ids import is_id, new_id
from . import audit as audit_service
from . import release_acceptance_auth as fresh
from . import release_acceptance_digest as digest
from . import release_acceptance_policy as policy
from . import release_sign_off
from . import settings as settings_service

#: The six audit actions §8 allows, and no seventh. A closed set, so a new kind of
#: event is a contract change rather than a string somebody added.
AUDIT_PROPOSED = "release.acceptance.proposed"
AUDIT_RECORDED = "release.acceptance.recorded"
AUDIT_CONFIRMED = "release.acceptance.confirmed"
AUDIT_INVALIDATED = "release.acceptance.proposal_invalidated"
AUDIT_WITHDRAWN = "release.acceptance.withdrawn"
AUDIT_DENIED = "release.acceptance.denied"
#: ``audit_events.outcome`` is ``varchar(8)`` over a closed set, and this feature writes
#: two of its three members: five actions that happened, and the one refusal that is a
#: committed fact rather than a rolled-back error (§8). ``error`` belongs to a request that
#: did not reach a decision, which this service never records -- such a request raises and
#: the canonical handler answers.
AUDIT_OUTCOMES = frozenset({"allow", "deny"})

AUDIT_ACTIONS = frozenset(
    {
        AUDIT_PROPOSED,
        AUDIT_RECORDED,
        AUDIT_CONFIRMED,
        AUDIT_INVALIDATED,
        AUDIT_WITHDRAWN,
        AUDIT_DENIED,
    }
)

#: The permission, and the only one. A project role, a token scope and a UI role are
#: none of them this (§2-2).
PERMISSION = "releases.accept"

#: The page §3 allows for pending proposals.
PENDING_PAGE_MAX = 100
PENDING_STATE = "pending_second_operator"


@dataclass(frozen=True)
class Refused:
    """A refusal the caller is told about **after** the transaction commits.

    §4 and §5 are explicit that an expired proposal and a superseded manifest are not
    errors to roll back: the proposal really did expire, the slot really is empty, and
    those are rows to keep. Raising was the first implementation and Codex measured what
    it did -- the ``InvError`` propagated through the route, ``get_write_session``'s
    ``with session.begin()`` rolled the whole transaction back, and the lifecycle event,
    the cleared slot, the audit row and the idempotency receipt all disappeared. The
    caller then saw a 409 describing a state the database had never reached.

    So the service returns this instead of raising, the route stores it as the receipt and
    returns it as a response, and the commit happens because nothing threw.
    """

    status: int
    code: str
    detail: str
    #: For a log and a test, never for the response body.
    reason: str


@dataclass(frozen=True)
class Outcome:
    """What a write produced: a body to serialise, or a refusal to commit and return."""

    status: int
    body: dict[str, Any] | None = None
    refused: Refused | None = None


#: The fields that make two decision requests the same decision (§4 convergence). Not the
#: proposal digest: that binds ``expiresAt``, which is the proposer's own fresh-auth
#: window, so two operators sending identical bodies would never match on it.
_SAME_DECISION_FIELDS = (
    "acceptance_id_ref",
    "outcome",
    "target_manifest_sha256",
    "reason_code",
)


def _same_decision(proposal: ReleaseAcceptanceProposal, request: Any) -> bool:
    """Whether this request is the proposal that already exists.

    Compares the content an operator reviewed, in order, including the reference lists --
    their order carries meaning, so a reordered list is a different decision and gets the
    conflict rather than the receipt.
    """
    if proposal.acceptance_id_ref != request.acceptance_id_ref:
        return False
    if request.outcome != "accepted" or proposal.outcome != "accepted":
        return False
    if str(proposal.target_manifest_sha256) != request.target_manifest_sha256:
        return False
    if proposal.reason_code != request.reason_code:
        return False
    targets = [
        {"targetId": item.target_id, "targetSha256": item.target_sha256}
        for item in request.target_refs
    ]
    measurements = [
        {
            "evidenceId": item.evidence_id,
            "evidenceSha256": item.evidence_sha256,
            "observedAt": digest.format_instant(item.observed_at),
        }
        for item in request.measurement_refs
    ]
    return (
        list(proposal.target_refs or []) == targets
        and list(proposal.measurement_refs or []) == measurements
        and list(proposal.known_limitations or []) == list(request.known_limitations)
    )


def _proposal_body(proposal: ReleaseAcceptanceProposal, *, replayed: bool) -> dict[str, Any]:
    return {
        "proposalId": proposal.proposal_id,
        "releaseId": proposal.release_id,
        "acceptanceIdRef": proposal.acceptance_id_ref,
        "outcome": "accepted",
        "state": PENDING_STATE,
        "targetManifestSha256": proposal.target_manifest_sha256,
        "proposalDigest": proposal.proposal_digest,
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": proposal.expires_at,
        "replayed": replayed,
    }


def _recorded_body(decision: AcceptanceRecord, *, replayed: bool) -> dict[str, Any]:
    accepted = decision.outcome == "accepted"
    return {
        "acceptanceId": decision.acceptance_id,
        "releaseId": decision.release_id,
        "acceptanceIdRef": decision.acceptance_id_ref,
        "outcome": decision.outcome,
        "state": "recorded",
        "acceptedManifestSha256": decision.accepted_manifest_sha256,
        "manifestMatches": True,
        "decisionSignOff": accepted,
        "decisionConfirmationCount": 2 if accepted else 1,
        "decidedAt": decision.decided_at,
        "replayed": replayed,
    }


class PrerequisitesUnavailable(Exception):
    """The surface is registered and not usable. ``SYS-0003`` / 503 / not retryable.

    Not retryable because retrying cannot deploy an identity provider mapper or bind a
    registry. The reason is for a log; the response says the same sentence to everyone.
    """


class ReferencesUnresolvable(Exception):
    """A target or measurement reference does not resolve. ``GRAPH-0003`` / 409."""


class ReferenceNotFound(Exception):
    """A scoped release, binding, or Evidence row is absent. ``RES-0004`` / 404."""


class ReferenceRetryable(Exception):
    """A resolver DB lock/deadlock/statement timeout. ``RES-0007`` / 503."""


class ReferenceResolver(Protocol):
    """Binds declared references to rows and blobs the server owns (§3-1)."""

    @property
    def bound(self) -> bool: ...

    def resolve(
        self,
        session: Session,
        *,
        tenant_id: uuid.UUID,
        release_id: str,
        target_refs: list[Any],
        measurement_refs: list[Any],
    ) -> Any: ...


@dataclass(frozen=True)
class UnboundReferenceResolver:
    """What the application holds today: nothing to resolve against, so it refuses.

    Deliberately not "resolve by comparing the caller's values", which §3-1 names as
    the implementation that must not exist. A reference the caller both supplies and
    verifies is a reference nobody checked.
    """

    bound: bool = False

    def resolve(self, session, *, tenant_id, release_id, target_refs, measurement_refs):
        raise ReferencesUnresolvable(
            "no authoritative target or Evidence registry is bound in this build"
        )


UNBOUND_RESOLVER = UnboundReferenceResolver()


def _require_resolution_criterion(resolution: Any, acceptance_id_ref: str) -> None:
    """Bind a resolver result to the criterion the write is about.

    A successful resolver call is not enough: as the target registry grows, returning
    a different criterion must not authorize this proposal or confirmation.
    """

    if getattr(resolution, "acceptance_id_ref", None) != acceptance_id_ref:
        raise ReferencesUnresolvable("the resolved target does not match the acceptance criterion")


def active_resolver() -> ReferenceResolver:
    """The resolver this deployment holds.

    A function rather than a module constant read directly, so tests can substitute an
    explicitly unbound resolver and prove the second half of the prerequisite gate.
    """
    from .release_acceptance_resolver import RESOLVER

    return RESOLVER


# ----------------------------------------------------------------------- step 0: the gate


def require_prerequisites(*, enabled: bool, resolver: ReferenceResolver = UNBOUND_RESOLVER) -> None:
    """The first thing every one of the five routes does, GETs included.

    Two conditions, one answer. Separating them in the response would tell an
    unauthenticated caller which part of the deployment is missing, and §7 already
    decided that errors do not describe the deployment.
    """
    if not enabled:
        raise PrerequisitesUnavailable("the release acceptance write surface is not enabled")
    if not resolver.bound:
        raise PrerequisitesUnavailable(
            "no authoritative target or Evidence registry is bound in this build"
        )


# ------------------------------------------------------- step 1: person, freshness, grant


def require_fresh_operator(
    session: Session, *, principal, now: dt.datetime
) -> fresh.FreshAuthProof:
    """A recently authenticated interactive human holding ``releases.accept``.

    Re-read on every request and before every replay. A login-time snapshot of a role
    is not a permission; the row is.

    It also **puts the verified human into the transaction**, which is why every write
    route calls this first. The row-level policies on these tables check that the actor
    column equals ``inv.user_id`` and that the human is active and permitted, so a write
    issued before this call is refused by the database. That is how I found that setting
    the scope only around the confirm function was not enough -- the proposal and vote
    inserts happen earlier in the same transaction. ``SET LOCAL`` lasts for the
    transaction, so one call covers the whole request and ends with it.
    """
    try:
        proof = fresh.proof_of_interactive_human(principal, now=now)
    except fresh.NotInteractiveHuman as error:
        # §7: a 403 does not distinguish stale fresh-auth from a missing permission.
        raise InvError(
            AUTH_PROJECT_SCOPE, "fresh interactive operator authentication is required"
        ) from error
    settings_service.require_global_administrator(
        session, tenant_id=principal.tenant_id, user_id=principal.user_id, permission=PERMISSION
    )
    # Entered and left immediately: the SET LOCAL it issues belongs to the transaction,
    # not to this block, which is the property the policies rely on.
    with actor_scope(session, principal.user_id):
        pass
    return proof


# ----------------------------------------------------------------- steps 3-8: the writes


def _locked_release(session: Session, *, tenant_id: uuid.UUID, release_id: str) -> ReleaseManifest:
    release = session.scalars(
        select(ReleaseManifest)
        .where(ReleaseManifest.tenant_id == tenant_id, ReleaseManifest.release_id == release_id)
        .with_for_update()
    ).one_or_none()
    if release is None:
        # §7: existence is not disclosed. Another tenant's release and a release that
        # was never recorded are the same answer.
        raise InvError(RES_RELEASE_NOT_FOUND, "release manifest not found")
    return release


def _required_criterion(release: ReleaseManifest, acceptance_id_ref: str) -> policy.PolicyRegistry:
    loaded = policy.load(
        pinned_sha256=release.policy_registry_sha256, pinned_version=release.policy_version
    )
    if not loaded.usable:
        raise InvError(GRAPH_INVALID_TRANSITION, "the release pins no usable policy registry")
    if acceptance_id_ref not in loaded.names():
        # §5-1: a decision about a criterion the registry does not require is refused
        # rather than recorded, because it would look like progress on sign-off.
        raise InvError(
            GRAPH_INVALID_TRANSITION, "this criterion is not required by the pinned policy"
        )
    return loaded


def _slot(
    session: Session, *, tenant_id: uuid.UUID, release_id: str, acceptance_id_ref: str
) -> ReleaseAcceptanceSlot:
    """The criterion's coordination row, created once and then locked.

    ``INSERT ... ON CONFLICT DO NOTHING`` then ``SELECT ... FOR UPDATE``: two
    simultaneous first proposals both try to create it, one wins, and both then wait on
    the same row. Creating it inside the transaction that needs it means there is no
    separate provisioning step that could be forgotten.
    """
    session.execute(
        text(
            "INSERT INTO release_acceptance_slots(slot_id,tenant_id,release_id,"
            "acceptance_id_ref,updated_at) VALUES(:s,:t,:r,:c,now()) "
            "ON CONFLICT (tenant_id,release_id,acceptance_id_ref) DO NOTHING"
        ),
        {"s": new_id("acceptance_slot"), "t": tenant_id, "r": release_id, "c": acceptance_id_ref},
    )
    return session.scalars(
        select(ReleaseAcceptanceSlot)
        .where(
            ReleaseAcceptanceSlot.tenant_id == tenant_id,
            ReleaseAcceptanceSlot.release_id == release_id,
            ReleaseAcceptanceSlot.acceptance_id_ref == acceptance_id_ref,
        )
        .with_for_update()
    ).one()


def _audit(
    session: Session,
    *,
    principal,
    action: str,
    detail: dict[str, Any],
    now: dt.datetime,
    outcome: str = "allow",
) -> str:
    if action not in AUDIT_ACTIONS:
        raise ValueError(f"{action} is not one of the six allowed acceptance audit actions")
    # ``allow``/``deny``, never ``succeeded``: the column is varchar(8) over a closed set,
    # so a value outside it is a failed INSERT in the middle of a request rather than a
    # mislabelled row. Checked here so the refusal is a ValueError at the call site.
    if outcome not in AUDIT_OUTCOMES:
        raise ValueError(f"{outcome} is not one of the allowed acceptance audit outcomes")
    return audit_service.record_event(
        session,
        now=now,
        actor_type="user",
        actor_id=principal.user_id,
        action=action,
        outcome=outcome,
        tenant_id=principal.tenant_id,
        target_type="release_manifest",
        target_id=detail.get("releaseId"),
        detail=detail,
    )


def propose_or_record(
    session: Session,
    *,
    principal,
    release_id: str,
    request: Any,
    proof: fresh.FreshAuthProof,
    resolver: ReferenceResolver,
    now: dt.datetime,
) -> Outcome:
    """``accepted`` opens a proposal; ``conditional`` and ``rejected`` are final at once.

    The asymmetry is the contract's: only ``accepted`` claims something about the world
    that two people should have checked. A hedge and a refusal are one person's
    statement, and requiring a second person to agree to a refusal would mean one person
    cannot refuse.
    """
    release = _locked_release(session, tenant_id=principal.tenant_id, release_id=release_id)
    loaded = _required_criterion(release, request.acceptance_id_ref)
    if str(release.manifest_sha256) != request.target_manifest_sha256:
        # Stale target, not malformed input: the caller accepted a composition this
        # release no longer has (§5).
        raise InvError(GRAPH_INVALID_TRANSITION, "the release composition has changed")
    resolution = resolver.resolve(
        session,
        tenant_id=principal.tenant_id,
        release_id=release_id,
        target_refs=list(request.target_refs),
        measurement_refs=list(request.measurement_refs),
    )
    _require_resolution_criterion(resolution, request.acceptance_id_ref)
    slot = _slot(
        session,
        tenant_id=principal.tenant_id,
        release_id=release_id,
        acceptance_id_ref=request.acceptance_id_ref,
    )

    if request.outcome != "accepted":
        return Outcome(
            status=201,
            body=_record_final(
                session,
                principal=principal,
                release=release,
                slot=slot,
                request=request,
                proof=proof,
                now=now,
            ),
        )
    body = _open_proposal(
        session,
        principal=principal,
        release=release,
        slot=slot,
        request=request,
        proof=proof,
        loaded=loaded,
        now=now,
    )
    return Outcome(status=202, body=body)


def _record_final(
    session: Session, *, principal, release, slot, request, proof, now
) -> dict[str, Any]:
    """A ``conditional`` or ``rejected`` decision: one person, recorded, no sign-off."""
    if slot.active_proposal_id is not None:
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            "this criterion already has a proposal awaiting a second operator",
        )
    if slot.active_acceptance_id is not None:
        # This function used to overwrite the slot's active decision, so a release's
        # sign-off could change with no withdrawal recorded anywhere. The database refuses
        # it too (0057's trigger); this is the refusal that says why in the contract's
        # words rather than as a constraint violation.
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            "this criterion already has an active decision; withdraw it first",
        )
    acceptance_id = new_id("acceptance")
    session.add(
        AcceptanceRecord(
            acceptance_id=acceptance_id,
            tenant_id=principal.tenant_id,
            release_id=release.release_id,
            acceptance_id_ref=request.acceptance_id_ref,
            outcome=request.outcome,
            accepted_manifest_sha256=release.manifest_sha256,
            known_limitations=list(request.known_limitations),
            accepted_by_user_id=principal.user_id,
            decided_at=now,
            attestation_version=proof.attestation_version,
            proposal_id=None,
        )
    )
    session.flush()
    slot.active_acceptance_id = acceptance_id
    slot.updated_at = now
    _audit(
        session,
        principal=principal,
        action=AUDIT_RECORDED,
        detail={
            "releaseId": release.release_id,
            "acceptanceId": acceptance_id,
            "acceptanceIdRef": request.acceptance_id_ref,
            "outcome": request.outcome,
            "manifestSha256": release.manifest_sha256,
            "targetRefCount": len(request.target_refs),
            "measurementRefCount": len(request.measurement_refs),
        },
        now=now,
    )
    return {
        "acceptanceId": acceptance_id,
        "releaseId": release.release_id,
        "acceptanceIdRef": request.acceptance_id_ref,
        "outcome": request.outcome,
        "state": "recorded",
        "acceptedManifestSha256": release.manifest_sha256,
        "manifestMatches": True,
        "decisionSignOff": False,
        "decisionConfirmationCount": 1,
        "decidedAt": now,
        "replayed": False,
    }


def _open_proposal(
    session: Session, *, principal, release, slot, request, proof, loaded, now
) -> dict[str, Any]:
    """An ``accepted`` decision awaiting a distinct second human."""
    if slot.active_proposal_id is not None:
        existing = session.get(ReleaseAcceptanceProposal, slot.active_proposal_id)
        if existing is not None and _same_decision(existing, request):
            # §4's convergence: the same body under a different key is the same decision,
            # so it gets the first proposal's answer and leaves no second vote and no
            # second audit row. Returning a conflict here instead -- which is what this
            # did -- would make a retry whose response was lost unrecoverable: the
            # operator cannot re-send it and cannot confirm it either, because confirming
            # requires having read the proposal they were never told about.
            return _proposal_body(existing, replayed=True)
        raise InvError(
            GRAPH_INVALID_TRANSITION,
            "this criterion already has a different proposal awaiting a second operator",
        )
    expires_at = min(
        proof.window_ends_at, now + dt.timedelta(seconds=fresh.FRESH_AUTH_WINDOW_SECONDS)
    )
    proposal_id = new_id("acceptance_proposal")
    proposal_digest = digest.proposal_digest(
        tenant_id=principal.tenant_id,
        release_id=release.release_id,
        acceptance_id_ref=request.acceptance_id_ref,
        outcome="accepted",
        target_manifest_sha256=release.manifest_sha256,
        policy_version=loaded.policy_version,
        policy_registry_sha256=loaded.registry_sha256,
        reason_code=request.reason_code,
        target_refs=list(request.target_refs),
        measurement_refs=list(request.measurement_refs),
        known_limitations=[],
        expires_at=expires_at,
    )
    session.add(
        ReleaseAcceptanceProposal(
            proposal_id=proposal_id,
            tenant_id=principal.tenant_id,
            release_id=release.release_id,
            acceptance_id_ref=request.acceptance_id_ref,
            outcome="accepted",
            target_manifest_sha256=release.manifest_sha256,
            proposal_digest=proposal_digest,
            reason_code=request.reason_code,
            target_refs=[
                {"targetId": item.target_id, "targetSha256": item.target_sha256}
                for item in request.target_refs
            ],
            measurement_refs=[
                {
                    "evidenceId": item.evidence_id,
                    "evidenceSha256": item.evidence_sha256,
                    "observedAt": digest.format_instant(item.observed_at),
                }
                for item in request.measurement_refs
            ],
            known_limitations=[],
            policy_version=loaded.policy_version,
            policy_registry_sha256=loaded.registry_sha256,
            proposed_by_user_id=principal.user_id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    event_id = _audit(
        session,
        principal=principal,
        action=AUDIT_PROPOSED,
        detail={
            "releaseId": release.release_id,
            "proposalId": proposal_id,
            "acceptanceIdRef": request.acceptance_id_ref,
            "manifestSha256": release.manifest_sha256,
            "proposalDigest": proposal_digest,
            "targetRefCount": len(request.target_refs),
            "measurementRefCount": len(request.measurement_refs),
        },
        now=now,
    )
    session.add(
        ReleaseAcceptanceVote(
            vote_id=new_id("acceptance_vote"),
            tenant_id=principal.tenant_id,
            proposal_id=proposal_id,
            user_id=principal.user_id,
            vote_role="proposer",
            human_attestation_version=proof.attestation_version,
            verified_issuer=proof.issuer,
            verified_client_id=proof.client_id,
            auth_time=proof.auth_time,
            amr_sha256=proof.amr_sha256,
            identity_verification_event_id=event_id,
            created_at=now,
        )
    )
    session.flush()
    slot.active_proposal_id = proposal_id
    slot.updated_at = now
    return {
        "proposalId": proposal_id,
        "releaseId": release.release_id,
        "acceptanceIdRef": request.acceptance_id_ref,
        "outcome": "accepted",
        "state": PENDING_STATE,
        "targetManifestSha256": release.manifest_sha256,
        "proposalDigest": proposal_digest,
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": expires_at,
        "replayed": False,
    }


def _review_payload(proposal: ReleaseAcceptanceProposal) -> dict[str, Any]:
    """Everything a confirmer must read, and no user ID (§3)."""
    return {
        "proposalId": proposal.proposal_id,
        "releaseId": proposal.release_id,
        "acceptanceIdRef": proposal.acceptance_id_ref,
        "outcome": "accepted",
        "state": PENDING_STATE,
        "targetManifestSha256": proposal.target_manifest_sha256,
        "proposalDigest": proposal.proposal_digest,
        "reasonCode": proposal.reason_code,
        "targetRefs": list(proposal.target_refs or []),
        "measurementRefs": list(proposal.measurement_refs or []),
        "knownLimitations": [],
        "requiredDistinctOperatorCount": 2,
        "proposalConfirmationCount": 1,
        "decisionSignOff": False,
        "expiresAt": proposal.expires_at,
    }


def encode_cursor(created_at: dt.datetime, proposal_id: str) -> str:
    """The page's position as one opaque string over **both** sort keys (§3, P1-7).

    The first version filtered on ``proposal_id`` alone while ordering by
    ``(created_at, proposal_id)``. Those two orders are not the same -- a ULID orders by
    the millisecond it was minted, a ``created_at`` by the request's clock -- so a page
    could skip a proposal or show one twice. Both keys travel, and the string is opaque so
    a caller cannot build one by hand and ask for a position the server never issued.
    """
    raw = f"{digest.format_instant(created_at)}|{proposal_id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[dt.datetime, str]:
    """The inverse, strict. A cursor that does not decode is refused, not ignored."""
    if not isinstance(cursor, str) or not 1 <= len(cursor) <= 256:
        raise InvError(VAL_SCHEMA, "cursor is not a page position")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        stamp, _, proposal_id = base64.urlsafe_b64decode(padded).decode("utf-8").partition("|")
        moment = dt.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=dt.timezone.utc
        )
    except (ValueError, TypeError) as error:
        raise InvError(VAL_SCHEMA, "cursor is not a page position") from error
    if not is_id(proposal_id, "acceptance_proposal"):
        raise InvError(VAL_SCHEMA, "cursor is not a page position")
    return moment, proposal_id


def pending_page(
    session: Session, *, tenant_id: uuid.UUID, release_id: str, limit: int, cursor: str | None
) -> dict[str, Any]:
    """Pending proposals a second operator can find without being told an ID.

    Ordered by ``(created_at, proposal_id)`` so the cursor is stable, and bounded at a
    hundred: a confirmer reads proposals, and a page nobody can read is not a page.
    """
    _locked_release(session, tenant_id=tenant_id, release_id=release_id)
    bounded = max(1, min(int(limit), PENDING_PAGE_MAX))
    query = (
        select(ReleaseAcceptanceProposal)
        .join(
            ReleaseAcceptanceSlot,
            (ReleaseAcceptanceSlot.tenant_id == ReleaseAcceptanceProposal.tenant_id)
            & (ReleaseAcceptanceSlot.active_proposal_id == ReleaseAcceptanceProposal.proposal_id),
        )
        .where(
            ReleaseAcceptanceProposal.tenant_id == tenant_id,
            ReleaseAcceptanceProposal.release_id == release_id,
        )
        .order_by(ReleaseAcceptanceProposal.created_at, ReleaseAcceptanceProposal.proposal_id)
        .limit(bounded + 1)
    )
    if cursor:
        # The row-value comparison, so the filter is the same order as the ORDER BY.
        after, last_id = decode_cursor(cursor)
        query = query.where(
            tuple_(ReleaseAcceptanceProposal.created_at, ReleaseAcceptanceProposal.proposal_id)
            > (after, last_id)
        )
    rows = list(session.scalars(query).all())
    page = rows[:bounded]
    return {
        "items": [_review_payload(row) for row in page],
        "nextCursor": (
            encode_cursor(page[-1].created_at, page[-1].proposal_id)
            if len(rows) > bounded and page
            else None
        ),
    }


def pending_proposal(
    session: Session, *, tenant_id: uuid.UUID, release_id: str, proposal_id: str
) -> dict[str, Any]:
    proposal = session.scalars(
        select(ReleaseAcceptanceProposal)
        .join(
            ReleaseAcceptanceSlot,
            (ReleaseAcceptanceSlot.tenant_id == ReleaseAcceptanceProposal.tenant_id)
            & (ReleaseAcceptanceSlot.active_proposal_id == ReleaseAcceptanceProposal.proposal_id),
        )
        .where(
            ReleaseAcceptanceProposal.tenant_id == tenant_id,
            ReleaseAcceptanceProposal.release_id == release_id,
            ReleaseAcceptanceProposal.proposal_id == proposal_id,
        )
    ).one_or_none()
    if proposal is None:
        # Inactive, another tenant's, or never existed: one answer (§3).
        raise InvError(RES_RELEASE_NOT_FOUND, "release acceptance proposal not found")
    return _review_payload(proposal)


def _close_proposal(
    session: Session, *, principal, proposal: ReleaseAcceptanceProposal, kind: str, now
) -> None:
    """Append the terminal event and empty the slot. Committed, then reported as 409.

    §4 is explicit that this is not a rollback: the proposal really did expire or get
    superseded, and that is a fact to record rather than an error to undo.
    """
    session.add(
        ReleaseAcceptanceLifecycleEvent(
            event_id=new_id("acceptance_lifecycle_event"),
            tenant_id=principal.tenant_id,
            proposal_id=proposal.proposal_id,
            event_kind=kind,
            acceptance_id=None,
            occurred_at=now,
        )
    )
    # Flushed before the slot moves, because the slot's trigger asks whether this proposal
    # has been closed and this session does not autoflush: without it the UPDATE runs
    # before the event exists and the database refuses the transition it is part of.
    session.flush()
    session.execute(
        text(
            "UPDATE release_acceptance_slots SET active_proposal_id=NULL, updated_at=:now "
            "WHERE tenant_id=:t AND release_id=:r AND acceptance_id_ref=:c "
            "AND active_proposal_id=:p"
        ),
        {
            "now": now,
            "t": principal.tenant_id,
            "r": proposal.release_id,
            "c": proposal.acceptance_id_ref,
            "p": proposal.proposal_id,
        },
    )
    detail = {
        "releaseId": proposal.release_id,
        "proposalId": proposal.proposal_id,
        "acceptanceIdRef": proposal.acceptance_id_ref,
        "closedReason": kind,
    }
    _audit(session, principal=principal, action=AUDIT_INVALIDATED, detail=detail, now=now)
    # **The denial §8 asks for, written here and nowhere else.**
    #
    # Every call of this function ends in the committed 409 of §5, so the request that
    # closes the proposal is exactly the request that is refused -- and a later request
    # that re-reads an already-closed proposal never arrives here, which is why a replay
    # or a different key adds no second row. The audit stays a count of refusals rather
    # than of retries without anything having to remember who transitioned.
    #
    # Why not the canonical denial boundary. That boundary audits the AC-02 category --
    # ``AUTH``/``SEC`` at 401/403, which ``is_audited_denial`` states and a global test
    # pins -- and this is a ``GRAPH`` 409 that the boundary deliberately does not record.
    # Reaching it would mean widening a security contract for one route. It also could not
    # describe this fact honestly: the only post-response hook above the route is the
    # trace middleware, and that runs *before* ``get_write_session`` commits (measured:
    # route, middleware, teardown), so a row written there would precede the commit it
    # claims to describe and would survive a commit that failed.
    #
    # In this transaction it is atomic with what it describes: the lifecycle event, the
    # emptied slot, the 409 receipt and this row all exist, or none of them do. That is
    # also the rule the repository's one-recorder invariant protects -- a denial must not
    # be left behind by a transaction that rolled back -- met from the other side.
    _audit(
        session,
        principal=principal,
        action=AUDIT_DENIED,
        detail={**detail, "refusedCode": STALE_CODE},
        now=now,
        outcome="deny",
    )


#: The code of that refusal, named before the refusal itself because ``_close_proposal``
#: records it in the audit row and is defined above.
STALE_CODE = "GRAPH-0003"

#: The refusal a closed proposal produces, in one place so the first request and every
#: later one with a different key answer identically (§5).
STALE = Refused(
    status=409,
    code=STALE_CODE,
    detail="The release acceptance state changed before this request was applied.",
    reason="the proposal was closed by expiry or by a superseded manifest",
)


def confirm(
    session: Session,
    *,
    principal,
    release_id: str,
    proposal_id: str,
    request: Any,
    proof: fresh.FreshAuthProof,
    resolver: ReferenceResolver,
    now: dt.datetime,
) -> Outcome:
    """The second operator. The database re-checks everything this function checked.

    Both layers on purpose: this one produces the contract's errors, and the canonical
    function is what holds if a future caller reaches the tables another way.

    Returns an :class:`Outcome` rather than raising for a closed proposal, because that
    refusal has to survive the commit -- see :class:`Refused`.
    """
    release = _locked_release(session, tenant_id=principal.tenant_id, release_id=release_id)
    proposal = session.scalars(
        select(ReleaseAcceptanceProposal).where(
            ReleaseAcceptanceProposal.tenant_id == principal.tenant_id,
            ReleaseAcceptanceProposal.release_id == release_id,
            ReleaseAcceptanceProposal.proposal_id == proposal_id,
        )
    ).one_or_none()
    if proposal is None:
        raise InvError(RES_RELEASE_NOT_FOUND, "release acceptance proposal not found")
    slot = _slot(
        session,
        tenant_id=principal.tenant_id,
        release_id=release_id,
        acceptance_id_ref=proposal.acceptance_id_ref,
    )

    # §4's confirmer race, from the loser's side: the winner's transaction has committed,
    # so this one finds the proposal closed and the decision recorded. It converges on that
    # decision instead of reporting a state error -- two operators who both confirmed the
    # same proposal did not disagree about anything.
    settled = session.scalars(
        select(ReleaseAcceptanceLifecycleEvent).where(
            ReleaseAcceptanceLifecycleEvent.tenant_id == principal.tenant_id,
            ReleaseAcceptanceLifecycleEvent.proposal_id == proposal_id,
        )
    ).all()
    confirmed = next((event for event in settled if event.event_kind == "confirmed"), None)
    if confirmed is not None and confirmed.acceptance_id:
        decision = session.get(AcceptanceRecord, confirmed.acceptance_id)
        if decision is not None:
            return Outcome(status=201, body=_recorded_body(decision, replayed=True))
    if settled:
        # Closed for a reason that produced no decision. The same 409 as the request that
        # closed it, so a different key asking again gets the same answer rather than a
        # fresh attempt at an already-settled proposal.
        return Outcome(status=409, refused=STALE)

    if slot.active_proposal_id != proposal_id:
        raise InvError(GRAPH_INVALID_TRANSITION, "the proposal is no longer awaiting confirmation")
    if now >= proposal.expires_at:
        _close_proposal(session, principal=principal, proposal=proposal, kind="expired", now=now)
        # Committed, then refused: the expiry is a fact, not an error (§4, §5).
        return Outcome(status=409, refused=STALE)
    if str(release.manifest_sha256) != str(proposal.target_manifest_sha256):
        _close_proposal(
            session, principal=principal, proposal=proposal, kind="manifest-superseded", now=now
        )
        return Outcome(status=409, refused=STALE)
    if request.proposal_digest != proposal.proposal_digest:
        raise InvError(GRAPH_INVALID_TRANSITION, "the confirmed digest is not this proposal's")
    if request.target_manifest_sha256 != str(release.manifest_sha256):
        raise InvError(GRAPH_INVALID_TRANSITION, "the release composition has changed")

    # §4 step 6 and step 8, which were missing. The proposal's references are re-resolved
    # against the authoritative registries *here*, not only when the proposal was made:
    # between the two there is a second human and an unbounded gap, and Evidence can be
    # withdrawn in it. Codex measured the gap by deleting the one resolve() call in the
    # decision path and watching 124 focused tests still pass.
    try:
        resolution = resolver.resolve(
            session,
            tenant_id=principal.tenant_id,
            release_id=release_id,
            target_refs=list(proposal.target_refs or []),
            measurement_refs=list(proposal.measurement_refs or []),
        )
        _require_resolution_criterion(resolution, proposal.acceptance_id_ref)
    except ReferencesUnresolvable:
        return Outcome(status=409, refused=STALE)
    # **The canonical function is the single authority for the grant at write time**, and
    # this is where a second service-level re-read used to be. Measured, not assumed:
    # ``business_admin_allowed`` takes ``FOR SHARE`` on the grant row, so the check at the
    # top of the request pins that row for the whole transaction -- a concurrent revocation
    # blocks until commit (probed on a scratch database: the revoking statement times out).
    # A second call inside the same transaction therefore *cannot* return a different
    # answer, which is why a mutation deleting it changed nothing and no test could kill
    # it. Dead code that looks like a security check is worse than its absence: it tells a
    # reader the grant is enforced twice when the second time is provably inert.
    #
    # What does hold: the first check, which takes the lock, and
    # ``public.release_acceptance_confirm``, which re-reads the grant itself and so covers
    # any path that reaches the tables without passing through this function (§4-1). §4
    # step 8's "re-check immediately before the write" is satisfied there, inside the same
    # statement that inserts the row.
    #
    # And the manifest once more from the locked row, so the digest the decision stores is
    # the one that was true at the moment of writing rather than at the moment of reading.
    current = session.scalars(
        select(ReleaseManifest.manifest_sha256).where(
            ReleaseManifest.tenant_id == principal.tenant_id,
            ReleaseManifest.release_id == release_id,
        )
    ).one()
    if str(current) != str(proposal.target_manifest_sha256):
        _close_proposal(
            session, principal=principal, proposal=proposal, kind="manifest-superseded", now=now
        )
        return Outcome(status=409, refused=STALE)

    acceptance_id = new_id("acceptance")
    event_id = _audit(
        session,
        principal=principal,
        action=AUDIT_CONFIRMED,
        detail={
            "releaseId": release.release_id,
            "proposalId": proposal_id,
            "acceptanceId": acceptance_id,
            "manifestSha256": release.manifest_sha256,
            "proposalDigest": proposal.proposal_digest,
        },
        now=now,
    )
    # The canonical function, with the acting human in transaction state rather than in
    # an argument (§4-1). It re-derives the active user, the live grant, the digest, the
    # expiry, the slot and the distinct voter, and raises if any of them moved.
    with actor_scope(session, principal.user_id):
        try:
            session.execute(
                text(
                    "SELECT public.release_acceptance_confirm("
                    ":proposal, :pdigest, :mdigest, :acceptance, :vote, :event, :identity,"
                    ":version, :issuer, :client, :auth_time, :amr, :now)"
                ),
                {
                    "proposal": proposal_id,
                    "pdigest": proposal.proposal_digest,
                    "mdigest": release.manifest_sha256,
                    "acceptance": acceptance_id,
                    "vote": new_id("acceptance_vote"),
                    "event": new_id("acceptance_lifecycle_event"),
                    "identity": event_id,
                    "version": proof.attestation_version,
                    "issuer": proof.issuer,
                    "client": proof.client_id,
                    "auth_time": proof.auth_time,
                    "amr": proof.amr_sha256,
                    "now": now,
                },
            )
        except Exception as error:  # noqa: BLE001 - mapped to the contract below
            raise _mapped_db_refusal(error) from error
    return Outcome(
        status=201,
        body={
            "acceptanceId": acceptance_id,
            "releaseId": release.release_id,
            "acceptanceIdRef": proposal.acceptance_id_ref,
            "outcome": "accepted",
            "state": "recorded",
            "acceptedManifestSha256": release.manifest_sha256,
            "manifestMatches": True,
            "decisionSignOff": True,
            "decisionConfirmationCount": 2,
            "decidedAt": now,
            "replayed": False,
        },
    )


def _mapped_db_refusal(error: Exception) -> InvError:
    """The canonical function's refusals, in the contract's words.

    The function raises ``insufficient_privilege`` for "not this person, not active, not
    permitted" and ``check_violation`` for state that moved. §7 keeps the first two
    indistinguishable in the response, which is why the same 403 covers the proposer
    confirming their own proposal.
    """
    text_of = str(getattr(error, "orig", error))
    if "proposer cannot be the second operator" in text_of:
        return InvError(AUTH_PROJECT_SCOPE, "a distinct second operator is required")
    if (
        "insufficient_privilege" in text_of
        or "may not accept" in text_of
        or "not active" in text_of
    ):
        return InvError(AUTH_PROJECT_SCOPE, "fresh interactive operator authentication is required")
    return InvError(GRAPH_INVALID_TRANSITION, "the proposal state changed before it was confirmed")


def withdraw(
    session: Session,
    *,
    principal,
    release_id: str,
    acceptance_id: str,
    request: Any,
    now: dt.datetime,
) -> dict[str, Any]:
    """One fresh operator may stop a decision counting, including one they did not make.

    Append-only: the decision, its votes and its evidence are untouched. A withdrawal
    that deleted them would remove the record of what was once trusted, which is the
    thing a later reader most needs.
    """
    release = _locked_release(session, tenant_id=principal.tenant_id, release_id=release_id)
    decision = session.scalars(
        select(AcceptanceRecord)
        .where(
            AcceptanceRecord.tenant_id == principal.tenant_id,
            AcceptanceRecord.release_id == release_id,
            AcceptanceRecord.acceptance_id == acceptance_id,
        )
        .with_for_update()
    ).one_or_none()
    if decision is None:
        raise InvError(RES_RELEASE_NOT_FOUND, "release acceptance not found")
    if request.accepted_manifest_sha256 != str(decision.accepted_manifest_sha256):
        # The digest on the row, not the release's current one: they differ exactly when
        # the release has moved on, which is a common reason to withdraw (§6).
        raise InvError(
            GRAPH_INVALID_TRANSITION, "the withdrawal names a different accepted composition"
        )
    already = session.scalars(
        select(ReleaseAcceptanceWithdrawal).where(
            ReleaseAcceptanceWithdrawal.tenant_id == principal.tenant_id,
            ReleaseAcceptanceWithdrawal.acceptance_id == acceptance_id,
        )
    ).one_or_none()
    if already is not None:
        raise InvError(GRAPH_INVALID_TRANSITION, "this decision is already withdrawn")

    # §4 step 8 for this route as well: the fresh-auth proof and the live grant are
    # re-checked immediately before the append, because everything above this line was a
    # read and a lock and the operator's window can close inside it.
    try:
        fresh.proof_of_interactive_human(principal, now=now)
    except fresh.NotInteractiveHuman as error:
        raise InvError(
            AUTH_PROJECT_SCOPE, "fresh interactive operator authentication is required"
        ) from error
    settings_service.require_global_administrator(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        permission=PERMISSION,
    )

    withdrawal_id = new_id("acceptance_withdrawal")
    session.add(
        ReleaseAcceptanceWithdrawal(
            withdrawal_id=withdrawal_id,
            tenant_id=principal.tenant_id,
            release_id=release_id,
            acceptance_id=acceptance_id,
            reason_code=request.reason_code,
            accepted_manifest_sha256=decision.accepted_manifest_sha256,
            withdrawn_by_user_id=principal.user_id,
            withdrawn_at=now,
        )
    )
    session.execute(
        text(
            "UPDATE release_acceptance_slots SET active_acceptance_id=NULL, updated_at=:now "
            "WHERE tenant_id=:t AND release_id=:r AND acceptance_id_ref=:c "
            "AND active_acceptance_id=:a"
        ),
        {
            "now": now,
            "t": principal.tenant_id,
            "r": release_id,
            "c": decision.acceptance_id_ref,
            "a": acceptance_id,
        },
    )
    session.flush()
    _audit(
        session,
        principal=principal,
        action=AUDIT_WITHDRAWN,
        detail={
            "releaseId": release_id,
            "acceptanceId": acceptance_id,
            "withdrawalId": withdrawal_id,
            "reasonCode": request.reason_code,
            "manifestSha256": decision.accepted_manifest_sha256,
        },
        now=now,
    )
    answer = release_sign_off.evaluate(
        session, tenant_id=principal.tenant_id, release=release, now=now
    )
    return {
        "withdrawalId": withdrawal_id,
        "acceptanceId": acceptance_id,
        "releaseId": release_id,
        "state": "withdrawn",
        "acceptedManifestSha256": decision.accepted_manifest_sha256,
        "withdrawnAcceptanceCountsTowardSignOff": False,
        # The release-scope aggregate after this commit, which is the one field the
        # write surface shares with the read surface and means the same thing (§3).
        "operatorSignOff": answer.operator_sign_off,
        "reasonCode": request.reason_code,
        "withdrawnAt": now,
        "replayed": False,
    }
