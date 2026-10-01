"""The one function that answers "is this release operator-signed" (S12-BE, #282 §5).

There used to be two answers. ``operator_sign_off()`` read the acceptance rows and
``pilot_readiness()`` had its own rules -- an AC-12 row must exist, no ``rejected`` row
may stand, no row may name another manifest -- and the two could disagree. §5 closes
that: one projection, and ``pilot_readiness`` asks it rather than re-deciding. The
separate "a rejected acceptance stands against this release" rule is gone, because a
rejected criterion is simply not an accepted one, and a rule that says the same thing
twice is a rule that can be changed in one place only.

**True requires all of this, for every criterion the pinned registry requires**:

* an *active* final decision -- the one the coordination slot names, not any row that
  was ever written;
* its outcome is ``accepted``;
* two **distinct** operators with valid fresh interactive attestation voted on the
  proposal behind it;
* it has not been withdrawn;
* the digest it pinned equals the release's current manifest digest;
* its target and measurement references resolve in the authoritative registries.

Any required criterion missing, conditional, rejected, withdrawn, drifted or
unresolvable makes the whole answer false. The registry itself must load and be
non-empty (``all([])`` is ``True``, which is the failure this is written to avoid), and
the release must carry the policy pin it was accepted against.

**What it reports today.** The last bullet is false for every decision, because the
authoritative target registry and the Evidence canonical-digest resolver do not exist
-- the contract owner made that a separate card (§0-1.2, §0-1.4) and forbade comparing
the caller's own values instead. So this projection answers false everywhere, which is
exactly what the read surface's ``Literal[False]`` and ``Literal[0]`` say. They are not
a placeholder standing in for an unwritten projection; the projection is here, and it
agrees with them. ``refs_bound`` is the one switch the follow-up card flips, and the
tests drive it both ways so the satisfied path is tested rather than asserted.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import (
    HUMAN_ATTESTATION_VERSION,
    AcceptanceRecord,
    ReleaseAcceptanceSlot,
    ReleaseAcceptanceVote,
    ReleaseAcceptanceWithdrawal,
    ReleaseManifest,
)
from . import release_acceptance_policy as policy

#: Whether the authoritative target registry and the Evidence canonical-digest resolver
#: are bound in this build. False, measured rather than assumed: ``contracts`` holds no
#: target registry and ``evidence_envelopes`` has no canonical envelope digest column.
#: The follow-up contract card flips this; until then no decision can satisfy a
#: criterion, and no write route is enabled either (§0-1.2, §0-1.4, §0-1.5).
AUTHORITATIVE_REFS_BOUND = False

#: Why a release is not signed off, as the read surface's closed value (§0-1.1). One
#: string for every prerequisite gap, because a reader deciding between "nobody signed"
#: and "this surface cannot tell" needs the second answer, not a taxonomy of it.
PREREQUISITES_UNAVAILABLE = "release-acceptance-prerequisites-unavailable"


@dataclass(frozen=True)
class CriterionState:
    """One required criterion, and why it is or is not satisfied."""

    acceptance_id_ref: str
    satisfied: bool
    #: Absent when satisfied. Never shown to a caller -- the public contract carries a
    #: single closed blocker value -- and present so an operator reading a log or a test
    #: failure learns which criterion and which rule, instead of "false".
    reason: str | None = None
    acceptance_id: str | None = None
    #: Distinct users whose attested votes admitted this decision.
    operators: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SignOff:
    """The whole answer for one release."""

    operator_sign_off: bool
    confirmed_operator_count: int
    blocked_by: str | None
    criteria: tuple[CriterionState, ...]
    policy_version: int | None
    policy_registry_sha256: str | None
    #: Why the aggregate is false when it is not a specific criterion's fault -- an
    #: unloadable registry, an unpinned release, unbound resolvers.
    reason: str | None = None


def _refused(reason: str, criteria: tuple[CriterionState, ...] = ()) -> SignOff:
    return SignOff(
        operator_sign_off=False,
        confirmed_operator_count=0,
        blocked_by=PREREQUISITES_UNAVAILABLE,
        criteria=criteria,
        policy_version=None,
        policy_registry_sha256=None,
        reason=reason,
    )


def evaluate(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    release: ReleaseManifest,
    now: dt.datetime,
    refs_bound: bool = AUTHORITATIVE_REFS_BOUND,
) -> SignOff:
    """Answer for one release, reading the rows rather than trusting a cached flag."""

    loaded = policy.load(
        pinned_sha256=release.policy_registry_sha256, pinned_version=release.policy_version
    )
    if not loaded.usable:
        # Includes the empty-registry case, which is the one that would otherwise read
        # as "every required criterion is accepted".
        return _refused(loaded.refused or "the policy registry lists no criteria")

    slots = {
        slot.acceptance_id_ref: slot
        for slot in session.scalars(
            select(ReleaseAcceptanceSlot).where(
                ReleaseAcceptanceSlot.tenant_id == tenant_id,
                ReleaseAcceptanceSlot.release_id == release.release_id,
            )
        ).all()
    }
    withdrawn = {
        row.acceptance_id
        for row in session.scalars(
            select(ReleaseAcceptanceWithdrawal).where(
                ReleaseAcceptanceWithdrawal.tenant_id == tenant_id,
                ReleaseAcceptanceWithdrawal.release_id == release.release_id,
            )
        ).all()
    }

    states: list[CriterionState] = []
    operators: set[str] = set()
    for required in loaded.required_criteria:
        ref = required.acceptance_id_ref
        slot = slots.get(ref)
        if slot is None or slot.active_acceptance_id is None:
            states.append(
                CriterionState(ref, False, reason="no active decision for this criterion")
            )
            continue
        decision = session.get(AcceptanceRecord, slot.active_acceptance_id)
        if decision is None or str(decision.tenant_id) != str(tenant_id):
            states.append(CriterionState(ref, False, reason="the active decision is unreadable"))
            continue
        if decision.acceptance_id in withdrawn:
            # §6: the criterion the withdrawn decision covered is unmet until a new
            # valid final exists. The row is kept; it just stops counting.
            states.append(
                CriterionState(
                    ref, False, reason="the active decision was withdrawn",
                    acceptance_id=decision.acceptance_id,
                )
            )
            continue
        if decision.outcome != "accepted":
            states.append(
                CriterionState(
                    ref, False, reason=f"the active decision is {decision.outcome}",
                    acceptance_id=decision.acceptance_id,
                )
            )
            continue
        if str(decision.accepted_manifest_sha256) != str(release.manifest_sha256):
            # A new composition under the same name needs a new proposal and two fresh
            # operators. No row is edited for this to become false.
            states.append(
                CriterionState(
                    ref, False, reason="the decision pinned a different composition",
                    acceptance_id=decision.acceptance_id,
                )
            )
            continue
        if decision.attestation_version != HUMAN_ATTESTATION_VERSION:
            states.append(
                CriterionState(
                    ref, False, reason="the decision carries no fresh human attestation",
                    acceptance_id=decision.acceptance_id,
                )
            )
            continue
        voters = frozenset(
            vote.user_id
            for vote in session.scalars(
                select(ReleaseAcceptanceVote).where(
                    ReleaseAcceptanceVote.tenant_id == tenant_id,
                    ReleaseAcceptanceVote.proposal_id == decision.proposal_id,
                    ReleaseAcceptanceVote.human_attestation_version
                    == HUMAN_ATTESTATION_VERSION,
                )
            ).all()
        )
        if len(voters) < 2:
            states.append(
                CriterionState(
                    ref, False, reason="fewer than two attested operators",
                    acceptance_id=decision.acceptance_id, operators=voters,
                )
            )
            continue
        if not refs_bound:
            # §3-1: without an authoritative registry to resolve against, an accepted
            # decision is a decision about references nobody can check. It does not
            # count, and no fallback compares the caller's own values.
            states.append(
                CriterionState(
                    ref,
                    False,
                    reason="target and measurement references cannot be resolved",
                    acceptance_id=decision.acceptance_id,
                    operators=voters,
                )
            )
            continue
        operators |= voters
        states.append(
            CriterionState(
                ref, True, acceptance_id=decision.acceptance_id, operators=voters
            )
        )

    satisfied = bool(states) and all(state.satisfied for state in states)
    return SignOff(
        operator_sign_off=satisfied,
        confirmed_operator_count=len(operators) if satisfied else 0,
        blocked_by=None if satisfied else PREREQUISITES_UNAVAILABLE,
        criteria=tuple(states),
        policy_version=loaded.policy_version,
        policy_registry_sha256=loaded.registry_sha256,
        reason=None if satisfied else "a required criterion is not satisfied",
    )


def unmet_criteria(answer: SignOff) -> list[str]:
    """The blockers ``pilot_readiness`` reports, phrased for a person reading a list."""
    if answer.reason and not answer.criteria:
        return [f"release acceptance: {answer.reason}"]
    return [
        f"AC {state.acceptance_id_ref}: {state.reason}"
        for state in answer.criteria
        if not state.satisfied
    ]


def evaluate_for_payload(
    session: Session, *, tenant_id: uuid.UUID, release: ReleaseManifest, now: dt.datetime
) -> dict[str, Any]:
    """The projection in the shape the read surface reports it.

    Deliberately not wired into ``_manifest_payload`` yet: the public contract pins
    ``operatorSignOff`` to ``Literal[False]`` and ``confirmedOperatorCount`` to
    ``Literal[0]`` until the prerequisites land (§0), and publishing a computed value
    now would mean the contract and the code disagreed about which was authoritative.
    What this does give is the thing that was missing -- a projection whose answer can
    be compared with those literals, which a test does.
    """
    answer = evaluate(session, tenant_id=tenant_id, release=release, now=now)
    return {
        "operatorSignOff": answer.operator_sign_off,
        "operatorSignOffBlockedBy": answer.blocked_by,
        "confirmedOperatorCount": answer.confirmed_operator_count,
    }
