"""The proposal digest a second operator confirms (S12-BE, #282 §3-2).

A confirmation has to be a confirmation of *content*. If the second operator sent only
a proposal ID, they would be agreeing to whatever that ID currently resolves to, and
the two-person rule would be two people agreeing to a pointer. So the server derives a
digest over everything the decision is about, returns it in the review response, and
the confirmer sends it back; a mismatch means they were looking at something else.

Every rule here exists because a digest is only useful if two honest parties compute
the same one and a dishonest change computes a different one:

* **alias keys, sorted, compact separators, UTF-8.** One spelling of the same content,
  so a reordered JSON object is not a different proposal;
* **arrays are never sorted.** ``targetRefs`` and ``measurementRefs`` carry order as
  meaning -- the list is what the operator reviewed, in the order they reviewed it --
  so reordering is a different proposal and the digest says so;
* **every instant is UTC with exactly six fractional digits.** ``2026-10-01T11:00:00Z``
  and ``2026-10-01T20:00:00+09:00`` are the same moment and must digest identically,
  while ``.5`` and ``.500000`` must not be two spellings of one value;
* **a naive datetime is refused.** Interpreting it as local time would make the digest
  depend on the server's zone, which is to say two servers would disagree about whether
  a confirmation matched.

The field list is ``(tenantId, releaseId, acceptanceIdRef, outcome,
targetManifestSha256, policyVersion, policyRegistrySha256, reasonCode, targetRefs,
measurementRefs, knownLimitations, expiresAt)`` and is closed: adding to it changes
every digest, so it is a contract change (§3-2), not an implementation detail.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Sequence
from typing import Any

#: The exact key order is irrelevant -- the serialisation sorts -- but the exact key
#: *set* is the contract. Named here so a reader can compare it with §3-2 without
#: reading the function.
DIGEST_FIELDS = (
    "tenantId",
    "releaseId",
    "acceptanceIdRef",
    "outcome",
    "targetManifestSha256",
    "policyVersion",
    "policyRegistrySha256",
    "reasonCode",
    "targetRefs",
    "measurementRefs",
    "knownLimitations",
    "expiresAt",
)


def format_instant(value: dt.datetime) -> str:
    """UTC, ``YYYY-MM-DDTHH:MM:SS.ffffffZ``, always six fractional digits.

    Refuses a naive datetime rather than assuming a zone: the digest would then depend
    on where the server runs, and a confirmation computed elsewhere would not match.
    """
    if not isinstance(value, dt.datetime):
        raise TypeError("an instant is required")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ValueError("an instant in the digest must say which zone it is in")
    utc = value.astimezone(dt.timezone.utc)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond:06d}Z"


def canonical_payload(
    *,
    tenant_id: Any,
    release_id: str,
    acceptance_id_ref: str,
    outcome: str,
    target_manifest_sha256: str,
    policy_version: int,
    policy_registry_sha256: str,
    reason_code: str,
    target_refs: Sequence[Any],
    measurement_refs: Sequence[Any],
    known_limitations: Sequence[str],
    expires_at: dt.datetime,
) -> dict[str, Any]:
    """The exact object the digest is taken over.

    Accepts either the contract models or plain mappings for the two ref lists, so a
    caller that has already validated a request does not have to take it apart and a
    test can state a vector without building models.
    """

    def target(item: Any) -> dict[str, str]:
        if isinstance(item, dict):
            return {"targetId": item["targetId"], "targetSha256": item["targetSha256"]}
        return {"targetId": item.target_id, "targetSha256": item.target_sha256}

    def measurement(item: Any) -> dict[str, str]:
        if isinstance(item, dict):
            return {
                "evidenceId": item["evidenceId"],
                "evidenceSha256": item["evidenceSha256"],
                "observedAt": format_instant(item["observedAt"]),
            }
        return {
            "evidenceId": item.evidence_id,
            "evidenceSha256": item.evidence_sha256,
            "observedAt": format_instant(item.observed_at),
        }

    payload = {
        "tenantId": str(tenant_id),
        "releaseId": release_id,
        "acceptanceIdRef": acceptance_id_ref,
        "outcome": outcome,
        "targetManifestSha256": target_manifest_sha256,
        "policyVersion": int(policy_version),
        "policyRegistrySha256": policy_registry_sha256,
        "reasonCode": reason_code,
        # Order preserved: the list is what was reviewed, in that order.
        "targetRefs": [target(item) for item in target_refs],
        "measurementRefs": [measurement(item) for item in measurement_refs],
        "knownLimitations": [str(item) for item in known_limitations],
        "expiresAt": format_instant(expires_at),
    }
    if set(payload) != set(DIGEST_FIELDS):
        # Not reachable from this function, and it is here because the field set is the
        # contract: a future edit that adds a key silently changes every digest.
        raise ValueError("the digest field set is fixed by the contract")
    return payload


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """One spelling: sorted keys, no spaces, UTF-8."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def proposal_digest(**fields: Any) -> str:
    """The lowercase hex SHA-256 of the canonical bytes."""
    return hashlib.sha256(canonical_bytes(canonical_payload(**fields))).hexdigest()
