"""VF-CL-03: licensePolicy/classification is an EXACT comparison, fail-closed (Codex verdict).

Two layers, both without a database:

1. Kernel registry binding policy (``RegistryBindingPolicy.allowed``, consulted by the
   kernel as ``(body['licensePolicy'], body['classification']) not in policy.allowed``) and
   its only builder ``configured_registry_policy``: near-misses (case, whitespace, prefix,
   swapped order, other classification) are refused and configuration cannot widen the set.
2. Claude-owned import adapter ``saintvision.adapters.model_import``: an import proposal must
   equal the immutable manifest declaration field-for-field; missing, differing, extra, and
   undeclared fields are each a refusal.

A match at either layer means ONLY that the compared values are identical. It is NOT a legal
licence permission and NOT an execution approval; those are decided by operators and by the
kernel's deployment admission, not by this comparison.
"""

from __future__ import annotations

import pytest

from inv.model_registry_binding import RegistryBindingPolicy
from inv.model_registry_config import configured_registry_policy
from saintvision.adapters.model_import import (
    MODEL_IMPORT_DECLARATION_MISMATCH,
    compare_declaration,
    require_exact_declaration,
)
from saintvision.errors import InvError

ALLOWED = frozenset({("Apache-2.0", "internal"), ("proprietary-invion", "restricted")})


def admits(policy: RegistryBindingPolicy, license_policy: str, classification: str) -> bool:
    """The kernel's admission predicate, verbatim in shape: set membership of the exact pair."""
    return (license_policy, classification) in policy.allowed


@pytest.fixture
def policy() -> RegistryBindingPolicy:
    return RegistryBindingPolicy(version="test-1", allowed=ALLOWED)


def test_exact_pair_is_admitted(policy):
    assert admits(policy, "Apache-2.0", "internal")
    assert admits(policy, "proprietary-invion", "restricted")


@pytest.mark.parametrize("license_policy, classification", [
    ("apache-2.0", "internal"),          # case
    ("Apache-2.0 ", "internal"),         # trailing whitespace
    (" Apache-2.0", "internal"),         # leading whitespace
    ("Apache-2.0", "Internal"),          # classification case
    ("Apache-2.0-or-later", "internal"), # prefix / superset string
    ("Apache-2.0", "public"),            # allowed license, other classification
    ("proprietary-invion", "internal"),  # cross pairing of two allowed pairs
    ("internal", "Apache-2.0"),          # swapped order
    ("", "internal"),                    # empty license
    ("Apache-2.0", ""),                  # empty classification
])
def test_near_misses_are_refused(policy, license_policy, classification):
    assert not admits(policy, license_policy, classification)


def test_policy_cannot_be_empty_or_unbounded():
    with pytest.raises(ValueError):
        RegistryBindingPolicy(version="v", allowed=frozenset())
    with pytest.raises(ValueError):
        RegistryBindingPolicy(version="v", allowed=frozenset({("a", "b", "c")}))
    with pytest.raises(ValueError):
        RegistryBindingPolicy(version="v", allowed=frozenset({("a" * 257, "b")}))
    with pytest.raises(ValueError):
        RegistryBindingPolicy(version="", allowed=ALLOWED)


def test_configuration_builds_exactly_the_declared_pairs_and_nothing_wider():
    policy = configured_registry_policy({
        "version": "cfg-1",
        "allowed": [
            {"licensePolicy": "Apache-2.0", "classification": "internal"},
            {"licensePolicy": "proprietary-invion", "classification": "restricted"},
        ],
    })
    assert policy.allowed == ALLOWED
    assert not admits(policy, "Apache-2.0", "restricted")


@pytest.mark.parametrize("entry", [
    {"licensePolicy": "Apache-2.0"},                                        # missing classification
    {"classification": "internal"},                                         # missing license
    {"licensePolicy": "Apache-2.0", "classification": "internal", "x": 1},  # extra key
    {"licensePolicy": ["Apache-2.0"], "classification": "internal"},        # non-string
    {"licensePolicy": "Apache-2.0", "classification": "Internal-*"},        # wildcard-looking value is just a string, but must not match 'internal'
])
def test_configuration_refuses_or_does_not_widen(entry):
    value = {"version": "cfg-1", "allowed": [entry]}
    try:
        policy = configured_registry_policy(value)
    except ValueError:
        return  # refused: fail-closed
    # If the parser accepted it, the only admitted pair is the literal one it declared.
    assert not admits(policy, "Apache-2.0", "internal") or entry == {"licensePolicy": "Apache-2.0", "classification": "internal"}


def test_duplicate_pairs_are_refused_not_collapsed():
    with pytest.raises(ValueError):
        configured_registry_policy({"version": "cfg-1", "allowed": [
            {"licensePolicy": "Apache-2.0", "classification": "internal"},
            {"licensePolicy": "Apache-2.0", "classification": "internal"},
        ]})


# ---------------------------------------------------------------------------
# Layer 2: import proposal vs immutable manifest declaration (adapter, fail-closed)
# ---------------------------------------------------------------------------

MANIFEST = {"modelId": "mdl_x", "version": "3", "licensePolicy": "Apache-2.0", "classification": "internal"}


def test_identical_proposal_matches_and_means_nothing_more():
    assert compare_declaration(MANIFEST, {"licensePolicy": "Apache-2.0", "classification": "internal"}) == []
    require_exact_declaration(MANIFEST, {"licensePolicy": "Apache-2.0", "classification": "internal"})


@pytest.mark.parametrize("proposal, expected", [
    ({"classification": "internal"}, ["missing:licensePolicy"]),
    ({"licensePolicy": "Apache-2.0"}, ["missing:classification"]),
    ({}, ["missing:licensePolicy", "missing:classification"]),
    ({"licensePolicy": "apache-2.0", "classification": "internal"}, ["differs:licensePolicy"]),
    ({"licensePolicy": "Apache-2.0 ", "classification": "internal"}, ["differs:licensePolicy"]),
    ({"licensePolicy": "Apache-2.0", "classification": "Internal"}, ["differs:classification"]),
    ({"licensePolicy": "Apache-2.0", "classification": " internal"}, ["differs:classification"]),
    ({"licensePolicy": "Apache-2.0", "classification": "public"}, ["differs:classification"]),      # relaxation attempt
    ({"licensePolicy": "Apache-2.0", "classification": "restricted"}, ["differs:classification"]),  # tightening is still a mismatch
    ({"licensePolicy": "Apache-2.0-or-later", "classification": "internal"}, ["differs:licensePolicy"]),
    ({"licensePolicy": ["Apache-2.0"], "classification": "internal"}, ["differs:licensePolicy"]),   # non-string
    ({"licensePolicy": "Apache-2.0", "classification": "internal", "waiver": True}, ["extra:waiver"]),
    ({"licensePolicy": "Apache-2.0", "classification": "internal", "classification ": "public"}, ["extra:classification "]),
])
def test_every_deviation_from_the_declaration_is_named_and_refused(proposal, expected):
    assert compare_declaration(MANIFEST, proposal) == expected
    with pytest.raises(InvError) as err:
        require_exact_declaration(MANIFEST, proposal)
    assert err.value.code == MODEL_IMPORT_DECLARATION_MISMATCH
    assert err.value.status == 409 and err.value.extra["mismatches"] == expected
    # The refusal names fields, never the proposed values.
    for field in expected:
        assert str(proposal.get(field.split(":", 1)[1], "")) not in err.value.message or proposal.get(field.split(":", 1)[1]) in ("", None)


@pytest.mark.parametrize("manifest", [
    {"modelId": "mdl_x", "version": "3", "classification": "internal"},          # declaration lacks license
    {"modelId": "mdl_x", "version": "3", "licensePolicy": None, "classification": "internal"},
    {},
])
def test_an_incomplete_declaration_cannot_be_matched(manifest):
    reasons = compare_declaration(manifest, {"licensePolicy": "Apache-2.0", "classification": "internal"})
    assert any(r.startswith("undeclared:") for r in reasons)
    with pytest.raises(InvError):
        require_exact_declaration(manifest, {"licensePolicy": "Apache-2.0", "classification": "internal"})


def test_comparison_is_pure_and_does_not_mutate_inputs():
    manifest = dict(MANIFEST)
    proposal = {"licensePolicy": "Apache-2.0", "classification": "public"}
    compare_declaration(manifest, proposal)
    assert manifest == MANIFEST and proposal == {"licensePolicy": "Apache-2.0", "classification": "public"}
