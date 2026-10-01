"""The digest two operators must agree on (#282 §3-2).

The tests are in two groups, and the second is the point. The first says the same
content digests the same however it is spelled -- key order, zone, equal instants.
The second says **every field changes it**: a digest that ignored one field would let a
confirmer agree to a proposal whose that-field differs from what they read, which is
precisely the review this digest exists to make binding. So there is one test that
walks the whole field list and mutates each in turn, rather than a few spot checks.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from saintvision.services import release_acceptance_digest as digest  # noqa: E402

UTC = dt.timezone.utc
KST = dt.timezone(dt.timedelta(hours=9))
EXPIRES = dt.datetime(2026, 10, 1, 11, 5, 0, tzinfo=UTC)
OBSERVED = dt.datetime(2026, 10, 1, 10, 0, 0, 123456, tzinfo=UTC)


def fields(**overrides):
    base = dict(
        tenant_id="22222222-2222-2222-2222-222222222222",
        release_id="rel_01J8Z3XQ2K9WMV5T7N4B6C8D0E",
        acceptance_id_ref="AC-12",
        outcome="accepted",
        target_manifest_sha256="a" * 64,
        policy_version=1,
        policy_registry_sha256="b" * 64,
        reason_code="OPERATIONAL_ACCEPTANCE",
        target_refs=[
            {"targetId": "target.one", "targetSha256": "c" * 64},
            {"targetId": "target.two", "targetSha256": "d" * 64},
        ],
        measurement_refs=[
            {"evidenceId": "evidence.one", "evidenceSha256": "e" * 64, "observedAt": OBSERVED}
        ],
        known_limitations=[],
        expires_at=EXPIRES,
    )
    base.update(overrides)
    return base


# ----------------------------------------------------------- one spelling per content


def test_the_digest_is_lowercase_hex_sha256_of_the_canonical_bytes():
    payload = digest.canonical_payload(**fields())
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    value = digest.proposal_digest(**fields())
    assert value == expected
    assert len(value) == 64 and value == value.lower()


def test_the_canonical_field_set_is_the_contract_list():
    assert set(digest.canonical_payload(**fields())) == set(digest.DIGEST_FIELDS)


def test_the_bytes_carry_no_spaces_and_sorted_keys():
    raw = digest.canonical_bytes(digest.canonical_payload(**fields())).decode()
    assert ", " not in raw and '": ' not in raw
    keys = [part.split('"')[1] for part in raw.split('{')[1].split(",")[:3]]
    assert keys == sorted(keys)


def test_the_same_moment_in_another_zone_digests_the_same():
    """A confirmation computed in Seoul must match one computed in UTC."""
    assert digest.proposal_digest(**fields(expires_at=EXPIRES.astimezone(KST))) == (
        digest.proposal_digest(**fields())
    )


def test_a_naive_instant_is_refused_rather_than_assumed_to_be_local():
    with pytest.raises(ValueError, match="which zone"):
        digest.proposal_digest(**fields(expires_at=EXPIRES.replace(tzinfo=None)))


def test_fractional_seconds_are_always_six_digits():
    whole = dt.datetime(2026, 10, 1, 11, 0, 0, tzinfo=UTC)
    assert digest.format_instant(whole) == "2026-10-01T11:00:00.000000Z"
    half = dt.datetime(2026, 10, 1, 11, 0, 0, 500000, tzinfo=UTC)
    assert digest.format_instant(half) == "2026-10-01T11:00:00.500000Z"
    # And the two are not the same value, which is the reason the padding is fixed.
    assert digest.format_instant(whole) != digest.format_instant(half)


def test_the_models_and_plain_mappings_digest_identically():
    """A caller holding validated request models should not have to unpack them."""
    from saintvision.api import schemas

    model_fields = fields(
        target_refs=[
            schemas.ReleaseAcceptanceTargetRef.model_validate(
                {"targetId": "target.one", "targetSha256": "c" * 64}
            ),
            schemas.ReleaseAcceptanceTargetRef.model_validate(
                {"targetId": "target.two", "targetSha256": "d" * 64}
            ),
        ],
        measurement_refs=[
            schemas.ReleaseAcceptanceMeasurementRef.model_validate(
                {
                    "evidenceId": "evidence.one",
                    "evidenceSha256": "e" * 64,
                    "observedAt": OBSERVED,
                }
            )
        ],
    )
    assert digest.proposal_digest(**model_fields) == digest.proposal_digest(**fields())


# ----------------------------------------------------------- every field is bound


MUTATIONS = {
    "tenantId": dict(tenant_id="33333333-3333-3333-3333-333333333333"),
    "releaseId": dict(release_id="rel_01J8Z3XQ2K9WMV5T7N4B6C8D0F"),
    "acceptanceIdRef": dict(acceptance_id_ref="AC-13"),
    "outcome": dict(outcome="conditional"),
    "targetManifestSha256": dict(target_manifest_sha256="f" * 64),
    "policyVersion": dict(policy_version=2),
    "policyRegistrySha256": dict(policy_registry_sha256="0" * 64),
    "reasonCode": dict(reason_code="SECURITY_REVIEW"),
    "targetRefs": dict(
        target_refs=[{"targetId": "target.one", "targetSha256": "9" * 64}]
    ),
    "measurementRefs": dict(
        measurement_refs=[
            {"evidenceId": "evidence.two", "evidenceSha256": "e" * 64, "observedAt": OBSERVED}
        ]
    ),
    "knownLimitations": dict(known_limitations=["browser acceptance not observed"]),
    "expiresAt": dict(expires_at=EXPIRES + dt.timedelta(seconds=1)),
}


def test_the_mutation_table_covers_every_contract_field():
    """A field the table forgot would be a field the next test never checked."""
    assert set(MUTATIONS) == set(digest.DIGEST_FIELDS)


@pytest.mark.parametrize("field", sorted(MUTATIONS))
def test_changing_any_field_changes_the_digest(field):
    assert digest.proposal_digest(**fields(**MUTATIONS[field])) != digest.proposal_digest(
        **fields()
    )


def test_reordering_the_refs_changes_the_digest():
    """Order is meaning: the list is what the operator reviewed, in that order (§3-2)."""
    reversed_targets = list(reversed(fields()["target_refs"]))
    assert digest.proposal_digest(**fields(target_refs=reversed_targets)) != (
        digest.proposal_digest(**fields())
    )


def test_an_observed_at_inside_a_measurement_is_bound_too():
    """The nested instant is part of the content, not decoration."""
    moved = [
        {
            "evidenceId": "evidence.one",
            "evidenceSha256": "e" * 64,
            "observedAt": OBSERVED + dt.timedelta(microseconds=1),
        }
    ]
    assert digest.proposal_digest(**fields(measurement_refs=moved)) != digest.proposal_digest(
        **fields()
    )
